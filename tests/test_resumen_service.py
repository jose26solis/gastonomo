"""Suma y agrupación por mes, sin tocar red ni base de datos."""

from datetime import datetime
from decimal import Decimal

from app.business.parsers.comprobante_bac import ComprobanteParseado
from app.business.services.resumen_service import (
    ResumenMensual,
    agrupar_por_mes,
    entrada_preferida_del_periodo,
    filtrar_del_periodo,
)


def _comprobante(
    fecha: datetime | None = datetime(2026, 8, 15),
    monto: Decimal | None = Decimal("100.00"),
    moneda: str | None = "CRC",
    tipo_transaccion: str | None = "COMPRA",
    confianza: float = 1.0,
) -> ComprobanteParseado:
    """Arma un comprobante de prueba con valores por defecto sumables."""
    return ComprobanteParseado(
        banco="BAC Credomatic",
        comercio="COMERCIO DE PRUEBA",
        ciudad=None,
        pais=None,
        fecha=fecha,
        marca_tarjeta="VISA",
        ultimos_cuatro="1234",
        autorizacion="1",
        referencia="1",
        tipo_transaccion=tipo_transaccion,
        moneda=moneda,
        monto=monto,
        confianza=confianza,
    )


def test_una_lista_vacia_no_produce_nada() -> None:
    assert agrupar_por_mes([]) == []


def test_suma_dos_compras_del_mismo_mes_y_moneda() -> None:
    comprobantes = [
        _comprobante(fecha=datetime(2026, 8, 5), monto=Decimal("100.00")),
        _comprobante(fecha=datetime(2026, 8, 20), monto=Decimal("50.50")),
    ]

    resumen = agrupar_por_mes(comprobantes)

    assert len(resumen) == 1
    assert resumen[0].anio == 2026
    assert resumen[0].mes == 8
    assert resumen[0].moneda == "CRC"
    assert resumen[0].total == Decimal("150.50")
    assert resumen[0].cantidad_transacciones == 2


def test_separa_meses_distintos() -> None:
    comprobantes = [
        _comprobante(fecha=datetime(2026, 7, 1), monto=Decimal("10.00")),
        _comprobante(fecha=datetime(2026, 8, 1), monto=Decimal("20.00")),
    ]

    resumen = agrupar_por_mes(comprobantes)

    assert len(resumen) == 2
    claves = {(r.anio, r.mes) for r in resumen}
    assert claves == {(2026, 7), (2026, 8)}


def test_no_mezcla_monedas_en_el_mismo_mes() -> None:
    comprobantes = [
        _comprobante(moneda="CRC", monto=Decimal("1000.00")),
        _comprobante(moneda="USD", monto=Decimal("15.00")),
    ]

    resumen = agrupar_por_mes(comprobantes)

    assert len(resumen) == 2
    por_moneda = {r.moneda: r.total for r in resumen}
    assert por_moneda == {"CRC": Decimal("1000.00"), "USD": Decimal("15.00")}


def test_descarta_lo_que_no_es_una_compra() -> None:
    """Una transferencia, por ejemplo, no debe sumarse como gasto."""
    comprobantes = [_comprobante(tipo_transaccion="TRANSFERENCIA")]

    assert agrupar_por_mes(comprobantes) == []


def test_descarta_lo_que_el_parser_no_entendio_con_confianza() -> None:
    comprobantes = [_comprobante(confianza=0.5)]

    assert agrupar_por_mes(comprobantes) == []


def test_descarta_comprobantes_sin_monto_fecha_o_moneda() -> None:
    comprobantes = [
        _comprobante(monto=None),
        _comprobante(fecha=None),
        _comprobante(moneda=None),
    ]

    assert agrupar_por_mes(comprobantes) == []


def test_el_orden_es_del_mes_mas_reciente_al_mas_viejo() -> None:
    comprobantes = [
        _comprobante(fecha=datetime(2026, 3, 1)),
        _comprobante(fecha=datetime(2026, 8, 1)),
        _comprobante(fecha=datetime(2026, 5, 1)),
    ]

    resumen = agrupar_por_mes(comprobantes)

    assert [(r.anio, r.mes) for r in resumen] == [(2026, 8), (2026, 5), (2026, 3)]


def test_la_suma_es_exacta_con_decimales() -> None:
    """Con punto flotante 0.1 + 0.2 no da 0.3; con Decimal, sí debe dar exacto."""
    comprobantes = [_comprobante(monto=Decimal("0.10")), _comprobante(monto=Decimal("0.20"))]

    resumen = agrupar_por_mes(comprobantes)

    assert resumen[0].total == Decimal("0.30")


def test_filtrar_del_periodo_deja_solo_el_mes_pedido() -> None:
    """Regresión: un presupuesto de setiembre no debe contar el gasto de agosto.

    Este es exactamente el bug reportado: el endpoint de presupuestos le pasaba
    la bandeja completa (todos los meses) a la clasificación por comercio, así
    que el `monto_consumido` de cualquier mes terminaba siendo el gasto de
    *toda* la historia en esa categoría, no el de ese mes puntual.
    """
    comprobantes = [
        _comprobante(fecha=datetime(2026, 8, 30), monto=Decimal("7870.00")),
        _comprobante(fecha=datetime(2026, 9, 5), monto=Decimal("1000.00")),
    ]

    del_agosto = filtrar_del_periodo(comprobantes, 2026, 8)
    del_setiembre = filtrar_del_periodo(comprobantes, 2026, 9)
    de_un_mes_sin_gasto = filtrar_del_periodo(comprobantes, 2026, 7)

    assert [c.monto for c in del_agosto] == [Decimal("7870.00")]
    assert [c.monto for c in del_setiembre] == [Decimal("1000.00")]
    assert de_un_mes_sin_gasto == []


def test_entrada_preferida_del_periodo_prefiere_crc_sobre_otras_monedas() -> None:
    """Regresión: por_mes ordena por (año, mes, moneda) -alfabético, USD antes que CRC.

    Una vista que solo puede mostrar una moneda a la vez (una tarjeta de KPI,
    un reporte de una página) no puede elegir "la primera fila" a ciegas.
    """
    por_mes = [
        ResumenMensual(
            anio=2026, mes=9, moneda="USD", total=Decimal("6.00"), cantidad_transacciones=2
        ),
        ResumenMensual(
            anio=2026, mes=9, moneda="CRC", total=Decimal("7600.00"), cantidad_transacciones=1
        ),
        ResumenMensual(
            anio=2026, mes=8, moneda="CRC", total=Decimal("50000.00"), cantidad_transacciones=10
        ),
    ]

    preferida = entrada_preferida_del_periodo(por_mes, 2026, 9)

    assert preferida is not None
    assert preferida.moneda == "CRC"
    assert preferida.total == Decimal("7600.00")


def test_entrada_preferida_del_periodo_cae_a_lo_que_haya_sin_crc() -> None:
    por_mes = [
        ResumenMensual(
            anio=2026, mes=9, moneda="USD", total=Decimal("6.00"), cantidad_transacciones=2
        )
    ]

    preferida = entrada_preferida_del_periodo(por_mes, 2026, 9)

    assert preferida is not None
    assert preferida.moneda == "USD"


def test_entrada_preferida_del_periodo_sin_datos_del_periodo_da_none() -> None:
    por_mes = [
        ResumenMensual(
            anio=2026, mes=8, moneda="CRC", total=Decimal("1.00"), cantidad_transacciones=1
        )
    ]

    assert entrada_preferida_del_periodo(por_mes, 2026, 9) is None


def test_filtrar_del_periodo_tambien_descarta_lo_no_sumable() -> None:
    """Mismo criterio que `agrupar_por_mes`: no compra, sin confianza o sin datos no cuenta."""
    comprobantes = [
        _comprobante(fecha=datetime(2026, 8, 1), tipo_transaccion="TRANSFERENCIA"),
        _comprobante(fecha=datetime(2026, 8, 1), confianza=0.5),
        _comprobante(fecha=datetime(2026, 8, 1), monto=None),
    ]

    assert filtrar_del_periodo(comprobantes, 2026, 8) == []
