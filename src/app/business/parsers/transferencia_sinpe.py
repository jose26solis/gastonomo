"""Lector de notificaciones de transferencia SINPE recibida.

A diferencia de `comprobante_bac.py` -un formato fijo de "Etiqueta: valor", una
linea por campo- una notificacion de SINPE es una oracion en prosa, y cada banco
la redacta distinto. Por eso este archivo tiene un lector exacto por banco, cada
uno comprobado contra una notificacion real de ese banco (BAC, Banco Nacional).

Para cualquier otro remitente -uno que `detectar_bancos` ya sabe que existe,
pero del que todavia no hay una notificacion real para validar un lector
exacto- hay un lector generico (`_parsear_generico`): busca los mismos
patrones que casi cualquier notificacion de SINPE comparte -un monto con su
moneda, una cuenta IBAN, una fecha, un numero de referencia- en vez de una
plantilla fija. Es menos preciso que un lector validado, así que nunca se
hace pasar por uno: cada resultado trae `confirmado=False`, y la pantalla lo
marca para revisar en vez de darlo por bueno solo porque el patron calzó.
Uno que no calza casi nada (`confianza` baja) ni siquiera llega a guardarse
-ver el umbral en `CuentaCorreoService._sincronizar_transferencias_sinpe`.

Solo se leen transferencias **recibidas** (acreditadas a la cuenta del titular):
es lo unico que hay notificaciones reales para confirmar. Una transferencia
enviada por el titular tendria una redaccion distinta -no hay una muestra real
todavia, asi que ni el lector exacto ni el generico intentan adivinarla.
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

# Patrones sueltos, no atados a la redacción de un banco en particular -es lo
# que usa `_parsear_generico` para un remitente sin lector exacto. Cada uno
# busca la forma en que casi cualquier notificación de SINPE en Costa Rica
# escribe ese dato, no una frase completa como los patrones de arriba.
_GEN_CUENTA = re.compile(rf"\b({_IBAN})\b")
_GEN_FECHA = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_GEN_MONTO = re.compile(
    r"([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*(colones|d.lares|dolares|crc|usd)", re.IGNORECASE
)
_GEN_REFERENCIA = re.compile(r"referencia\D{0,12}?(\d{6,30})", re.IGNORECASE)
_GEN_COMPROBANTE = re.compile(r"comprobante\D{0,12}?(\d{4,20})", re.IGNORECASE)
_GEN_CONCEPTO = re.compile(r"concepto\D{0,12}?:?\s*([^\n.]{3,80})", re.IGNORECASE)
_GEN_DOMINIO = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")

_MONEDAS_GENERICO = {
    "colones": "CRC", "crc": "CRC", "₡": "CRC",
    "dolares": "USD", "dólares": "USD", "usd": "USD", "$": "USD",
}  # fmt: skip


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
    # False para el lector genérico: el patrón calzó, pero nadie validó este
    # formato contra una notificación real de ese banco en particular. La
    # pantalla lo muestra igual -es mejor que nada- pero marcado para revisar.
    confirmado: bool = True

    @property
    def es_confiable(self) -> bool:
        """Bajo 0.75 la transferencia no se guarda sola: va a revision."""
        return self.confianza >= 0.75


def parsear_transferencia_sinpe(remitente: str, texto: str) -> TransferenciaSinpeParseada:
    """Elige el lector segun el dominio del remitente y lee la notificacion.

    BAC y Banco Nacional tienen lector exacto, validado contra una
    notificación real de cada uno. Cualquier otro remitente cae al lector
    genérico (`_parsear_generico`): nunca devuelve `None` -de eso se encarga
    el umbral de confianza en `CuentaCorreoService._sincronizar_transferencias_sinpe`,
    que descarta lo que el patrón genérico no pudo leer en absoluto.
    """
    dominio = remitente.lower()
    if DOMINIO_REMITENTE_BNCR in dominio:
        return _parsear_bncr(texto)
    if DOMINIO_REMITENTE_BAC in dominio:
        return _parsear_bac(texto)
    return _parsear_generico(remitente, texto)


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


def _parsear_generico(remitente: str, texto: str) -> TransferenciaSinpeParseada:
    """Lee lo que pueda con patrones sueltos, para un remitente sin lector exacto.

    No hay una notificación real de este banco contra la cual validar un
    lector propio -ver la nota del módulo. Lo que sí hay es que casi
    cualquier notificación de SINPE en Costa Rica menciona un monto con su
    moneda, una cuenta IBAN, una fecha y un número de referencia; buscar
    esos cuatro patrones sueltos encuentra algo en un banco nuevo sin
    inventarle el formato completo. `destinatario` se deja en blanco a
    propósito: el saludo ("Hola...", "Estimado(a)...") varía demasiado entre
    bancos como para arriesgar un nombre equivocado.
    """
    cuenta_destino = _primer_grupo(_GEN_CUENTA, texto)
    fecha = _primera_fecha_generica(texto)
    moneda, monto = _leer_monto(_GEN_MONTO, texto, monedas=_MONEDAS_GENERICO)
    referencia = _primer_grupo(_GEN_REFERENCIA, texto)

    return TransferenciaSinpeParseada(
        banco=_dominio_generico(remitente),
        destinatario=None,
        cuenta_destino=cuenta_destino,
        fecha=fecha,
        moneda=moneda,
        monto=monto,
        concepto=_primer_grupo(_GEN_CONCEPTO, texto),
        referencia=referencia,
        comprobante=_primer_grupo(_GEN_COMPROBANTE, texto),
        confianza=_confianza(cuenta_destino, fecha, monto, referencia),
        confirmado=False,
    )


def _dominio_generico(remitente: str) -> str:
    """Saca el dominio de un remitente para usarlo como nombre de banco -no hay
    un nombre curado para un banco que todavía no tiene lector propio."""
    coincidencia = _GEN_DOMINIO.search(remitente)
    return coincidencia.group(1).lower() if coincidencia else remitente.lower()


def _primera_fecha_generica(texto: str) -> datetime | None:
    """`15/03/2026` -> datetime a medianoche. Sin hora: su formato varía demasiado
    entre bancos como para adivinarla, y agrupar por mes no la necesita."""
    coincidencia = _GEN_FECHA.search(texto)
    if coincidencia is None:
        return None
    dia, mes, anio_str = coincidencia.group(1).split("/")
    anio = int(anio_str) if len(anio_str) == 4 else 2000 + int(anio_str)
    try:
        return datetime(anio, int(mes), int(dia))
    except ValueError:
        return None


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


def _leer_monto(
    patron: re.Pattern[str], texto: str, monedas: dict[str, str] = _MONEDAS
) -> tuple[str | None, Decimal | None]:
    """`25,500.00 Colones` -> moneda ISO y monto exacto.

    La coma separa miles y el punto separa decimales, igual que en
    `comprobante_bac.py`. SINPE solo mueve colones en Costa Rica -"Dolares" se
    soporta por si acaso, pero ninguna de las dos muestras reales lo usa.
    """
    coincidencia = patron.search(texto)
    if coincidencia is None:
        return None, None
    moneda = monedas.get(coincidencia.group(2).lower())
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
