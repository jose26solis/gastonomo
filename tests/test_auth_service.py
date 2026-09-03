"""El servicio de registro e inicio de sesión."""

import json
import time

import pytest
from sqlalchemy.orm import Session

from app.business.errors import CredencialesInvalidas, DatosInvalidos, ReglaDeNegocioViolada
from app.business.seguridad.cifrado import cifrar
from app.business.services.auth_service import (
    AuthService,
    IniciarSesionComando,
    RegistrarUsuarioComando,
    Sesion,
)
from app.data.models.usuario import Usuario
from app.data.repositories.usuario_repository import UsuarioRepository
from app.presentation.routers.cuentas_correo import _decodificar_estado


@pytest.fixture
def servicio(sesion: Session) -> AuthService:
    return AuthService(UsuarioRepository(sesion))


def _registrar(servicio: AuthService, correo: str = "ana@ejemplo.cr") -> Sesion:
    return servicio.registrar(
        RegistrarUsuarioComando(
            nombre_completo="Ana Pérez", correo=correo, contrasena="contrasena-segura"
        )
    )


def test_registrar_crea_la_cuenta_y_devuelve_una_sesion_ya_iniciada(
    servicio: AuthService,
) -> None:
    sesion = _registrar(servicio)

    assert sesion.usuario.id is not None
    assert sesion.usuario.nombre_completo == "Ana Pérez"
    assert sesion.usuario.correo == "ana@ejemplo.cr"
    assert sesion.token
    # La contraseña nunca se guarda en claro, ni siquiera reconocible dentro
    # del hash: es lo único que de verdad importa de esta prueba.
    assert "contrasena-segura" not in sesion.usuario.contrasena_hash


def test_registrar_normaliza_el_correo_a_minusculas(servicio: AuthService) -> None:
    sesion = servicio.registrar(
        RegistrarUsuarioComando(
            nombre_completo="Ana Pérez", correo="  Ana@Ejemplo.CR  ", contrasena="contrasena-segura"
        )
    )

    assert sesion.usuario.correo == "ana@ejemplo.cr"


def test_registrar_dos_veces_el_mismo_correo_se_rechaza(servicio: AuthService) -> None:
    _registrar(servicio, correo="ana@ejemplo.cr")

    with pytest.raises(ReglaDeNegocioViolada):
        _registrar(servicio, correo="ANA@ejemplo.cr")  # mismo correo, otra capitalización


def test_registrar_con_contrasena_corta_se_rechaza(servicio: AuthService) -> None:
    with pytest.raises(DatosInvalidos):
        servicio.registrar(
            RegistrarUsuarioComando(
                nombre_completo="Ana Pérez", correo="ana@ejemplo.cr", contrasena="corta"
            )
        )


def test_registrar_con_correo_sin_arroba_se_rechaza(servicio: AuthService) -> None:
    with pytest.raises(DatosInvalidos):
        servicio.registrar(
            RegistrarUsuarioComando(
                nombre_completo="Ana Pérez",
                correo="no-es-un-correo",
                contrasena="contrasena-segura",
            )
        )


def test_iniciar_sesion_con_las_credenciales_correctas(servicio: AuthService) -> None:
    _registrar(servicio)

    sesion = servicio.iniciar_sesion(
        IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="contrasena-segura")
    )

    assert sesion.usuario.correo == "ana@ejemplo.cr"
    assert sesion.token


def test_iniciar_sesion_es_insensible_a_mayusculas_en_el_correo(servicio: AuthService) -> None:
    _registrar(servicio)

    sesion = servicio.iniciar_sesion(
        IniciarSesionComando(correo="ANA@Ejemplo.cr", contrasena="contrasena-segura")
    )

    assert sesion.usuario.correo == "ana@ejemplo.cr"


def test_iniciar_sesion_con_contrasena_incorrecta_da_credenciales_invalidas(
    servicio: AuthService,
) -> None:
    _registrar(servicio)

    with pytest.raises(CredencialesInvalidas):
        servicio.iniciar_sesion(
            IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="la-que-no-es")
        )


def test_iniciar_sesion_con_correo_que_no_existe_da_el_mismo_error_que_contrasena_incorrecta(
    servicio: AuthService,
) -> None:
    """El mismo tipo de error para las dos causas: distinguirlas le confirmaría a
    quien ataque que un correo puntual sí tiene cuenta en el sistema.
    """
    _registrar(servicio, correo="ana@ejemplo.cr")

    try:
        servicio.iniciar_sesion(
            IniciarSesionComando(correo="nadie@ejemplo.cr", contrasena="lo-que-sea")
        )
        pytest.fail("debía lanzar CredencialesInvalidas")
    except CredencialesInvalidas as error_correo_inexistente:
        mensaje_correo_inexistente = str(error_correo_inexistente)

    try:
        servicio.iniciar_sesion(
            IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="lo-que-sea")
        )
        pytest.fail("debía lanzar CredencialesInvalidas")
    except CredencialesInvalidas as error_contrasena_incorrecta:
        mensaje_contrasena_incorrecta = str(error_contrasena_incorrecta)

    assert mensaje_correo_inexistente == mensaje_contrasena_incorrecta


def test_usuario_de_token_resuelve_al_dueno_del_token(servicio: AuthService) -> None:
    sesion = _registrar(servicio)

    resuelto = servicio.usuario_de_token(sesion.token)

    assert resuelto.id == sesion.usuario.id


def test_usuario_de_token_con_un_token_ilegible_da_credenciales_invalidas(
    servicio: AuthService,
) -> None:
    with pytest.raises(CredencialesInvalidas):
        servicio.usuario_de_token("esto-no-es-un-token-valido")


def test_usuario_de_token_con_un_token_vencido_da_credenciales_invalidas(
    servicio: AuthService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No se espera un mes real -se baja el TTL a 1 segundo para la prueba.

    2.5s de espera, no 1.5s: Fernet marca el tiempo con resolución de un
    segundo entero, así que una diferencia real de 1.5s puede redondear a
    una diferencia de 1 -exactamente el TTL, que no es "mayor que" y no
    vence. Mismo ajuste que ya hizo falta para el TTL del `state` de OAuth2.
    """
    monkeypatch.setattr("app.business.services.auth_service._TTL_SESION_SEGUNDOS", 1)
    sesion = _registrar(servicio)

    time.sleep(2.5)

    with pytest.raises(CredencialesInvalidas):
        servicio.usuario_de_token(sesion.token)


def test_un_state_de_vinculacion_no_sirve_como_token_de_sesion(
    servicio: AuthService, usuario: Usuario
) -> None:
    """Fija la protección contra confusión de tokens: el `state` de OAuth2 y el
    token de sesión comparten clave de cifrado y forma de JSON -sin el campo
    `proposito` que cada uno agrega, uno serviría como el otro mientras no venciera.
    """
    state_de_vinculacion = cifrar(
        json.dumps({"usuario_id": usuario.id, "proposito": "vincular-correo"})
    )

    with pytest.raises(CredencialesInvalidas):
        servicio.usuario_de_token(state_de_vinculacion)


def test_un_token_de_sesion_no_sirve_como_state_de_vinculacion() -> None:
    """La otra dirección de la misma protección, vista desde cuentas_correo.py."""
    token_de_sesion = cifrar(json.dumps({"usuario_id": 1, "proposito": "sesion"}))

    with pytest.raises(DatosInvalidos):
        _decodificar_estado(token_de_sesion)


def test_usuario_de_token_de_un_usuario_desactivado_da_credenciales_invalidas(
    servicio: AuthService, sesion: Session
) -> None:
    resultado = _registrar(servicio)
    resultado.usuario.activo = False
    sesion.commit()

    with pytest.raises(CredencialesInvalidas):
        servicio.usuario_de_token(resultado.token)


def test_iniciar_sesion_de_un_usuario_desactivado_da_credenciales_invalidas(
    servicio: AuthService, sesion: Session
) -> None:
    resultado = _registrar(servicio)
    resultado.usuario.activo = False
    sesion.commit()

    with pytest.raises(CredencialesInvalidas):
        servicio.iniciar_sesion(
            IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="contrasena-segura")
        )
