"""Contrato común a los proveedores de correo (Outlook, Gmail).

`CategoriaService` no sabe qué es HTTP; los proveedores de correo sí, porque
hablar con Microsoft y con Google es exactamente su trabajo. Lo que evita que
esa dependencia externa se filtre hacia arriba es que `CuentaCorreoService`
solo conoce esta interfaz, nunca `httpx` ni la forma de la respuesta de cada
API. Cambiar de librería HTTP, o agregar un tercer proveedor, no debería tocar
una sola línea del servicio de negocio.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class TokensDeCorreo:
    """Lo que un proveedor entrega tras autenticar: acceso, refresco y vigencia."""

    token_acceso: str
    token_refresco: str | None
    expira_en: datetime


@dataclass(frozen=True)
class MensajeResumido:
    """Metadatos mínimos de un mensaje, para probar la conexión sin leer el cuerpo."""

    identificador: str
    remitente: str
    asunto: str
    recibido_en: datetime | None


class ProveedorDeCorreo(Protocol):
    """Lo que `CuentaCorreoService` necesita de cualquier proveedor de correo."""

    def url_de_autorizacion(self, estado: str) -> str:
        """Arma la URL a la que se redirige al titular para que autorice el acceso."""
        ...

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        """Cambia el código de autorización que devolvió el proveedor por tokens."""
        ...

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        """Pide un token de acceso nuevo usando el token de refresco vigente."""
        ...

    def obtener_direccion(self, token_acceso: str) -> str:
        """Resuelve la dirección del buzón que autorizó, para identificar la cuenta."""
        ...

    def listar_mensajes_recientes(
        self, token_acceso: str, limite: int, remitente_contiene: str | None = None
    ) -> list[MensajeResumido]:
        """Trae los mensajes más recientes, opcionalmente solo de un remitente.

        `remitente_contiene` filtra por una subcadena de la dirección del
        remitente (por ejemplo `"baccredomatic.cr"`). Sin ese filtro, trae
        cualquier mensaje reciente; con él, ninguno que no coincida.
        """
        ...

    def obtener_cuerpo_de_mensaje(self, token_acceso: str, identificador: str) -> str:
        """Trae el cuerpo de un mensaje como texto plano, listo para parsear.

        Nunca HTML: cada proveedor es responsable de pedirlo o convertirlo a
        texto plano de su lado, para que `comprobante_bac.py` -que espera
        líneas `Etiqueta: valor`- nunca tenga que lidiar con etiquetas HTML.
        """
        ...
