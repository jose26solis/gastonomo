"""El servicio de registro e inicio de sesión."""

import json
import time
from urllib.parse import parse_qs, urlparse

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
from app.business.services.identidad_google import PerfilDeGoogle
from app.data.models.usuario import Usuario
from app.data.repositories.usuario_repository import UsuarioRepository
from app.presentation.routers.cuentas_correo import _decodificar_estado
from tests.apoyos_google import IdentidadGoogleFalsa


@pytest.fixture
def servicio(sesion: Session) -> AuthService:
    return AuthService(UsuarioRepository(sesion))


@pytest.fixture
def google_falso() -> IdentidadGoogleFalsa:
    return IdentidadGoogleFalsa()


@pytest.fixture
def servicio_con_google(sesion: Session, google_falso: IdentidadGoogleFalsa) -> AuthService:
    return AuthService(UsuarioRepository(sesion), google_falso)


def _extraer_state(url_autorizacion: str) -> str:
    return parse_qs(urlparse(url_autorizacion).query)["state"][0]


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


# ---- Iniciar sesión con Google ----


def test_google_no_configurado_da_datos_invalidos(servicio: AuthService) -> None:
    """`servicio` (sin doble de Google) es justamente el caso "no configurado"."""
    with pytest.raises(DatosInvalidos):
        servicio.url_de_inicio_sesion_google()


def test_iniciar_sesion_con_google_crea_la_cuenta_la_primera_vez(
    servicio_con_google: AuthService,
) -> None:
    estado = _extraer_state(servicio_con_google.url_de_inicio_sesion_google())

    sesion = servicio_con_google.iniciar_sesion_con_google("codigo-de-google", estado)

    assert sesion.usuario.correo == "ana@gmail.com"
    assert sesion.usuario.google_id == "google-1"
    assert sesion.usuario.contrasena_hash is None, "una cuenta de solo Google no tiene contraseña"
    assert sesion.token


def test_iniciar_sesion_con_google_una_segunda_vez_entra_a_la_misma_cuenta(
    servicio_con_google: AuthService,
) -> None:
    estado_1 = _extraer_state(servicio_con_google.url_de_inicio_sesion_google())
    primera = servicio_con_google.iniciar_sesion_con_google("codigo-1", estado_1)

    estado_2 = _extraer_state(servicio_con_google.url_de_inicio_sesion_google())
    segunda = servicio_con_google.iniciar_sesion_con_google("codigo-2", estado_2)

    assert segunda.usuario.id == primera.usuario.id


def test_iniciar_sesion_con_google_con_correo_no_verificado_se_rechaza(
    sesion: Session,
) -> None:
    perfil = PerfilDeGoogle(
        id="google-2", correo="ana@gmail.com", correo_verificado=False, nombre="Ana"
    )
    servicio = AuthService(UsuarioRepository(sesion), IdentidadGoogleFalsa(perfil))
    estado = _extraer_state(servicio.url_de_inicio_sesion_google())

    with pytest.raises(DatosInvalidos):
        servicio.iniciar_sesion_con_google("codigo", estado)


def test_iniciar_sesion_con_google_no_linkea_solo_por_coincidir_el_correo(
    sesion: Session,
) -> None:
    """Ya existe una cuenta local con ese correo, pero sin vincular Google: no se
    inicia sesión en ella con solo tener el mismo correo en la cuenta de Google -eso
    sería dejar entrar a quien sea que controle esa cuenta de Google a una cuenta
    que otra persona ya protegió con una contraseña.
    """
    servicio = AuthService(UsuarioRepository(sesion))
    _registrar(servicio, correo="ana@gmail.com")

    perfil = PerfilDeGoogle(
        id="google-3", correo="ana@gmail.com", correo_verificado=True, nombre="Ana"
    )
    servicio_google = AuthService(UsuarioRepository(sesion), IdentidadGoogleFalsa(perfil))
    estado = _extraer_state(servicio_google.url_de_inicio_sesion_google())

    with pytest.raises(ReglaDeNegocioViolada, match="Ya existe una cuenta"):
        servicio_google.iniciar_sesion_con_google("codigo", estado)


def test_iniciar_sesion_con_google_con_un_state_de_otro_proposito_se_rechaza(
    servicio_con_google: AuthService,
) -> None:
    """Fija la protección contra confusión de tokens para este par de propósitos
    también -mismo motivo que ya se probó para sesión/vinculación de correo.
    """
    estado_de_vinculacion = cifrar(json.dumps({"proposito": "vincular-google", "usuario_id": 1}))

    with pytest.raises(DatosInvalidos):
        servicio_con_google.iniciar_sesion_con_google("codigo", estado_de_vinculacion)


# ---- Vincular / desvincular Google a una cuenta ya logueada ----


def test_vincular_google_agrega_el_metodo_de_acceso(
    servicio_con_google: AuthService,
) -> None:
    resultado = _registrar(servicio_con_google)
    assert resultado.usuario.google_id is None

    estado = _extraer_state(servicio_con_google.url_de_vinculacion_google(resultado.usuario.id))
    actualizado = servicio_con_google.vincular_google("codigo", estado)

    assert actualizado.google_id == "google-1"
    assert actualizado.contrasena_hash is not None, "vincular Google no borra la contraseña"


def test_vincular_una_cuenta_de_google_ya_vinculada_a_otro_titular_se_rechaza(
    sesion: Session, google_falso: IdentidadGoogleFalsa
) -> None:
    servicio = AuthService(UsuarioRepository(sesion), google_falso)
    dueno_original = _registrar(servicio, correo="dueno@ejemplo.cr").usuario
    estado_1 = _extraer_state(servicio.url_de_vinculacion_google(dueno_original.id))
    servicio.vincular_google("codigo-1", estado_1)

    otro_titular = _registrar(servicio, correo="otro@ejemplo.cr").usuario
    estado_2 = _extraer_state(servicio.url_de_vinculacion_google(otro_titular.id))

    with pytest.raises(ReglaDeNegocioViolada):
        servicio.vincular_google("codigo-2", estado_2)


def test_desvincular_google_sin_contrasena_se_rechaza(
    servicio_con_google: AuthService,
) -> None:
    """Google es el único método de acceso de esta cuenta -desvincularlo la dejaría sin ninguno."""
    estado_login = _extraer_state(servicio_con_google.url_de_inicio_sesion_google())
    usuario = servicio_con_google.iniciar_sesion_con_google("codigo", estado_login).usuario
    assert usuario.contrasena_hash is None

    with pytest.raises(ReglaDeNegocioViolada):
        servicio_con_google.desvincular_google(usuario)


def test_desvincular_google_con_contrasena_funciona(
    servicio_con_google: AuthService,
) -> None:
    resultado = _registrar(servicio_con_google)
    estado = _extraer_state(servicio_con_google.url_de_vinculacion_google(resultado.usuario.id))
    vinculado = servicio_con_google.vincular_google("codigo", estado)

    desvinculado = servicio_con_google.desvincular_google(vinculado)

    assert desvinculado.google_id is None


# ---- Cambiar contraseña ----


def test_cambiar_contrasena_exige_la_actual_si_ya_tenia_una(servicio: AuthService) -> None:
    resultado = _registrar(servicio)

    with pytest.raises(CredencialesInvalidas):
        servicio.cambiar_contrasena(resultado.usuario, "la-que-no-es", "otra-contrasena-nueva")


def test_cambiar_contrasena_con_la_actual_correcta_funciona(servicio: AuthService) -> None:
    resultado = _registrar(servicio)

    servicio.cambiar_contrasena(resultado.usuario, "contrasena-segura", "otra-contrasena-nueva")

    nueva_sesion = servicio.iniciar_sesion(
        IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="otra-contrasena-nueva")
    )
    assert nueva_sesion.usuario.id == resultado.usuario.id


def test_ponerle_contrasena_a_una_cuenta_de_solo_google_no_pide_la_actual(
    servicio_con_google: AuthService,
) -> None:
    estado = _extraer_state(servicio_con_google.url_de_inicio_sesion_google())
    usuario = servicio_con_google.iniciar_sesion_con_google("codigo", estado).usuario
    assert usuario.contrasena_hash is None

    servicio_con_google.cambiar_contrasena(usuario, None, "una-contrasena-nueva")

    assert usuario.contrasena_hash is not None
    sesion_por_contrasena = servicio_con_google.iniciar_sesion(
        IniciarSesionComando(correo="ana@gmail.com", contrasena="una-contrasena-nueva")
    )
    assert sesion_por_contrasena.usuario.id == usuario.id


def test_cambiar_contrasena_nueva_demasiado_corta_se_rechaza(servicio: AuthService) -> None:
    resultado = _registrar(servicio)

    with pytest.raises(DatosInvalidos):
        servicio.cambiar_contrasena(resultado.usuario, "contrasena-segura", "corta")


# ---- Recuperar contraseña olvidada ----


def test_solicitar_recuperacion_de_un_correo_que_no_existe_no_lanza_nada(
    servicio: AuthService,
) -> None:
    """Mismo motivo que iniciar_sesion: no puede confirmarle a quien pregunta si
    ese correo específico tiene cuenta o no -ni con un error, ni con ninguno."""
    servicio.solicitar_recuperacion_contrasena("nadie@ejemplo.cr")


def test_solicitar_recuperacion_de_una_cuenta_desactivada_no_lanza_nada(
    servicio: AuthService, sesion: Session
) -> None:
    resultado = _registrar(servicio)
    resultado.usuario.activo = False
    sesion.commit()

    servicio.solicitar_recuperacion_contrasena(resultado.usuario.correo)


def test_solicitar_recuperacion_sin_servicio_de_correo_configurado_no_lanza_nada(
    servicio: AuthService,
) -> None:
    """`servicio` (sin doble de correo) es el caso "SMTP no configurado" -degrada
    a loguear el enlace, ver EnviarCorreoService; nunca debería reventar por eso."""
    _registrar(servicio)

    servicio.solicitar_recuperacion_contrasena("ana@ejemplo.cr")


def test_solicitar_recuperacion_manda_el_enlace_por_el_servicio_de_correo(
    sesion: Session,
) -> None:
    enviados: list[tuple[str, str, str]] = []

    class CorreoFalso:
        def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
            enviados.append((destinatario, asunto, cuerpo))

    servicio = AuthService(UsuarioRepository(sesion), correo=CorreoFalso())
    resultado = _registrar(servicio)

    servicio.solicitar_recuperacion_contrasena(resultado.usuario.correo)

    assert len(enviados) == 1
    destinatario, asunto, cuerpo = enviados[0]
    assert destinatario == "ana@ejemplo.cr"
    assert "restablecer" in asunto.lower()
    assert "/restablecer-contrasena?token=" in cuerpo


def test_restablecer_contrasena_con_un_enlace_valido_cambia_la_contrasena(
    sesion: Session,
) -> None:
    capturado: dict[str, str] = {}

    class CorreoFalso:
        def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
            capturado["cuerpo"] = cuerpo

    servicio = AuthService(UsuarioRepository(sesion), correo=CorreoFalso())
    resultado = _registrar(servicio)
    servicio.solicitar_recuperacion_contrasena(resultado.usuario.correo)
    token = capturado["cuerpo"].split("token=")[1].split()[0]

    sesion_nueva = servicio.restablecer_contrasena(token, "otra-contrasena-nueva")

    assert sesion_nueva.usuario.id == resultado.usuario.id
    assert sesion_nueva.token
    reingreso = servicio.iniciar_sesion(
        IniciarSesionComando(correo="ana@ejemplo.cr", contrasena="otra-contrasena-nueva")
    )
    assert reingreso.usuario.id == resultado.usuario.id


def test_restablecer_contrasena_con_un_token_ilegible_se_rechaza(servicio: AuthService) -> None:
    with pytest.raises(DatosInvalidos):
        servicio.restablecer_contrasena("esto-no-es-un-token-valido", "otra-contrasena-nueva")


def test_restablecer_contrasena_con_un_token_vencido_se_rechaza(
    servicio: AuthService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mismo ajuste de tiempo que el TTL de sesión: 2.5s de espera, no 1.5s, por la
    resolución de un segundo entero con la que Fernet marca el tiempo."""
    monkeypatch.setattr("app.business.services.auth_service._TTL_RECUPERACION_SEGUNDOS", 1)
    token = cifrar(json.dumps({"usuario_id": 1, "proposito": "recuperar-contrasena"}))

    time.sleep(2.5)

    with pytest.raises(DatosInvalidos):
        servicio.restablecer_contrasena(token, "otra-contrasena-nueva")


def test_restablecer_contrasena_con_un_token_de_otro_proposito_se_rechaza(
    servicio: AuthService, usuario: Usuario
) -> None:
    """Fija la misma protección contra confusión de tokens que ya existe entre
    sesión y los `state` de OAuth2 -acá, contra el propio token de sesión."""
    token_de_sesion = cifrar(json.dumps({"usuario_id": usuario.id, "proposito": "sesion"}))

    with pytest.raises(DatosInvalidos):
        servicio.restablecer_contrasena(token_de_sesion, "otra-contrasena-nueva")


def test_restablecer_contrasena_nueva_demasiado_corta_se_rechaza(
    servicio: AuthService, usuario: Usuario
) -> None:
    token = cifrar(json.dumps({"usuario_id": usuario.id, "proposito": "recuperar-contrasena"}))

    with pytest.raises(DatosInvalidos):
        servicio.restablecer_contrasena(token, "corta")


def test_restablecer_contrasena_de_una_cuenta_desactivada_se_rechaza(
    servicio: AuthService, sesion: Session
) -> None:
    resultado = _registrar(servicio)
    resultado.usuario.activo = False
    sesion.commit()
    token = cifrar(
        json.dumps({"usuario_id": resultado.usuario.id, "proposito": "recuperar-contrasena"})
    )

    with pytest.raises(DatosInvalidos):
        servicio.restablecer_contrasena(token, "otra-contrasena-nueva")
