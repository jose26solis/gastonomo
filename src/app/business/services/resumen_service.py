"""Suma comprobantes ya parseados, agrupados por año, mes y moneda.

No sabe leer correos ni hablar con ningún proveedor: recibe una lista de
`ComprobanteParseado` y hace la cuenta. Separarlo de `CuentaCorreoService`
-que sí sabe leer correos- deja esta parte, la que puede tener un error de
cálculo, probada sin necesidad de simular ningún proveedor.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.business.parsers.comprobante_bac import ComprobanteParseado


@dataclass(frozen=True)
class ResumenMensual:
    """Total de compras de un mes, en una moneda."""

    anio: int
    mes: int
    moneda: str
    total: Decimal
    cantidad_transacciones: int


@dataclass(frozen=True)
class ResumenFinanciero:
    """Lo que se pudo leer de la bandeja: los comprobantes y su suma por mes.

    Van juntos a propósito: cada comprobante cuesta una petición real al
    proveedor de correo, así que un resumen y la lista de movimientos que lo
    componen se calculan de una sola pasada, no de dos.
    """

    comprobantes: list[ComprobanteParseado]
    por_mes: list[ResumenMensual]


def agrupar_por_mes(comprobantes: list[ComprobanteParseado]) -> list[ResumenMensual]:
    """Suma los montos de compra por año, mes y moneda, del más reciente al más viejo.

    Descarta lo que no se puede sumar de forma honesta: comprobantes que no
    son una compra (una transferencia, por ejemplo), los que el parser no
    entendió con confianza (`es_confiable`), y los que -por lo que sea- no
    traen monto, fecha o moneda. Sumar un valor que no se está seguro de haber
    leído bien daría un total que parece preciso y no lo es.

    Las monedas nunca se mezclan en un mismo total: sin una tasa de cambio
    real, sumar colones y dólares directamente daría un número inventado.
    """
    acumulado: dict[tuple[int, int, str], tuple[Decimal, int]] = {}
    for comprobante in comprobantes:
        if not _es_sumable(comprobante):
            continue
        # Los tres campos ya se confirmaron no-None en _es_sumable; el tipo
        # de ComprobanteParseado los sigue marcando opcionales.
        assert comprobante.fecha is not None
        assert comprobante.moneda is not None
        assert comprobante.monto is not None

        clave = (comprobante.fecha.year, comprobante.fecha.month, comprobante.moneda)
        total_previo, cantidad_previa = acumulado.get(clave, (Decimal("0"), 0))
        acumulado[clave] = (total_previo + comprobante.monto, cantidad_previa + 1)

    resumen = [
        ResumenMensual(
            anio=anio, mes=mes, moneda=moneda, total=total, cantidad_transacciones=cantidad
        )
        for (anio, mes, moneda), (total, cantidad) in acumulado.items()
    ]
    resumen.sort(key=lambda r: (r.anio, r.mes, r.moneda), reverse=True)
    return resumen


def filtrar_del_periodo(
    comprobantes: list[ComprobanteParseado], anio: int, mes: int
) -> list[ComprobanteParseado]:
    """Deja solo los comprobantes de compra confiables de un año y mes puntual.

    Se usa antes de clasificar por comercio para calcular presupuestos: un
    presupuesto es de un período específico, así que lo que se compara contra
    su límite tiene que ser el gasto de ese mismo período, no el de toda la
    bandeja. Reutiliza el mismo criterio de "sumable" que `agrupar_por_mes`
    para no contar dos veces lo que ese total tampoco cuenta.
    """
    return [
        c
        for c in comprobantes
        if _es_sumable(c) and c.fecha is not None and c.fecha.year == anio and c.fecha.month == mes
    ]


def _es_sumable(comprobante: ComprobanteParseado) -> bool:
    return (
        comprobante.es_compra
        and comprobante.es_confiable
        and comprobante.monto is not None
        and comprobante.fecha is not None
        and comprobante.moneda is not None
    )
