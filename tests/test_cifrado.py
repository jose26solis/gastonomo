"""Cifrado de los tokens de correo antes de guardarlos."""

import time

import pytest

from app.business.seguridad.cifrado import TokenIlegible, cifrar, descifrar


def test_cifrar_y_descifrar_recupera_el_valor_original() -> None:
    original = "un-token-de-acceso-cualquiera"

    cifrado = cifrar(original)

    assert cifrado != original, "el valor cifrado nunca debe coincidir con el original"
    assert descifrar(cifrado) == original


def test_dos_cifrados_del_mismo_valor_no_son_iguales() -> None:
    """Fernet agrega un vector de inicialización aleatorio: cifrar dos veces el
    mismo token no debe dejar un patrón reconocible en la base de datos."""
    primero = cifrar("mismo-token")
    segundo = cifrar("mismo-token")

    assert primero != segundo
    assert descifrar(primero) == descifrar(segundo) == "mismo-token"


def test_sin_ttl_un_valor_cifrado_hace_tiempo_sigue_siendo_valido() -> None:
    """Los tokens de acceso guardados no caducan solos: los vence Microsoft o Google."""
    cifrado = cifrar("token-de-acceso")
    time.sleep(1.1)

    assert descifrar(cifrado) == "token-de-acceso"


def test_con_ttl_un_valor_vencido_se_rechaza() -> None:
    """Regresión: el `state` del handshake de OAuth2 sí debe tener vida corta.

    Sin un `ttl`, Fernet no impone ningún límite de tiempo por sí solo -un
    `state` interceptado seguiría siendo válido para siempre mientras la
    clave de cifrado no cambiara.
    """
    cifrado = cifrar("state-del-handshake")
    time.sleep(2.5)

    with pytest.raises(TokenIlegible):
        descifrar(cifrado, ttl_segundos=1)


def test_con_ttl_un_valor_reciente_sigue_siendo_valido() -> None:
    cifrado = cifrar("state-del-handshake")

    assert descifrar(cifrado, ttl_segundos=600) == "state-del-handshake"
