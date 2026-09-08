"""La API de registro e inicio de sesión, y la protección que añade al resto de la API."""

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.business.services.auth_service import AuthService
from app.data.models.usuario import Usuario
from app.data.repositories.usuario_repository import UsuarioRepository
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_auth
from tests.apoyos_google import IdentidadGoogleFalsa
from tests.conftest import CONTRASENA_DE_PRUEBA


def _extraer_state(url_autorizacion: str) -> str:
    return parse_qs(urlparse(url_autorizacion).query)["state"][0]


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


def _con_google_falso(sesion) -> None:
    """Sustituye AuthService por uno con un doble de Google, sobre la misma sesión de la prueba."""

    def _armar() -> AuthService:
        return AuthService(UsuarioRepository(sesion), IdentidadGoogleFalsa())

    app.dependency_overrides[obtener_servicio_de_auth] = _armar


def test_login_con_google_de_punta_a_punta_crea_la_cuenta(cliente: TestClient, sesion) -> None:
    """`cliente` no importa para este flujo -las dos llamadas son públicas."""
    _con_google_falso(sesion)
    try:
        inicio = cliente.get("/api/auth/google/iniciar")
        assert inicio.status_code == 200
        estado = _extraer_state(inicio.json()["url_autorizacion"])

        respuesta = cliente.post(
            "/api/auth/google/callback", json={"codigo": "codigo-de-prueba", "estado": estado}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token"]
    assert cuerpo["usuario"]["correo"] == "ana@gmail.com"
    assert cuerpo["usuario"]["tiene_contrasena"] is False
    assert cuerpo["usuario"]["google_vinculado"] is True


def test_vincular_google_de_punta_a_punta_a_la_cuenta_logueada(
    cliente: TestClient, usuario: Usuario, sesion
) -> None:
    _con_google_falso(sesion)
    try:
        inicio = cliente.get("/api/auth/google/vincular/iniciar")
        assert inicio.status_code == 200
        estado = _extraer_state(inicio.json()["url_autorizacion"])

        respuesta = cliente.post(
            "/api/auth/google/vincular/callback", json={"codigo": "codigo", "estado": estado}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == usuario.id
    assert cuerpo["google_vinculado"] is True
    assert cuerpo["tiene_contrasena"] is True, "vincular Google no borra la contraseña existente"


def test_vincular_google_sin_sesion_iniciada_se_traduce_a_401(cliente: TestClient, sesion) -> None:
    _con_google_falso(sesion)
    try:
        respuesta = cliente.get("/api/auth/google/vincular/iniciar", headers={"Authorization": ""})
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert respuesta.status_code == 401


def test_desvincular_google_sin_contrasena_se_traduce_a_409(cliente: TestClient, sesion) -> None:
    _con_google_falso(sesion)
    try:
        estado = _extraer_state(cliente.get("/api/auth/google/iniciar").json()["url_autorizacion"])
        sesion_google = cliente.post(
            "/api/auth/google/callback", json={"codigo": "codigo", "estado": estado}
        ).json()

        respuesta = cliente.delete(
            "/api/auth/google/vincular",
            headers={"Authorization": f"Bearer {sesion_google['token']}"},
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert respuesta.status_code == 409


def test_cambiar_contrasena_con_la_actual_correcta(cliente: TestClient, usuario: Usuario) -> None:
    respuesta = cliente.post(
        "/api/auth/contrasena",
        json={"contrasena_actual": CONTRASENA_DE_PRUEBA, "contrasena_nueva": "otra-segura-123"},
    )

    assert respuesta.status_code == 200

    login = cliente.post(
        "/api/auth/iniciar-sesion",
        json={"correo": usuario.correo, "contrasena": "otra-segura-123"},
    )
    assert login.status_code == 200


def test_cambiar_contrasena_con_la_actual_incorrecta_se_traduce_a_401(
    cliente: TestClient,
) -> None:
    respuesta = cliente.post(
        "/api/auth/contrasena",
        json={"contrasena_actual": "la-que-no-es", "contrasena_nueva": "otra-segura-123"},
    )

    assert respuesta.status_code == 401


def test_preferencia_sinpe_es_falsa_por_default(cliente: TestClient) -> None:
    assert cliente.get("/api/auth/yo").json()["leer_transferencias_sinpe"] is False


def test_prender_la_preferencia_sinpe(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/auth/preferencias/sinpe", json={"activo": True})

    assert respuesta.status_code == 200
    assert respuesta.json()["leer_transferencias_sinpe"] is True
    assert cliente.get("/api/auth/yo").json()["leer_transferencias_sinpe"] is True


def test_apagar_la_preferencia_sinpe(cliente: TestClient) -> None:
    cliente.post("/api/auth/preferencias/sinpe", json={"activo": True})

    respuesta = cliente.post("/api/auth/preferencias/sinpe", json={"activo": False})

    assert respuesta.status_code == 200
    assert respuesta.json()["leer_transferencias_sinpe"] is False


# ---- Recuperar contraseña olvidada ----


def _con_correo_falso(sesion) -> list[tuple[str, str, str]]:
    """Sustituye AuthService por uno con un doble de correo saliente, sobre la
    misma sesión de la prueba -mismo patrón que `_con_google_falso`."""
    enviados: list[tuple[str, str, str]] = []

    class CorreoFalso:
        def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
            enviados.append((destinatario, asunto, cuerpo))

    def _armar() -> AuthService:
        return AuthService(UsuarioRepository(sesion), correo=CorreoFalso())

    app.dependency_overrides[obtener_servicio_de_auth] = _armar
    return enviados


def test_solicitar_recuperacion_da_200_con_el_mismo_mensaje_exista_o_no_la_cuenta(
    cliente: TestClient, usuario: Usuario, sesion
) -> None:
    _con_correo_falso(sesion)
    try:
        con_cuenta = cliente.post("/api/auth/recuperar/solicitar", json={"correo": usuario.correo})
        sin_cuenta = cliente.post(
            "/api/auth/recuperar/solicitar", json={"correo": "nadie@ejemplo.cr"}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert con_cuenta.status_code == 200
    assert sin_cuenta.status_code == 200
    assert con_cuenta.json() == sin_cuenta.json()


def test_recuperacion_de_punta_a_punta_deja_la_cuenta_con_la_contrasena_nueva(
    cliente: TestClient, usuario: Usuario, sesion
) -> None:
    enviados = _con_correo_falso(sesion)
    try:
        solicitud = cliente.post("/api/auth/recuperar/solicitar", json={"correo": usuario.correo})
        assert solicitud.status_code == 200
        token = enviados[0][2].split("token=")[1].split()[0]

        respuesta = cliente.post(
            "/api/auth/recuperar/confirmar",
            json={"token": token, "contrasena_nueva": "otra-segura-123"},
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_auth]

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token"]
    assert cuerpo["usuario"]["id"] == usuario.id

    login = cliente.post(
        "/api/auth/iniciar-sesion",
        json={"correo": usuario.correo, "contrasena": "otra-segura-123"},
    )
    assert login.status_code == 200


def test_confirmar_recuperacion_con_un_token_invalido_se_traduce_a_422(
    cliente: TestClient,
) -> None:
    respuesta = cliente.post(
        "/api/auth/recuperar/confirmar",
        json={"token": "esto-no-es-un-token-valido", "contrasena_nueva": "otra-segura-123"},
    )

    assert respuesta.status_code == 422
