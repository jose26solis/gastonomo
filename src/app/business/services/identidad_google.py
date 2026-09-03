"""OAuth2 de Google, pero para autenticación -no para leer correo.

Deliberadamente aparte de `correo/gmail.py`: ese archivo implementa
`ProveedorDeCorreo` (listar mensajes, leer el cuerpo de uno) para vincular un
buzón que se va a sincronizar. "Iniciar sesión con Google" no necesita nada
de eso -ni falta que le siga vigente el token después del login- así que
forzarlo dentro de esa interfaz sería una abstracción que no calza. Lo que sí
comparten es el cliente HTTP, las credenciales (mismo Client ID/Secret,
`google_client_id`/`google_client_secret`) y el patrón de "hablar el
protocolo a mano en vez de traer un SDK", porque acá también son cuatro
peticiones simples.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.business.errors import ErrorDeProveedorExterno
from app.config.settings import Configuracion

# Solo identidad, nunca gmail.readonly: pedir un alcance más amplio del que
# se necesita es exactamente lo que un titular no puede verificar con solo
# mirar la pantalla de consentimiento, y es más superficie para revisar en
# la verificación de OAuth de Google.
_ALCANCES = "openid email profile"


@dataclass(frozen=True)
class PerfilDeGoogle:
    """Lo que Google confirma sobre quién acaba de autorizar."""

    id: str
    correo: str
    correo_verificado: bool
    nombre: str


class IdentidadGoogleProveedor:
    """Intercambia un código de autorización de Google por el perfil de quien autorizó."""

    def __init__(self, cliente: httpx.Client, configuracion: Configuracion) -> None:
        self._cliente = cliente
        self._client_id = configuracion.google_client_id
        self._client_secret = configuracion.google_client_secret
        self._redirect_uri = configuracion.google_login_redirect_uri

    def url_de_autorizacion(self, estado: str) -> str:
        parametros = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "scope": _ALCANCES,
            "state": estado,
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(parametros)}"

    def perfil_desde_codigo(self, codigo: str) -> PerfilDeGoogle:
        """Cambia el código por un token de acceso y trae el perfil en la misma llamada.

        A diferencia de vincular un buzón, acá no hace falta guardar ningún
        token -el de acceso se usa una sola vez, para esta consulta, y se
        descarta. No se pide `access_type=offline` ni `prompt=consent`
        -eso es para conseguir un refresh_token que sobreviva, y esta
        integración no vuelve a hablar con Google después de este momento.
        """
        respuesta_token = self._cliente.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": codigo,
                "redirect_uri": self._redirect_uri,
            },
        )
        cuerpo_token = self._cuerpo_o_error(respuesta_token, "intercambiando el código con Google")
        token_acceso = cuerpo_token.get("access_token")
        if not token_acceso:
            raise ErrorDeProveedorExterno("Google no devolvió un token de acceso.")

        respuesta_perfil = self._cliente.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_acceso}"},
        )
        cuerpo_perfil = self._cuerpo_o_error(respuesta_perfil, "consultando el perfil de Google")
        try:
            return PerfilDeGoogle(
                id=cuerpo_perfil["id"],
                correo=cuerpo_perfil["email"],
                correo_verificado=bool(cuerpo_perfil.get("verified_email", False)),
                nombre=cuerpo_perfil.get("name") or cuerpo_perfil["email"],
            )
        except KeyError as error:
            raise ErrorDeProveedorExterno(
                "Google devolvió un perfil sin los campos esperados."
            ) from error

    def _cuerpo_o_error(self, respuesta: httpx.Response, contexto: str) -> dict:
        if respuesta.status_code >= 400:
            raise ErrorDeProveedorExterno(
                f"Google rechazó la solicitud {contexto} "
                f"(HTTP {respuesta.status_code}): {respuesta.text[:300]}"
            )
        return respuesta.json()
