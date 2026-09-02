"""La API del tipo de cambio, incluida la traducción de errores de negocio a HTTP."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.tipo_cambio_service import TipoDeCambio
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_tipo_cambio


class _ServicioFalso:
    """Doble de prueba: no habla con el BCCR, devuelve o falla según se le pida."""

    def __init__(self, resultado: TipoDeCambio | None = None) -> None:
        self.resultado = resultado

    def obtener(self, fecha: date | None = None) -> TipoDeCambio:
        if self.resultado is None:
            raise ErrorDeProveedorExterno("El Banco Central no está configurado.")
        return self.resultado


@pytest.fixture
def cliente_sin_bccr(cliente: TestClient) -> TestClient:
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = lambda: _ServicioFalso(None)
    yield cliente
    del app.dependency_overrides[obtener_servicio_de_tipo_cambio]


@pytest.fixture
def cliente_con_bccr(cliente: TestClient) -> TestClient:
    resultado = TipoDeCambio(
        fecha=date(2026, 9, 2), compra=Decimal("520.50"), venta=Decimal("524.00")
    )
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = lambda: _ServicioFalso(resultado)
    yield cliente
    del app.dependency_overrides[obtener_servicio_de_tipo_cambio]


def test_devuelve_el_tipo_de_cambio(cliente_con_bccr: TestClient) -> None:
    respuesta = cliente_con_bccr.get("/api/tipo-cambio")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["fecha"] == "2026-09-02"
    assert cuerpo["compra"] == "520.50"
    assert cuerpo["venta"] == "524.00"


def test_sin_configurar_se_traduce_a_502(cliente_sin_bccr: TestClient) -> None:
    respuesta = cliente_sin_bccr.get("/api/tipo-cambio")

    assert respuesta.status_code == 502
