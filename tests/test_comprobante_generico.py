"""El lector genérico de comprobantes de compra, para bancos sin lector exacto."""

from datetime import datetime
from decimal import Decimal

from app.business.parsers.comprobante_generico import parsear_comprobante_generico


def test_lee_los_campos_con_moneda_antes_del_monto() -> None:
    texto = (
        "Se ha realizado una compra con su tarjeta VISA terminada en 5566.\n"
        "Comercio: AUTOMERCADO ESCAZU\n"
        "Fecha: 05/09/2026 14:32\n"
        "Monto: CRC 15,420.50\n"
        "Autorizacion: 445566\n"
    )

    resultado = parsear_comprobante_generico("Banco Popular", texto)

    assert resultado.banco == "Banco Popular"
    assert resultado.comercio == "AUTOMERCADO ESCAZU"
    assert resultado.fecha == datetime(2026, 9, 5)
    assert resultado.marca_tarjeta == "VISA"
    assert resultado.ultimos_cuatro == "5566"
    assert resultado.autorizacion == "445566"
    assert resultado.moneda == "CRC"
    assert resultado.monto == Decimal("15420.50")
    assert resultado.tipo_transaccion == "COMPRA"
    assert resultado.es_compra is True


def test_lee_los_campos_con_moneda_despues_del_monto_y_simbolo_de_dolar() -> None:
    texto = (
        "Notificacion de compra\n"
        "Establecimiento: FARMACIA FISCHEL\n"
        "Tarjeta: **** 1234\n"
        "Total: $45.00\n"
    )

    resultado = parsear_comprobante_generico("Scotiabank", texto)

    assert resultado.comercio == "FARMACIA FISCHEL"
    assert resultado.ultimos_cuatro == "1234"
    assert resultado.moneda == "USD"
    assert resultado.monto == Decimal("45.00")


def test_un_monto_sin_separador_de_miles_no_pierde_el_primer_digito() -> None:
    """Bajo mil no siempre lleva coma -8500.00, no 8,500.00- y un separador
    exigido de más se comía el primer dígito. Ver la nota en `_NUMERO`."""
    resultado = parsear_comprobante_generico(
        "Davivienda", "Comercio: EPA SANTA ANA\nMonto: 8500.00 colones"
    )

    assert resultado.monto == Decimal("8500.00")
    assert resultado.moneda == "CRC"


def test_reconoce_la_tarjeta_marcada_como_terminada_en() -> None:
    resultado = parsear_comprobante_generico(
        "Banco de Costa Rica", "Comercio: EPA\nMonto: ₡5000.00\nTarjeta terminada en 9988"
    )

    assert resultado.ultimos_cuatro == "9988"


def test_lee_una_fecha_en_formato_texto_como_bac() -> None:
    resultado = parsear_comprobante_generico(
        "Davivienda", "Comercio: EPA SANTA ANA\nMonto: 8500.00 colones\nFecha: Sep 5, 2026"
    )

    assert resultado.fecha == datetime(2026, 9, 5)


def test_un_dia_mayor_a_doce_no_se_confunde_con_el_mes() -> None:
    """25/03/2026 no puede leerse como mes 25 -cae al segundo intento (mm/dd)
    solo cuando el primero no calza como fecha válida."""
    resultado = parsear_comprobante_generico(
        "Davivienda", "Comercio: EPA\nMonto: ₡100.00\n25/03/2026"
    )

    assert resultado.fecha == datetime(2026, 3, 25)


def test_un_texto_que_no_es_un_comprobante_no_extrae_nada() -> None:
    resultado = parsear_comprobante_generico("Banco X", "hola, como estas")

    assert resultado.comercio is None
    assert resultado.fecha is None
    assert resultado.ultimos_cuatro is None
    assert resultado.monto is None
    assert resultado.confianza == 0.0
    assert resultado.es_confiable is False
    # `tipo_transaccion` siempre queda COMPRA: es lo que el titular declara al
    # usar esta pantalla, no algo que dependa de haber encontrado el resto.
    assert resultado.tipo_transaccion == "COMPRA"


def test_un_comprobante_incompleto_baja_la_confianza_en_vez_de_reventar() -> None:
    resultado = parsear_comprobante_generico("Banco X", "Comercio: TIENDA X\nMonto: CRC 1,000.00")

    assert resultado.comercio == "TIENDA X"
    assert resultado.monto == Decimal("1000.00")
    assert resultado.fecha is None
    assert resultado.ultimos_cuatro is None
    assert resultado.confianza == 0.5
    assert resultado.es_confiable is False


def test_reconoce_establecimiento_como_sinonimo_de_comercio() -> None:
    resultado = parsear_comprobante_generico("Banco X", "Establecimiento: SODA LA ESQUINA")

    assert resultado.comercio == "SODA LA ESQUINA"


def test_un_numero_de_referencia_sin_moneda_reconocible_no_se_confunde_con_el_monto() -> None:
    """Un número con dos decimales que no lleva ninguna moneda reconocible -ni
    antes, ni después- no se toma como el monto: sería inventar la moneda."""
    resultado = parsear_comprobante_generico(
        "Banco X", "Comercio: TIENDA X\nReferencia: 12345.67\nNo hay monto en ningún lado."
    )

    assert resultado.monto is None
    assert resultado.moneda is None
