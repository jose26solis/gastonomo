"""La API de registro e inicio de sesión, y la protección que añade al resto de la API."""

from fastapi.testclient import TestClient

from app.data.models.usuario import Usuario
from tests.conftest import CONTRASENA_DE_PRUEBA


def test_registro_devuelve_201_con_token_y_usuario(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/auth/registro",
        json={
            "nombre_completo": "Beto Solano",
            "correo": "beto@ejemplo.cr",
            "contrasena": "contrasena-segura",
        },
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["token"]
    assert cuerpo["usuario"]["correo"] == "beto@ejemplo.cr"
    assert cuerpo["usuario"]["nombre_completo"] == "Beto Solano"
    assert "contrasena" not in cuerpo["usuario"]
    assert "contrasena_hash" not in cuerpo["usuario"]


def test_registro_con_correo_repetido_se_traduce_a_409(
    cliente: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente.post(
        "/api/auth/registro",
        json={
            "nombre_completo": "Otra vez Ana",
            "correo": usuario.correo,
            "contrasena": "contrasena-segura",
        },
    )

    assert respuesta.status_code == 409


def test_registro_con_contrasena_corta_se_traduce_a_422(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/auth/registro",
        json={"nombre_completo": "Beto Solano", "correo": "beto@ejemplo.cr", "contrasena": "corta"},
    )

    assert respuesta.status_code == 422


def test_iniciar_sesion_con_las_credenciales_correctas(
    cliente: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente.post(
        "/api/auth/iniciar-sesion",
        json={"correo": usuario.correo, "contrasena": CONTRASENA_DE_PRUEBA},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token"]
    assert cuerpo["usuario"]["id"] == usuario.id


def test_iniciar_sesion_con_contrasena_incorrecta_se_traduce_a_401(
    cliente: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente.post(
        "/api/auth/iniciar-sesion",
        json={"correo": usuario.correo, "contrasena": "la-que-no-es"},
    )

    assert respuesta.status_code == 401


def test_yo_con_un_token_valido_devuelve_el_titular(cliente: TestClient, usuario: Usuario) -> None:
    """`cliente` ya trae un token válido por defecto (ver conftest.py)."""
    respuesta = cliente.get("/api/auth/yo")

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == usuario.id


def test_yo_sin_encabezado_de_autorizacion_se_traduce_a_401(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/auth/yo", headers={"Authorization": ""})

    assert respuesta.status_code == 401


def test_yo_con_un_token_ilegible_se_traduce_a_401(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/auth/yo", headers={"Authorization": "Bearer esto-no-es-un-token"})

    assert respuesta.status_code == 401


def test_un_endpoint_protegido_sin_sesion_se_traduce_a_401(
    cliente: TestClient, usuario: Usuario
) -> None:
    """Fija que la protección alcanzó de verdad a un endpoint existente, no solo a /auth."""
    respuesta = cliente.get(
        "/api/categorias", params={"usuario_id": usuario.id}, headers={"Authorization": ""}
    )

    assert respuesta.status_code == 401


def test_un_endpoint_protegido_con_la_sesion_de_otro_titular_se_traduce_a_403(
    cliente: TestClient, usuario: Usuario, sesion
) -> None:
    """`cliente` está autenticado como `usuario`; pedir los datos de otro id se rechaza
    aunque ese otro titular sí exista de verdad.
    """
    otro = Usuario(
        nombre_completo="Otra persona",
        correo="otra-persona-auth@gastonomo.cr",
        contrasena_hash="hash",
    )
    sesion.add(otro)
    sesion.commit()

    respuesta = cliente.get("/api/categorias", params={"usuario_id": otro.id})

    assert respuesta.status_code == 403
