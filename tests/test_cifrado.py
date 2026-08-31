"""Cifrado de los tokens de correo antes de guardarlos."""

from app.business.seguridad.cifrado import cifrar, descifrar


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
