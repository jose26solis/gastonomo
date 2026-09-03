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

    def listar_mensajes_recientes(
        self, token_acceso: str, limite: int, remitente_contiene: str | None = None
    ) -> list[MensajeResumido]:
        # Con filtro se usa $search: filtra del lado del servidor sobre TODA
        # la bandeja, no solo los mensajes mas recientes. La alternativa de
        # pedir un lote de recientes y descartar en Python lo que no coincide
        # -lo que hacia esta funcion antes- se probo contra una bandeja real
        # con 105 correos de un remitente repartidos en mas de dos anios, y
        # solo alcanzaba los de la ultima semana: con tanto correo de otros
        # remitentes mezclado, ni 100 mensajes recientes cubren un mes.
        #
        # Graph exige el encabezado ConsistencyLevel para $search y no deja
        # combinarlo con $orderby -el orden por fecha se aplica despues, en
        # Python- por eso esta rama arma la peticion distinto a la que no
        # tiene filtro.
        encabezados = self._encabezado(token_acceso)
        parametros: dict[str, str | int] = {"$select": "id,subject,from,receivedDateTime"}
        if remitente_contiene:
            parametros["$search"] = f'"from:{remitente_contiene}"'
            parametros["$top"] = limite
            encabezados["ConsistencyLevel"] = "eventual"
        else:
            parametros["$top"] = limite
            parametros["$orderby"] = "receivedDateTime desc"

        respuesta = self._cliente.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers=encabezados,
            params=parametros,
        )
        cuerpo = self._cuerpo_o_error(respuesta, "listando mensajes de Outlook")
        mensajes = [self._mensaje_desde_json(mensaje) for mensaje in cuerpo.get("value", [])]
        if remitente_contiene:
            # $search es busqueda de texto, no una igualdad exacta; se
            # reconfirma en Python que el remitente de verdad coincide, y se
            # reordena por fecha porque Graph no deja pedir $orderby junto con
            # $search (devuelve por relevancia).
            mensajes = [m for m in mensajes if remitente_contiene.lower() in m.remitente.lower()]
            mensajes.sort(
                key=lambda m: m.recibido_en or datetime.min.replace(tzinfo=UTC), reverse=True
            )
        return mensajes[:limite]

    def buscar_por_texto(self, token_acceso: str, texto: str, limite: int) -> list[MensajeResumido]:
        """`subject:texto` restringe `$search` de Graph al asunto -sin el prefijo
        buscaría también remitente y cuerpo, y eso trae boletines y avisos que solo
        mencionan la palabra de pasada (ver la nota en `ProveedorDeCorreo.buscar_por_texto`).
        Sin reconfirmar nada del lado del cliente después: a diferencia de
        `listar_mensajes_recientes`, acá no hay una sola subcadena exacta que el texto
        tenga que cumplir.
        """
        encabezados = self._encabezado(token_acceso)
        encabezados["ConsistencyLevel"] = "eventual"
        respuesta = self._cliente.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers=encabezados,
            params={
                "$select": "id,subject,from,receivedDateTime",
                "$search": f'"subject:{texto}"',
                "$top": limite,
            },
        )
        cuerpo = self._cuerpo_o_error(respuesta, "buscando mensajes de Outlook")
        mensajes = [self._mensaje_desde_json(mensaje) for mensaje in cuerpo.get("value", [])]
        mensajes.sort(key=lambda m: m.recibido_en or datetime.min.replace(tzinfo=UTC), reverse=True)
        return mensajes[:limite]

    def obtener_cuerpo_de_mensaje(self, token_acceso: str, identificador: str) -> str:
        # El encabezado Prefer le pide a Graph que convierta el cuerpo a texto
        # plano de su lado. Sin él, "body.content" viene en HTML -BAC manda
        # sus notificaciones con una plantilla HTML- y comprobante_bac.py
        # espera lineas "Etiqueta: valor", no etiquetas <div>/<p>.
        encabezados = self._encabezado(token_acceso)
        encabezados["Prefer"] = 'outlook.body-content-type="text"'
        respuesta = self._cliente.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{identificador}",
            headers=encabezados,
            params={"$select": "body"},
        )
        cuerpo = self._cuerpo_o_error(respuesta, f"leyendo el mensaje {identificador} de Outlook")
        return cuerpo.get("body", {}).get("content", "")

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
