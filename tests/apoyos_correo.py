"""Doble de prueba de un `ProveedorDeCorreo`, compartido entre pruebas.

No es un archivo `test_*.py` a propósito: pytest no debe intentar coleccionarlo
como una suite, es solo una pieza que las suites importan.
"""

from datetime import UTC, datetime, timedelta

from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo


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

    def listar_mensajes_recientes(self, token_acceso: str, limite: int) -> list[MensajeResumido]:
        return [
            MensajeResumido(
                identificador="1",
                remitente="NotificacionBAC@baccredomatic.cr",
                asunto="Notificacion de transaccion",
                recibido_en=datetime.now(UTC),
            )
        ]
