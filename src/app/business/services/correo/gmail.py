"""Proveedor OAuth2 de Google, para leer Gmail.

Mismo criterio que `outlook.py`: HTTP directo contra los endpoints publicos de
Google en vez del SDK, porque el flujo completo son cuatro peticiones simples.

Referencia: https://developers.google.com/identity/protocols/oauth2/web-server
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo
from app.config.settings import Configuracion

_ALCANCES = "https://www.googleapis.com/auth/gmail.readonly email"


class GmailProveedor:
    """Implementa `ProveedorDeCorreo` contra la API de Gmail."""

    def __init__(self, cliente: httpx.Client, configuracion: Configuracion) -> None:
        self._cliente = cliente
        self._client_id = configuracion.google_client_id
        self._client_secret = configuracion.google_client_secret
        self._redirect_uri = configuracion.google_redirect_uri

    def url_de_autorizacion(self, estado: str) -> str:
        parametros = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "scope": _ALCANCES,
            "state": estado,
            # access_type=offline es el equivalente de Google a offline_access de
            # Microsoft: sin el no llega refresh_token. prompt=consent fuerza a
            # que lo mande incluso si el titular ya autorizo antes -Google solo
            # entrega el refresh_token la primera vez que se autoriza.
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(parametros)}"

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        respuesta = self._cliente.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": codigo,
                "redirect_uri": self._redirect_uri,
            },
        )
        return self._tokens_desde_respuesta(respuesta)

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        respuesta = self._cliente.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": token_refresco,
            },
        )
        tokens = self._tokens_desde_respuesta(respuesta)
        # Google no reenvia el refresh_token al refrescar: el original sigue
        # vigente. Se conserva el que ya teniamos para que el llamador no se
        # quede sin uno.
        return TokensDeCorreo(
            token_acceso=tokens.token_acceso,
            token_refresco=tokens.token_refresco or token_refresco,
            expira_en=tokens.expira_en,
        )

    def obtener_direccion(self, token_acceso: str) -> str:
        respuesta = self._cliente.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers=self._encabezado(token_acceso),
        )
        cuerpo = self._cuerpo_o_error(respuesta, "consultando el perfil de Google")
        direccion = cuerpo.get("email")
        if not direccion:
            raise ErrorDeProveedorExterno("Google no devolvio una direccion de correo.")
        return direccion

    def listar_mensajes_recientes(self, token_acceso: str, limite: int) -> list[MensajeResumido]:
        """Trae los últimos mensajes.

        La API de Gmail entrega primero solo identificadores; el asunto y el
        remitente hay que pedirlos aparte por cada mensaje. Por eso esta llamada
        cuesta 1 + N peticiones y `limite` debe mantenerse chico -esto es para
        confirmar que el token funciona, no para sincronizar la bandeja.
        """
        listado = self._cliente.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers=self._encabezado(token_acceso),
            params={"maxResults": limite},
        )
        cuerpo = self._cuerpo_o_error(listado, "listando mensajes de Gmail")
        return [
            self._leer_mensaje(token_acceso, mensaje["id"])
            for mensaje in cuerpo.get("messages", [])
        ]

    def _leer_mensaje(self, token_acceso: str, identificador: str) -> MensajeResumido:
        respuesta = self._cliente.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{identificador}",
            headers=self._encabezado(token_acceso),
            params={"format": "metadata", "metadataHeaders": ["Subject", "From"]},
        )
        cuerpo = self._cuerpo_o_error(respuesta, "leyendo un mensaje de Gmail")
        encabezados = {
            encabezado["name"]: encabezado["value"]
            for encabezado in cuerpo.get("payload", {}).get("headers", [])
        }
        recibido_en = None
        if marca_de_tiempo := cuerpo.get("internalDate"):
            recibido_en = datetime.fromtimestamp(int(marca_de_tiempo) / 1000, tz=UTC)
        return MensajeResumido(
            identificador=identificador,
            remitente=encabezados.get("From", "desconocido"),
            asunto=encabezados.get("Subject") or "(sin asunto)",
            recibido_en=recibido_en,
        )

    def _encabezado(self, token_acceso: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token_acceso}"}

    def _tokens_desde_respuesta(self, respuesta: httpx.Response) -> TokensDeCorreo:
        cuerpo = self._cuerpo_o_error(respuesta, "intercambiando el token con Google")
        try:
            expira_en = datetime.now(UTC) + timedelta(seconds=int(cuerpo["expires_in"]))
            return TokensDeCorreo(
                token_acceso=cuerpo["access_token"],
                token_refresco=cuerpo.get("refresh_token"),
                expira_en=expira_en,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise ErrorDeProveedorExterno(
                "Google devolvio una respuesta de token con forma inesperada."
            ) from error

    def _cuerpo_o_error(self, respuesta: httpx.Response, contexto: str) -> dict:
        if respuesta.status_code >= 400:
            raise ErrorDeProveedorExterno(
                f"Google rechazo la solicitud {contexto} "
                f"(HTTP {respuesta.status_code}): {respuesta.text[:300]}"
            )
        return respuesta.json()
