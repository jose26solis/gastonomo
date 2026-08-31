"""El proveedor de Gmail, contra una API de Google simulada."""

from datetime import UTC, datetime

import httpx
import pytest

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.correo.gmail import GmailProveedor
from app.config.settings import Configuracion


def _configuracion() -> Configuracion:
    return Configuracion(
        nombre_aplicacion="Gastonomo",
        version="0.1.0",
        url_base_datos="sqlite://",
        microsoft_client_id="",
        microsoft_client_secret="",
        microsoft_tenant="",
        microsoft_redirect_uri="",
        google_client_id="client-de-prueba",
        google_client_secret="secreto-de-prueba",
        google_redirect_uri="http://localhost/api/cuentas-correo/gmail/callback",
        clave_cifrado_tokens="clave-no-usada-en-estas-pruebas",
        origenes_permitidos=[],
    )


def _google_simulado(peticion: httpx.Request) -> httpx.Response:
    if peticion.url.path == "/token":
        return httpx.Response(
            200,
            json={
                "access_token": "token-de-acceso",
                "refresh_token": "token-de-refresco",
                "expires_in": 3600,
            },
        )
    if peticion.url.path == "/oauth2/v2/userinfo":
        return httpx.Response(200, json={"email": "titular@gmail.com"})
    if peticion.url.path == "/gmail/v1/users/me/messages":
        return httpx.Response(200, json={"messages": [{"id": "msg-1"}]})
    if peticion.url.path == "/gmail/v1/users/me/messages/msg-1":
        return httpx.Response(
            200,
            json={
                "internalDate": "1788182820000",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Notificacion de transaccion WALMART"},
                        {"name": "From", "value": "NotificacionBAC@baccredomatic.cr"},
                    ]
                },
            },
        )
    raise AssertionError(f"peticion inesperada en la prueba: {peticion.method} {peticion.url}")


@pytest.fixture
def proveedor() -> GmailProveedor:
    cliente = httpx.Client(transport=httpx.MockTransport(_google_simulado))
    return GmailProveedor(cliente, _configuracion())


def test_arma_la_url_de_autorizacion_pidiendo_acceso_fuera_de_linea(
    proveedor: GmailProveedor,
) -> None:
    url = proveedor.url_de_autorizacion("estado-de-prueba")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-de-prueba" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=estado-de-prueba" in url


def test_intercambia_el_codigo_por_tokens(proveedor: GmailProveedor) -> None:
    tokens = proveedor.intercambiar_codigo("codigo-de-autorizacion")

    assert tokens.token_acceso == "token-de-acceso"
    assert tokens.token_refresco == "token-de-refresco"
    assert tokens.expira_en > datetime.now(UTC)


def test_obtiene_la_direccion_del_perfil(proveedor: GmailProveedor) -> None:
    assert proveedor.obtener_direccion("token") == "titular@gmail.com"


def test_lista_los_mensajes_recientes_resolviendo_cada_uno(proveedor: GmailProveedor) -> None:
    mensajes = proveedor.listar_mensajes_recientes("token", limite=5)

    assert len(mensajes) == 1
    assert mensajes[0].identificador == "msg-1"
    assert mensajes[0].remitente == "NotificacionBAC@baccredomatic.cr"
    assert mensajes[0].asunto == "Notificacion de transaccion WALMART"
    assert mensajes[0].recibido_en is not None


def test_refrescar_conserva_el_token_de_refresco_si_google_no_lo_reenvia() -> None:
    """Google solo manda refresh_token la primera vez que se autoriza."""

    def sin_refresh_token(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "token-nuevo", "expires_in": 3600})

    proveedor = GmailProveedor(
        httpx.Client(transport=httpx.MockTransport(sin_refresh_token)), _configuracion()
    )

    tokens = proveedor.refrescar("token-de-refresco-original")

    assert tokens.token_acceso == "token-nuevo"
    assert tokens.token_refresco == "token-de-refresco-original"


def test_un_rechazo_de_google_se_traduce_a_error_de_proveedor_externo() -> None:
    def rechazo(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    proveedor = GmailProveedor(
        httpx.Client(transport=httpx.MockTransport(rechazo)), _configuracion()
    )

    with pytest.raises(ErrorDeProveedorExterno):
        proveedor.intercambiar_codigo("codigo-vencido")
