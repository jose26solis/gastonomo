"""Cifrado simétrico de los tokens de acceso a los buzones vinculados.

Un token de acceso a Gmail o a Outlook es, en la práctica, la llave de la
correspondencia de una persona. Guardarlo en claro en la base de datos
convertiría cualquier fuga de la base en una fuga de esos buzones. Se cifra con
Fernet (AES-128 en modo CBC más HMAC de autenticación) usando una única clave
simétrica que vive fuera del repositorio, en `GASTONOMO_CLAVE_CIFRADO_TOKENS`.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.business.errors import ErrorDeNegocio
from app.config.settings import obtener_configuracion


class TokenIlegible(ErrorDeNegocio):
    """El valor cifrado no se pudo descifrar con la clave actual.

    Pasa cuando la clave de cifrado cambió desde que se guardó el token (por
    ejemplo, una clave efímera de desarrollo que se regeneró al reiniciar). La
    cuenta de correo queda con tokens ilegibles y hay que volver a vincularla.
    """


@lru_cache
def _fernet() -> Fernet:
    return Fernet(obtener_configuracion().clave_cifrado_tokens.encode())


def cifrar(valor: str) -> str:
    """Cifra un valor en claro y lo devuelve como texto listo para guardar."""
    return _fernet().encrypt(valor.encode()).decode()


def descifrar(valor: str, ttl_segundos: int | None = None) -> str:
    """Descifra un valor guardado. Lanza `TokenIlegible` si la clave no calza o venció.

    `ttl_segundos` es opcional a propósito: los tokens de acceso guardados no
    tienen por qué caducar por sí solos -su vigencia la controla Microsoft o
    Google, no cuánto tiempo lleven cifrados en la base. El parámetro sí lo
    usa el `state` del handshake de OAuth2, que por diseño debe ser de corta
    vida (ver `cuentas_correo.py`): sin un `ttl`, Fernet no impone ningún
    límite de tiempo por sí solo, y un `state` interceptado seguiría siendo
    válido indefinidamente mientras la clave de cifrado no cambie.
    """
    try:
        return _fernet().decrypt(valor.encode(), ttl=ttl_segundos).decode()
    except InvalidToken as error:
        raise TokenIlegible(
            "El token no se pudo descifrar con la clave de cifrado actual, o venció."
        ) from error
