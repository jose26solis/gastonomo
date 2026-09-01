"""Suma y agrupación por mes, sin tocar red ni base de datos."""

from datetime import datetime
from decimal import Decimal

from app.business.parsers.comprobante_bac import ComprobanteParseado
from app.business.services.resumen_service import agrupar_por_mes


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
