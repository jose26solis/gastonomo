"""El lector de transferencias SINPE, probado contra dos notificaciones reales anonimizadas."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.business.parsers.transferencia_sinpe import parsear_transferencia_sinpe

MUESTRAS = Path(__file__).parent / "fixtures"


@pytest.fixture
def sinpe_bncr() -> str:
    return (MUESTRAS / "sinpe_bncr_dtr.txt").read_text(encoding="utf-8")


@pytest.fixture
def sinpe_bac() -> str:
    return (MUESTRAS / "sinpe_bac_recibida.txt").read_text(encoding="utf-8")


def test_lee_los_campos_de_una_transferencia_del_banco_nacional(sinpe_bncr: str) -> None:
    resultado = parsear_transferencia_sinpe("bncontacto@bncr.fi.cr", sinpe_bncr)

    assert resultado is not None
    assert resultado.banco == "Banco Nacional"
    assert resultado.destinatario == "PERSONA DE PRUEBA"
    assert resultado.cuenta_destino == "CR21015112345678901234"
    assert resultado.fecha == datetime(2026, 3, 15, 9, 12, 45)
    assert resultado.moneda == "CRC"
    assert resultado.monto == Decimal("25500.00")
    assert resultado.concepto == "Pago de prueba"
    assert resultado.referencia == "2026031509124540404011122"
    assert resultado.comprobante == "40404040"
    assert resultado.confianza == 1.0
    assert resultado.es_confiable is True


def test_lee_los_campos_de_una_transferencia_de_bac(sinpe_bac: str) -> None:
    resultado = parsear_transferencia_sinpe("notificaciones@baccredomatic.cr", sinpe_bac)

    assert resultado is not None
    assert resultado.banco == "BAC Credomatic"
    assert resultado.destinatario == "PERSONA DE PRUEBA"
    assert resultado.cuenta_destino == "CR2101XXXXXXXXXXXX9988"
    assert resultado.fecha == datetime(2026, 3, 15, 9, 15, 30)
    assert resultado.moneda == "CRC"
    assert resultado.monto == Decimal("15000.00")
    assert resultado.concepto == "Pago de prueba"
    assert resultado.referencia == "2026031509887766554433221"
    assert resultado.comprobante is None, (
        "BAC no manda un numero de comprobante aparte del de referencia"
    )
    assert resultado.confianza == 1.0


def test_el_monto_es_decimal_exacto(sinpe_bncr: str) -> None:
    """Con punto flotante el reporte no cuadra por centimos, igual que en comprobante_bac.py."""
    resultado = parsear_transferencia_sinpe("bncontacto@bncr.fi.cr", sinpe_bncr)

    assert resultado is not None
    assert isinstance(resultado.monto, Decimal)
    assert resultado.monto * 2 == Decimal("51000.00")


def test_un_remitente_de_un_banco_no_soportado_no_se_intenta_leer() -> None:
    """Un candidato de `detectar_bancos` sin lector todavia: no hay que adivinarle el formato."""
    resultado = parsear_transferencia_sinpe(
        "info@promerica.fi.cr", "Su transferencia SINPE fue procesada."
    )

    assert resultado is None


def test_el_concepto_de_bac_no_arrastra_los_guiones_de_relleno(sinpe_bac: str) -> None:
    """La plantilla de BAC rellena el resto de la linea con guiones bajos cuando el
    concepto es corto -ver fixtures/LEEME.md. El campo no debe incluirlos."""
    resultado = parsear_transferencia_sinpe("notificaciones@baccredomatic.cr", sinpe_bac)

    assert resultado is not None
    assert "_" not in resultado.concepto


def test_una_transferencia_incompleta_baja_la_confianza_en_vez_de_reventar() -> None:
    resultado = parsear_transferencia_sinpe(
        "bncontacto@bncr.fi.cr", "Estimado(a): ALGUIEN\nSin el resto de los campos."
    )

    assert resultado is not None
    assert resultado.cuenta_destino is None
    assert resultado.monto is None
    assert resultado.confianza == 0.0
    assert resultado.es_confiable is False


def test_un_texto_que_no_es_una_transferencia_no_extrae_nada() -> None:
    resultado = parsear_transferencia_sinpe(
        "bncontacto@bncr.fi.cr", "Buenos dias, recuerde su cita."
    )

    assert resultado is not None
    assert resultado.confianza == 0.0
    assert resultado.destinatario is None
