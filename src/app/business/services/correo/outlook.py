"""Proveedor OAuth2 de Microsoft identity platform, para leer Outlook / Microsoft 365.

Habla HTTP directo contra los dos endpoints públicos de Microsoft en vez de usar
el SDK oficial (MSAL): son dos llamadas POST y tres GET, y traer una librería
completa de manejo de sesiones y caché de tokens para eso le agregaría una capa
de comportamiento implícito a un flujo que se entiende mejor leyendo las cuatro
peticiones tal cual viajan por la red.

Referencia: https://learn.microsoft.com/graph/auth-v2-user
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo
from app.config.settings import Configuracion

# offline_access es lo que hace que la respuesta traiga refresh_token; sin ese
# alcance, el usuario tendria que volver a autorizar cada vez que expire el
# token de acceso, que dura apenas una hora.
_ALCANCES = "offline_access Mail.Read User.Read"


class OutlookProveedor:
    """Implementa `ProveedorDeCorreo` contra Microsoft Graph."""

    def __init__(self, cliente: httpx.Client, configuracion: Configuracion) -> None:
        self._cliente = cliente
        self._client_id = configuracion.microsoft_client_id
        self._client_secret = configuracion.microsoft_client_secret
        self._redirect_uri = configuracion.microsoft_redirect_uri
        self._tenant = configuracion.microsoft_tenant

    def url_de_autorizacion(self, estado: str) -> str:
        parametros = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "response_mode": "query",
            "scope": _ALCANCES,
            "state": estado,
        }
        return f"{self._url_autorizar}?{urlencode(parametros)}"

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        respuesta = self._cliente.post(
            self._url_token,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": codigo,
                "redirect_uri": self._redirect_uri,
                "scope": _ALCANCES,
            },
        )
        return self._tokens_desde_respuesta(respuesta)

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        respuesta = self._cliente.post(
            self._url_token,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": token_refresco,
                "scope": _ALCANCES,
            },
        )
        return self._tokens_desde_respuesta(respuesta)

    def obtener_direccion(self, token_acceso: str) -> str:
        respuesta = self._cliente.get(
            "https://graph.microsoft.com/v1.0/me", headers=self._encabezado(token_acceso)
        )
        cuerpo = self._cuerpo_o_error(respuesta, "consultando el perfil de Microsoft Graph")
        # Una cuenta personal (outlook.com) no siempre trae "mail"; el nombre de
        # usuario principal es la direccion real en ese caso.
        direccion = cuerpo.get("mail") or cuerpo.get("userPrincipalName")
        if not direccion:
            raise ErrorDeProveedorExterno(
                "Microsoft Graph no devolvio una direccion de correo para esta cuenta."
            )
        return direccion

    def listar_mensajes_recientes(self, token_acceso: str, limite: int) -> list[MensajeResumido]:
        respuesta = self._cliente.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers=self._encabezado(token_acceso),
            params={
                "$top": limite,
                "$select": "id,subject,from,receivedDateTime",
                "$orderby": "receivedDateTime desc",
            },
        )
        cuerpo = self._cuerpo_o_error(respuesta, "listando mensajes de Outlook")
        return [self._mensaje_desde_json(mensaje) for mensaje in cuerpo.get("value", [])]

    @property
    def _url_autorizar(self) -> str:
        return f"https://login.microsoftonline.com/{self._tenant}/oauth2/v2.0/authorize"

    @property
    def _url_token(self) -> str:
        return f"https://login.microsoftonline.com/{self._tenant}/oauth2/v2.0/token"

    def _encabezado(self, token_acceso: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token_acceso}"}

    def _tokens_desde_respuesta(self, respuesta: httpx.Response) -> TokensDeCorreo:
        cuerpo = self._cuerpo_o_error(respuesta, "intercambiando el token con Microsoft")
        try:
            expira_en = datetime.now(UTC) + timedelta(seconds=int(cuerpo["expires_in"]))
            return TokensDeCorreo(
                token_acceso=cuerpo["access_token"],
                token_refresco=cuerpo.get("refresh_token"),
                expira_en=expira_en,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise ErrorDeProveedorExterno(
                "Microsoft devolvio una respuesta de token con forma inesperada."
            ) from error

    def _mensaje_desde_json(self, mensaje: dict) -> MensajeResumido:
        remitente = mensaje.get("from", {}).get("emailAddress", {}).get("address", "desconocido")
        recibido_en = None
        if valor := mensaje.get("receivedDateTime"):
            recibido_en = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return MensajeResumido(
            identificador=mensaje.get("id", ""),
            remitente=remitente,
            asunto=mensaje.get("subject") or "(sin asunto)",
            recibido_en=recibido_en,
        )

    def _cuerpo_o_error(self, respuesta: httpx.Response, contexto: str) -> dict:
        if respuesta.status_code >= 400:
            raise ErrorDeProveedorExterno(
                f"Microsoft rechazo la solicitud {contexto} "
                f"(HTTP {respuesta.status_code}): {respuesta.text[:300]}"
            )
        return respuesta.json()
