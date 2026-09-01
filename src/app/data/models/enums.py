"""Enumeraciones del dominio.

Solo estan las que usan las entidades implementadas en el Laboratorio 1. Las
demas (estado de compra, tipo de metodo de pago, estado de comprobante) entran
cuando entren sus entidades.
"""

from enum import StrEnum


class Moneda(StrEnum):
    """Monedas que el sistema reconoce. La base de calculo es el colon."""

    CRC = "CRC"
    USD = "USD"
    EUR = "EUR"


class ProveedorCorreo(StrEnum):
    """Buzones que el sistema sabe vincular y leer."""

    OUTLOOK = "OUTLOOK"
    GMAIL = "GMAIL"


class EstadoCuentaCorreo(StrEnum):
    """Ciclo de vida de un buzón vinculado."""

    ACTIVA = "ACTIVA"
    TOKEN_EXPIRADO = "TOKEN_EXPIRADO"
    DESVINCULADA = "DESVINCULADA"
    ERROR = "ERROR"


class EstadoPresupuesto(StrEnum):
    """Dónde va el gasto de una categoría respecto a su límite del mes.

    No se persiste: se calcula cada vez, comparando el límite guardado contra
    el consumo real del período. Ver `PresupuestoService.calcular_estado`.
    """

    EN_RANGO = "EN_RANGO"
    CERCA_DEL_LIMITE = "CERCA_DEL_LIMITE"
    EXCEDIDO = "EXCEDIDO"
