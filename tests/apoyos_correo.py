"""Doble de prueba de un `ProveedorDeCorreo`, compartido entre pruebas.

No es un archivo `test_*.py` a propósito: pytest no debe intentar coleccionarlo
como una suite, es solo una pieza que las suites importan.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo

_CUERPOS_DE_MENSAJE = {
    "1": (Path(__file__).parent / "fixtures" / "comprobante_bac_compra.txt").read_text(
        encoding="utf-8"
    ),
    "2": "Aproveche nuestras ofertas de la semana en PriceSmart.",
    "4": (Path(__file__).parent / "fixtures" / "sinpe_bncr_dtr.txt").read_text(encoding="utf-8"),
    "5": (Path(__file__).parent / "fixtures" / "sinpe_bac_recibida.txt").read_text(
        encoding="utf-8"
    ),
}


class ProveedorDeCorreoFalso:
    """No toca la red: devuelve tokens y mensajes fijos, y recuerda qué le pidieron.

    Sirve para probar `CuentaCorreoService` y los endpoints de vinculación sin
    hablar con Microsoft ni con Google. Las pruebas contra el HTTP real de cada
    proveedor viven en `test_correo_outlook.py` y `test_correo_gmail.py`.
    """

    def __init__(self, direccion: str = "titular@ejemplo.cr") -> None:
        self.direccion = direccion
        self.codigo_recibido: str | None = None
        self.token_refrescado_con: str | None = None
        # Lo que sincronizar() no debe repetir en un segundo llamado: cada
        # identificador queda aquí la vez que de verdad se le pidió el cuerpo.
        self.cuerpos_leidos: list[str] = []

    def url_de_autorizacion(self, estado: str) -> str:
        return f"https://proveedor.falso/autorizar?state={estado}"

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        self.codigo_recibido = codigo
        return TokensDeCorreo(
            token_acceso="acceso-1",
            token_refresco="refresco-1",
            expira_en=datetime.now(UTC) + timedelta(hours=1),
        )

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        self.token_refrescado_con = token_refresco
        return TokensDeCorreo(
            token_acceso="acceso-2",
            token_refresco="refresco-2",
            expira_en=datetime.now(UTC) + timedelta(hours=1),
        )

    def obtener_direccion(self, token_acceso: str) -> str:
        return self.direccion

    def listar_mensajes_recientes(
        self, token_acceso: str, limite: int, remitente_contiene: str | None = None
    ) -> list[MensajeResumido]:
        """Simula una bandeja con un correo de BAC y uno que no lo es.

        El segundo mensaje existe para que las pruebas puedan comprobar que el
        filtro de remitente de verdad descarta lo que no coincide, no solo que
        el parametro se recibe.
        """
        mensajes = [
            MensajeResumido(
                identificador="1",
                remitente="NotificacionBAC@baccredomatic.cr",
                asunto="Notificacion de transaccion",
                recibido_en=datetime.now(UTC),
            ),
            MensajeResumido(
                identificador="2",
                remitente="promociones@pricesmart.com",
                asunto="Ofertas de la semana",
                recibido_en=datetime.now(UTC),
            ),
        ]
        if remitente_contiene:
            mensajes = [m for m in mensajes if remitente_contiene.lower() in m.remitente.lower()]
        return mensajes[:limite]

    def obtener_cuerpo_de_mensaje(self, token_acceso: str, identificador: str) -> str:
        if identificador not in _CUERPOS_DE_MENSAJE:
            raise ErrorDeProveedorExterno(f"Mensaje {identificador} inexistente en la prueba.")
        self.cuerpos_leidos.append(identificador)
        return _CUERPOS_DE_MENSAJE[identificador]

    def buscar_por_texto(self, token_acceso: str, texto: str, limite: int) -> list[MensajeResumido]:
        """Simula una búsqueda restringida al asunto: a diferencia del filtro por
        remitente, esta sí encuentra el mensaje que no es de BAC -es justo el caso
        que `detectar_bancos` necesita poder ver- pero solo si "banco" está en el
        asunto, igual que el proveedor real.
        """
        mensajes = [
            MensajeResumido(
                identificador="1",
                remitente="NotificacionBAC@baccredomatic.cr",
                asunto="Su banco le confirma una transaccion",
                recibido_en=datetime.now(UTC),
            ),
            MensajeResumido(
                identificador="2",
                remitente="promociones@pricesmart.com",
                asunto="Ofertas de la semana",
                recibido_en=datetime.now(UTC),
            ),
            MensajeResumido(
                identificador="3",
                remitente="avisos@bncr.fi.cr",
                asunto="Su banco le informa",
                recibido_en=datetime.now(UTC) - timedelta(days=1),
            ),
            # Los dos de abajo son para detectar_transferencias_sinpe: ninguno
            # contiene "banco" en el asunto, así que no afectan las pruebas de
            # detectar_bancos de más arriba.
            MensajeResumido(
                identificador="4",
                remitente="bncontacto@bncr.fi.cr",
                asunto="Transferencia SINPE DTR procesada satisfactoriamente",
                recibido_en=datetime.now(UTC) - timedelta(days=2),
            ),
            MensajeResumido(
                identificador="5",
                remitente="notificaciones@baccredomatic.cr",
                asunto="Notificación de Transferencia SINPE",
                recibido_en=datetime.now(UTC) - timedelta(hours=3),
            ),
        ]
        return [m for m in mensajes if texto.lower() in m.asunto.lower()][:limite]
