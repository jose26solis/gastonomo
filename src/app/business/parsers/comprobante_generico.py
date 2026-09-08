"""Lector de comprobantes de compra de un banco sin lector exacto.

`comprobante_bac.py` lee un formato fijo ("Etiqueta: valor", una línea por
campo), comprobado contra una notificación real de BAC. Para cualquier otro
banco -mientras no exista una notificación real de ese banco para construirle
un lector propio- este archivo busca los mismos patrones que casi cualquier
notificación de compra en Costa Rica comparte: un comercio, un monto con su
moneda, una fecha, los últimos cuatro dígitos de la tarjeta. Es el mismo
criterio que ya usa `transferencia_sinpe.py` para un remitente sin lector
exacto: menos preciso que uno validado, así que nunca se hace pasar por uno.

A diferencia de la ingesta automática por correo, acá el titular pega el
texto a mano (pantalla "Cargar comprobante") y confirma o corrige el
resultado antes de que se convierta en una `Compra` real -por eso alcanza con
"lo mejor que se pueda", no hace falta acertar todo solo.
"""

import re
from datetime import datetime
from decimal import Decimal

from app.business.parsers.comprobante_bac import (
    CAMPOS_OBLIGATORIOS,
    ComprobanteParseado,
)

_COMERCIO = re.compile(
    r"^(?:Comercio|Establecimiento|Afiliado)[:\s]+(.+)$", re.MULTILINE | re.IGNORECASE
)

_TARJETA = re.compile(r"(AMEX|VISA|MASTERCARD|MASTER CARD)", re.IGNORECASE)
# Cubre "**** 4321", "XXXX4321", "terminada en 4321", "terminación 4321" -las
# formas más comunes en que una notificación enmascara la tarjeta sin decir
# "Comercio:" ni ningún otro rótulo fijo.
_ULTIMOS_CUATRO = re.compile(r"(?:[*xX]{2,}\s*|termina(?:da|ci.n)?\s+en\s+)(\d{4})\b")

_MONEDAS = {
    "colones": "CRC", "crc": "CRC", "₡": "CRC",
    "dolares": "USD", "dólares": "USD", "usd": "USD", "$": "USD",
    "euros": "EUR", "eur": "EUR", "€": "EUR",
}  # fmt: skip
# Dos decimales siempre, pero la parte entera admite dos formas: agrupada de a
# tres con separador ("15,420" / "1.234") o corrida sin ninguno ("8500") -un
# monto bajo mil no necesariamente lleva coma, y exigirla de más se comía el
# primer dígito (ver la nota de `_leer_monto`).
_NUMERO = r"\d{1,3}(?:[.,]\d{3})+[.,]\d{2}|\d+[.,]\d{2}"
# La moneda puede venir antes del monto, como código de tres letras o símbolo
# ("CRC 15,420.50", "$45.00") -formato típico de un rótulo tipo "Monto:"- o
# después, como palabra ("8500.00 colones") -formato típico en prosa. Se
# intenta primero la de antes; si no calza, la de después.
_MONTO_PREFIJO = re.compile(rf"(₡|\$|€|CRC|USD|EUR)\s*({_NUMERO})", re.IGNORECASE)
_MONTO_SUFIJO = re.compile(
    rf"({_NUMERO})\s*(colones|d.lares|dolares|euros|crc|usd|eur)", re.IGNORECASE
)

_MESES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}  # fmt: skip

# Dos formas de fecha nada más -numérica (la más común) y "Mon DD, YYYY" (la
# que usa BAC, por si el titular pega un comprobante de otro banco con un
# formato parecido). Cualquier otro formato queda para corregir a mano.
_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_FECHA_TEXTO = re.compile(r"\b([A-Za-z]{3})\w*\.?\s+(\d{1,2}),?\s+(\d{4})\b")

_AUTORIZACION = re.compile(r"Autorizaci.n[:\s]+(\w+)", re.IGNORECASE)
_REFERENCIA = re.compile(r"Referencia[:\s]+(\w+)", re.IGNORECASE)


def parsear_comprobante_generico(banco: str, texto: str) -> ComprobanteParseado:
    """Lee lo que se pueda de un comprobante de compra sin lector exacto.

    `banco` es el que escribió el titular en el formulario -no hay forma de
    adivinarlo del texto sin un remitente de correo real (acá no hay
    ninguno: el texto se pegó a mano). `tipo_transaccion` siempre queda
    "COMPRA": es justo lo que el titular está declarando al usar esta
    pantalla, no algo que haga falta leer del texto.
    """
    comercio = _primer_grupo(_COMERCIO, texto)
    fecha = _primera_fecha(texto)
    marca, ultimos_cuatro = _leer_tarjeta(texto)
    moneda, monto = _leer_monto(texto)

    campos = {
        "comercio": comercio,
        "fecha": fecha,
        "ultimos_cuatro": ultimos_cuatro,
        "monto": monto,
    }
    encontrados = sum(1 for nombre in CAMPOS_OBLIGATORIOS if campos[nombre] is not None)

    return ComprobanteParseado(
        banco=banco,
        comercio=comercio,
        ciudad=None,
        pais=None,
        fecha=fecha,
        marca_tarjeta=marca,
        ultimos_cuatro=ultimos_cuatro,
        autorizacion=_primer_grupo(_AUTORIZACION, texto),
        referencia=_primer_grupo(_REFERENCIA, texto),
        tipo_transaccion="COMPRA",
        moneda=moneda,
        monto=monto,
        confianza=encontrados / len(CAMPOS_OBLIGATORIOS),
    )


def _primer_grupo(patron: re.Pattern[str], texto: str) -> str | None:
    coincidencia = patron.search(texto)
    return coincidencia.group(1).strip() if coincidencia else None


def _leer_tarjeta(texto: str) -> tuple[str | None, str | None]:
    marca = _primer_grupo(_TARJETA, texto)
    ultimos_cuatro = _primer_grupo(_ULTIMOS_CUATRO, texto)
    return (marca.replace(" ", "").upper() if marca else None), ultimos_cuatro


def _leer_monto(texto: str) -> tuple[str | None, Decimal | None]:
    """`CRC 15,420.50`, `₡7,870.00` o `8500.00 colones` -> moneda ISO y monto exacto.

    A diferencia de `comprobante_bac.py`, acá no hay un rótulo "Monto:" fijo
    con el que anclarse, así que se acepta la moneda antes o después del
    número -ver `_MONTO_PREFIJO`/`_MONTO_SUFIJO`.
    """
    coincidencia = _MONTO_PREFIJO.search(texto)
    if coincidencia:
        clave, valor = coincidencia.groups()
    else:
        coincidencia = _MONTO_SUFIJO.search(texto)
        if coincidencia is None:
            return None, None
        valor, clave = coincidencia.groups()

    moneda = _MONEDAS.get(clave.lower())
    if moneda is None:
        return None, None
    try:
        return moneda, Decimal(valor.replace(",", ""))
    except ArithmeticError:
        return None, None


def _primera_fecha(texto: str) -> datetime | None:
    numerica = _FECHA_NUMERICA.search(texto)
    if numerica:
        primero, segundo, anio_str = numerica.groups()
        anio = int(anio_str) if len(anio_str) == 4 else 2000 + int(anio_str)
        # dd/mm es lo que usa Costa Rica -si el "mes" no calza como mes válido
        # (>12), se prueba mm/dd por si el comprobante vino en formato US.
        for dia_str, mes_str in ((primero, segundo), (segundo, primero)):
            try:
                return datetime(anio, int(mes_str), int(dia_str))
            except ValueError:
                continue

    texto_fecha = _FECHA_TEXTO.search(texto)
    if texto_fecha:
        mes_str, dia_str, anio_str = texto_fecha.groups()
        mes = _MESES.get(mes_str.upper())
        if mes is not None:
            try:
                return datetime(int(anio_str), mes, int(dia_str))
            except ValueError:
                return None

    return None
