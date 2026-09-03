"""Lector de notificaciones de transferencia SINPE recibida.

A diferencia de `comprobante_bac.py` -un formato fijo de "Etiqueta: valor", una
linea por campo- una notificacion de SINPE es una oracion en prosa, y cada banco
la redacta distinto. Por eso este archivo tiene un lector por banco, cada uno
comprobado contra una notificacion real de ese banco, y una funcion que elige
cual usar segun el dominio del remitente -el mismo criterio que ya separa los
`ProveedorDeCorreo` por proveedor de correo.

Solo se leen transferencias **recibidas** (acreditadas a la cuenta del titular):
es lo unico que hay una notificacion real para confirmar. Una transferencia
enviada por el titular tendria una redaccion distinta -no hay una muestra real
todavia, asi que este lector no intenta adivinarla.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.business.parsers.comprobante_bac import DOMINIO_REMITENTE_BAC

CAMPOS_OBLIGATORIOS = ("cuenta_destino", "fecha", "monto", "referencia")

# Dominio real desde el que el Banco Nacional manda sus notificaciones de SINPE
# (confirmado contra una notificacion real: bncontacto@bncr.fi.cr).
DOMINIO_REMITENTE_BNCR = "bncr.fi.cr"

_MONEDAS = {"colones": "CRC", "dolares": "USD", "dólares": "USD"}

# El comodin `.` ocupa el lugar de la tilde, igual que en comprobante_bac.py: no es
# una rareza confirmada en las dos muestras que validan este lector -las dos
# llegaron con los acentos intactos- pero es la misma precaucion, por si otra
# exportacion a PDF rompe el mapa de acentos como ya le pasa al de compra.
_IBAN = r"[A-Z]{2}[0-9X]{16,24}"
_HORA = r"\d{1,2}:\d{2}:\d{2}\s*[APap]\.?\s*[Mm]\.?"

_BNCR_DESTINATARIO = re.compile(r"Estimado\(a\):\s*(.+)")
_BNCR_CUENTA = re.compile(rf"realizada a la cuenta\s+({_IBAN})")
_BNCR_FECHA = re.compile(r"se realiz.\s+el\s+d.a\s+(\d{2}/\d{2}/\d{4})")
_BNCR_HORA = re.compile(rf"a las\s+({_HORA})")
_BNCR_MONTO = re.compile(r"por un monto de\s*([\d.,]+)\s*(Colones|D.lares)", re.IGNORECASE)
_BNCR_CONCEPTO = re.compile(r"por concepto de\s*(.+?)\.\s*El n.mero de comprobante", re.DOTALL)
_BNCR_COMPROBANTE = re.compile(r"n.mero de comprobante es\s*(\d+)")
_BNCR_REFERENCIA = re.compile(r"n.mero de referencia\s*(\d+)")

_BAC_DESTINATARIO = re.compile(r"Hola\s+(.+?)\s*:")
_BAC_REFERENCIA = re.compile(r"n.mero de referencia\s*(\d+)")
_BAC_CUENTA = re.compile(rf"cuenta IBAN\s*({_IBAN})")
_BAC_MONTO = re.compile(r"por un monto de\s*([\d.,]+)\s*(Colones|D.lares)", re.IGNORECASE)
# Se corta en "_" o "." porque la plantilla de BAC rellena el resto de la linea
# con guiones bajos cuando el concepto es corto -ver la nota en fixtures/LEEME.md.
_BAC_CONCEPTO = re.compile(r"por concepto de\s*([^_.]+)", re.DOTALL)
_BAC_FECHA_HORA = re.compile(rf"D.a y hora\s*(\d{{2}}/\d{{2}}/\d{{4}})\s+({_HORA})")


@dataclass(frozen=True)
class TransferenciaSinpeParseada:
    """Lo que el lector logro sacar de una notificacion de SINPE recibida.

    Es un resultado de lectura, no una entidad: no se guarda tal cual, igual que
    `ComprobanteParseado` de `comprobante_bac.py`.
    """

    banco: str
    destinatario: str | None
    cuenta_destino: str | None
    fecha: datetime | None
    moneda: str | None
    monto: Decimal | None
    concepto: str | None
    referencia: str | None
    # Solo el Banco Nacional lo incluye en el mensaje; BAC no.
    comprobante: str | None
    confianza: float

    @property
    def es_confiable(self) -> bool:
        """Bajo 0.75 la transferencia no se guarda sola: va a revision."""
        return self.confianza >= 0.75


def parsear_transferencia_sinpe(remitente: str, texto: str) -> TransferenciaSinpeParseada | None:
    """Elige el lector segun el dominio del remitente y lee la notificacion.

    Devuelve `None` -no lanza excepcion- para un remitente que no es ninguno de
    los dos bancos que este lector sabe leer todavia: es una situacion normal
    (`detectar_bancos` encuentra remitentes de SINPE de otros bancos todo el
    tiempo), no un error del programa.
    """
    dominio = remitente.lower()
    if DOMINIO_REMITENTE_BNCR in dominio:
        return _parsear_bncr(texto)
    if DOMINIO_REMITENTE_BAC in dominio:
        return _parsear_bac(texto)
    return None


def _parsear_bncr(texto: str) -> TransferenciaSinpeParseada:
    cuenta_destino = _primer_grupo(_BNCR_CUENTA, texto)
    fecha = _combinar_fecha_hora(
        _primer_grupo(_BNCR_FECHA, texto), _primer_grupo(_BNCR_HORA, texto)
    )
    moneda, monto = _leer_monto(_BNCR_MONTO, texto)

    return TransferenciaSinpeParseada(
        banco="Banco Nacional",
        destinatario=_primer_grupo(_BNCR_DESTINATARIO, texto),
        cuenta_destino=cuenta_destino,
        fecha=fecha,
        moneda=moneda,
        monto=monto,
        concepto=_primer_grupo(_BNCR_CONCEPTO, texto),
        referencia=_primer_grupo(_BNCR_REFERENCIA, texto),
        comprobante=_primer_grupo(_BNCR_COMPROBANTE, texto),
        confianza=_confianza(cuenta_destino, fecha, monto, _primer_grupo(_BNCR_REFERENCIA, texto)),
    )


def _parsear_bac(texto: str) -> TransferenciaSinpeParseada:
    cuenta_destino = _primer_grupo(_BAC_CUENTA, texto)
    coincidencia_fecha_hora = _BAC_FECHA_HORA.search(texto)
    fecha = (
        _combinar_fecha_hora(coincidencia_fecha_hora.group(1), coincidencia_fecha_hora.group(2))
        if coincidencia_fecha_hora
        else None
    )
    moneda, monto = _leer_monto(_BAC_MONTO, texto)
    referencia = _primer_grupo(_BAC_REFERENCIA, texto)

    return TransferenciaSinpeParseada(
        banco="BAC Credomatic",
        destinatario=_primer_grupo(_BAC_DESTINATARIO, texto),
        cuenta_destino=cuenta_destino,
        fecha=fecha,
        moneda=moneda,
        monto=monto,
        concepto=_primer_grupo(_BAC_CONCEPTO, texto),
        referencia=referencia,
        comprobante=None,  # BAC no manda un numero de comprobante aparte del de referencia.
        confianza=_confianza(cuenta_destino, fecha, monto, referencia),
    )


def _confianza(
    cuenta_destino: str | None,
    fecha: datetime | None,
    monto: Decimal | None,
    referencia: str | None,
) -> float:
    campos = {
        "cuenta_destino": cuenta_destino,
        "fecha": fecha,
        "monto": monto,
        "referencia": referencia,
    }
    encontrados = sum(1 for nombre in CAMPOS_OBLIGATORIOS if campos[nombre] is not None)
    return encontrados / len(CAMPOS_OBLIGATORIOS)


def _primer_grupo(patron: re.Pattern[str], texto: str) -> str | None:
    coincidencia = patron.search(texto)
    return coincidencia.group(1).strip() if coincidencia else None


def _leer_monto(patron: re.Pattern[str], texto: str) -> tuple[str | None, Decimal | None]:
    """`25,500.00 Colones` -> moneda ISO y monto exacto.

    La coma separa miles y el punto separa decimales, igual que en
    `comprobante_bac.py`. SINPE solo mueve colones en Costa Rica -"Dolares" se
    soporta por si acaso, pero ninguna de las dos muestras reales lo usa.
    """
    coincidencia = patron.search(texto)
    if coincidencia is None:
        return None, None
    moneda = _MONEDAS.get(coincidencia.group(2).lower())
    try:
        return moneda, Decimal(coincidencia.group(1).replace(",", ""))
    except ArithmeticError:
        return moneda, None


def _combinar_fecha_hora(fecha_str: str | None, hora_str: str | None) -> datetime | None:
    """`15/03/2026` + `09:12:45 AM` -> datetime. Las dos muestras reales usan hora de 12."""
    if fecha_str is None or hora_str is None:
        return None
    coincidencia_fecha = re.match(r"(\d{2})/(\d{2})/(\d{4})", fecha_str)
    coincidencia_hora = re.search(r"(\d{1,2}):(\d{2}):(\d{2})\s*([APap])", hora_str)
    if coincidencia_fecha is None or coincidencia_hora is None:
        return None
    dia, mes, anio = (int(grupo) for grupo in coincidencia_fecha.groups())
    hora12, minuto, segundo, meridiano = coincidencia_hora.groups()
    hora = int(hora12) % 12
    if meridiano.upper() == "P":
        hora += 12
    try:
        return datetime(anio, mes, dia, hora, int(minuto), int(segundo))
    except ValueError:
        return None
