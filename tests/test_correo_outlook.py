"""El proveedor de Outlook, contra un Microsoft Graph simulado.

`httpx.MockTransport` intercepta la petición antes de que salga a la red: estas
pruebas verifican que el proveedor arma las peticiones correctas y traduce la
respuesta, sin depender de que Microsoft esté disponible.
"""

from datetime import UTC, datetime

import httpx
import pytest

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.correo.outlook import OutlookProveedor
from app.config.settings import Configuracion


def _configuracion() -> Configuracion:
    return Configuracion(
        nombre_aplicacion="Gastonomo",
        version="0.1.0",
        url_base_datos="sqlite://",
        microsoft_client_id="client-de-prueba",
        microsoft_client_secret="secreto-de-prueba",
        microsoft_tenant="consumers",
        microsoft_redirect_uri="http://localhost/api/cuentas-correo/outlook/callback",
        google_client_id="",
        google_client_secret="",
        google_redirect_uri="",
        clave_cifrado_tokens="clave-no-usada-en-estas-pruebas",
        origenes_permitidos=[],
    )


def _microsoft_simulado(peticion: httpx.Request) -> httpx.Response:
    if peticion.url.path.endswith("/oauth2/v2.0/token"):
        return httpx.Response(
            200,
            json={
                "access_token": "token-de-acceso",
                "refresh_token": "token-de-refresco",
                "expires_in": 3600,
            },
        )
    if peticion.url.path == "/v1.0/me":
        return httpx.Response(200, json={"mail": "titular@outlook.com"})
    if peticion.url.path == "/v1.0/me/messages":
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "abc123",
                        "subject": "Notificacion de transaccion WALMART",
                        "from": {"emailAddress": {"address": "NotificacionBAC@baccredomatic.cr"}},
                        "receivedDateTime": "2026-08-30T13:27:00Z",
                    },
                    {
                        "id": "xyz789",
                        "subject": "Ofertas de la semana",
                        "from": {"emailAddress": {"address": "promociones@pricesmart.com"}},
                        "receivedDateTime": "2026-08-30T10:00:00Z",
                    },
                ]
            },
        )
    if peticion.url.path == "/v1.0/me/messages/abc123":
        assert peticion.headers.get("Prefer") == 'outlook.body-content-type="text"'
        return httpx.Response(
            200, json={"body": {"contentType": "text", "content": "Comercio: WALMART\n"}}
        )
    raise AssertionError(f"peticion inesperada en la prueba: {peticion.method} {peticion.url}")


@pytest.fixture
def proveedor() -> OutlookProveedor:
    cliente = httpx.Client(transport=httpx.MockTransport(_microsoft_simulado))
    return OutlookProveedor(cliente, _configuracion())


def test_arma_la_url_de_autorizacion_con_los_alcances_correctos(
    proveedor: OutlookProveedor,
) -> None:
    url = proveedor.url_de_autorizacion("estado-de-prueba")

    assert url.startswith("https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?")
    assert "client_id=client-de-prueba" in url
    assert "state=estado-de-prueba" in url
    assert "offline_access" in url
    assert "Mail.Read" in url


def test_intercambia_el_codigo_por_tokens(proveedor: OutlookProveedor) -> None:
    tokens = proveedor.intercambiar_codigo("codigo-de-autorizacion")

    assert tokens.token_acceso == "token-de-acceso"
    assert tokens.token_refresco == "token-de-refresco"
    assert tokens.expira_en > datetime.now(UTC)


def test_refrescar_pide_un_token_nuevo(proveedor: OutlookProveedor) -> None:
    tokens = proveedor.refrescar("token-de-refresco-vigente")

    assert tokens.token_acceso == "token-de-acceso"


def test_obtiene_la_direccion_del_perfil(proveedor: OutlookProveedor) -> None:
    assert proveedor.obtener_direccion("token") == "titular@outlook.com"


def test_lista_los_mensajes_recientes_sin_filtro(proveedor: OutlookProveedor) -> None:
    mensajes = proveedor.listar_mensajes_recientes("token", limite=5)

    assert len(mensajes) == 2
    assert mensajes[0].identificador == "abc123"
    assert mensajes[0].remitente == "NotificacionBAC@baccredomatic.cr"
    assert mensajes[0].asunto == "Notificacion de transaccion WALMART"
    assert mensajes[0].recibido_en == datetime(2026, 8, 30, 13, 27, tzinfo=UTC)


def test_lista_solo_los_mensajes_del_remitente_filtrado(proveedor: OutlookProveedor) -> None:
    mensajes = proveedor.listar_mensajes_recientes(
        "token", limite=5, remitente_contiene="baccredomatic.cr"
    )

    assert len(mensajes) == 1
    assert mensajes[0].remitente == "NotificacionBAC@baccredomatic.cr"


def test_el_filtro_de_remitente_no_distingue_mayusculas(proveedor: OutlookProveedor) -> None:
    mensajes = proveedor.listar_mensajes_recientes(
        "token", limite=5, remitente_contiene="BACCREDOMATIC.CR"
    )

    assert len(mensajes) == 1


def test_el_limite_se_aplica_despues_de_filtrar(proveedor: OutlookProveedor) -> None:
    """Con limite=1 y filtro, debe devolver 1 mensaje de BAC, no el primero sin filtrar."""
    mensajes = proveedor.listar_mensajes_recientes(
        "token", limite=1, remitente_contiene="baccredomatic.cr"
    )

    assert len(mensajes) == 1
    assert mensajes[0].remitente == "NotificacionBAC@baccredomatic.cr"


def test_con_filtro_se_manda_search_y_consistency_level() -> None:
    """$search busca en toda la bandeja, no solo en los mensajes recientes.

    Probado contra una bandeja real con 105 correos de un mismo remitente
    repartidos en mas de dos anios: pedir un lote de recientes y filtrar en
    Python -lo que hacia esta funcion antes- solo alcanzaba a encontrar los
    de la ultima semana.
    """
    peticiones: list[httpx.Request] = []

    def espia(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return _microsoft_simulado(peticion)

    proveedor = OutlookProveedor(
        httpx.Client(transport=httpx.MockTransport(espia)), _configuracion()
    )
    proveedor.listar_mensajes_recientes("token", limite=5, remitente_contiene="baccredomatic.cr")

    peticion = next(p for p in peticiones if p.url.path == "/v1.0/me/messages")
    assert peticion.url.params.get("$search") == '"from:baccredomatic.cr"'
    assert peticion.headers.get("ConsistencyLevel") == "eventual"
    assert "$orderby" not in peticion.url.params, "Graph no deja combinar $search con $orderby"


def test_sin_filtro_no_se_manda_search_ni_consistency_level() -> None:
    peticiones: list[httpx.Request] = []

    def espia(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return _microsoft_simulado(peticion)

    proveedor = OutlookProveedor(
        httpx.Client(transport=httpx.MockTransport(espia)), _configuracion()
    )
    proveedor.listar_mensajes_recientes("token", limite=5)

    peticion = next(p for p in peticiones if p.url.path == "/v1.0/me/messages")
    assert "$search" not in peticion.url.params
    assert "ConsistencyLevel" not in peticion.headers
    assert peticion.url.params.get("$orderby") == "receivedDateTime desc"


def test_obtiene_el_cuerpo_del_mensaje_en_texto_plano(proveedor: OutlookProveedor) -> None:
    """El mock ya comprueba, dentro del handler, que viaja el header Prefer."""
    cuerpo = proveedor.obtener_cuerpo_de_mensaje("token", "abc123")

    assert cuerpo == "Comercio: WALMART\n"


def test_un_perfil_sin_correo_falla_explicitamente() -> None:
    def sin_correo(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    proveedor = OutlookProveedor(
        httpx.Client(transport=httpx.MockTransport(sin_correo)), _configuracion()
    )

    with pytest.raises(ErrorDeProveedorExterno):
        proveedor.obtener_direccion("token")


def test_un_rechazo_de_microsoft_se_traduce_a_error_de_proveedor_externo() -> None:
    def rechazo(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    proveedor = OutlookProveedor(
        httpx.Client(transport=httpx.MockTransport(rechazo)), _configuracion()
    )

    with pytest.raises(ErrorDeProveedorExterno):
        proveedor.intercambiar_codigo("codigo-vencido")
