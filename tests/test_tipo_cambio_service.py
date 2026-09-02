"""El servicio de tipo de cambio, contra un Banco Central simulado.

`httpx.MockTransport` intercepta la petición antes de que salga a la red -estas
pruebas no dependen de que el BCCR esté disponible, y no pueden probar el
contrato real del servicio (nombres exactos de parámetro del lado del BCCR):
solo que este código hace lo que se espera con lo que reciba.
"""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.tipo_cambio_service import TipoCambioService
from app.config.settings import Configuracion


def _configuracion(
    *, correo: str = "titular@ejemplo.cr", token: str = "token-de-prueba"
) -> Configuracion:
    return Configuracion(
        nombre_aplicacion="Gastonomo",
        version="0.1.0",
        url_base_datos="sqlite://",
        microsoft_client_id="",
        microsoft_client_secret="",
        microsoft_tenant="",
        microsoft_redirect_uri="",
        google_client_id="",
        google_client_secret="",
        google_redirect_uri="",
        clave_cifrado_tokens="clave-no-usada-en-estas-pruebas",
        origenes_permitidos=[],
        bccr_correo=correo,
        bccr_token=token,
    )


def _xml_de(*valores: str) -> str:
    filas = "".join(
        f"<INGC011_CAT_INDICADORECONOMIC><NUM_VALOR>{v}</NUM_VALOR></INGC011_CAT_INDICADORECONOMIC>"
        for v in valores
    )
    return f"<Datos_de_Indicador_Economico>{filas}</Datos_de_Indicador_Economico>"


def _bccr_simulado(peticion: httpx.Request) -> httpx.Response:
    indicador = peticion.url.params.get("tcIndicador")
    assert peticion.url.params.get("tcCorreo") == "titular@ejemplo.cr"
    assert peticion.url.params.get("tcToken") == "token-de-prueba"
    if indicador == "317":
        return httpx.Response(200, text=_xml_de("519.80", "520.50"))
    if indicador == "318":
        return httpx.Response(200, text=_xml_de("523.10", "524.00"))
    raise AssertionError(f"indicador inesperado en la prueba: {indicador}")


@pytest.fixture
def servicio() -> TipoCambioService:
    cliente = httpx.Client(transport=httpx.MockTransport(_bccr_simulado))
    return TipoCambioService(cliente, _configuracion())


def test_obtiene_compra_y_venta_y_se_queda_con_el_ultimo_valor_del_rango(
    servicio: TipoCambioService,
) -> None:
    """Del rango de _DIAS_DE_MARGEN días, el último valor es el más reciente."""
    tipo_de_cambio = servicio.obtener(date(2026, 9, 2))

    assert tipo_de_cambio.fecha == date(2026, 9, 2)
    assert tipo_de_cambio.compra == Decimal("520.50")
    assert tipo_de_cambio.venta == Decimal("524.00")


def test_una_segunda_llamada_a_la_misma_fecha_no_vuelve_a_tocar_la_red() -> None:
    peticiones: list[httpx.Request] = []

    def _contador(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        indicador = peticion.url.params.get("tcIndicador")
        return httpx.Response(200, text=_xml_de("520.50" if indicador == "317" else "524.00"))

    cliente = httpx.Client(transport=httpx.MockTransport(_contador))
    servicio = TipoCambioService(cliente, _configuracion())

    servicio.obtener(date(2026, 9, 2))
    servicio.obtener(date(2026, 9, 2))

    assert len(peticiones) == 2, "compra y venta se piden una vez cada una, no cuatro"


def test_sin_credenciales_configuradas_da_error_de_proveedor_externo() -> None:
    cliente = httpx.Client(transport=httpx.MockTransport(_bccr_simulado))
    servicio = TipoCambioService(cliente, _configuracion(correo="", token=""))

    assert servicio.configurado is False
    with pytest.raises(ErrorDeProveedorExterno):
        servicio.obtener()


def test_el_banco_central_rechaza_la_solicitud(servicio: TipoCambioService) -> None:
    def _rechazo(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    servicio._cliente = httpx.Client(transport=httpx.MockTransport(_rechazo))  # type: ignore[attr-defined]

    with pytest.raises(ErrorDeProveedorExterno):
        servicio.obtener(date(2026, 9, 2))


def test_una_respuesta_sin_ningun_valor_da_error_de_proveedor_externo() -> None:
    def _vacio(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<Datos_de_Indicador_Economico></Datos_de_Indicador_Economico>"
        )

    cliente = httpx.Client(transport=httpx.MockTransport(_vacio))
    servicio = TipoCambioService(cliente, _configuracion())

    with pytest.raises(ErrorDeProveedorExterno):
        servicio.obtener(date(2026, 9, 2))


def test_una_respuesta_que_no_es_xml_valido_da_error_de_proveedor_externo() -> None:
    def _basura(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="esto no es XML")

    cliente = httpx.Client(transport=httpx.MockTransport(_basura))
    servicio = TipoCambioService(cliente, _configuracion())

    with pytest.raises(ErrorDeProveedorExterno):
        servicio.obtener(date(2026, 9, 2))
