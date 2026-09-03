"""Endpoints de registro, inicio de sesión, y login/vinculación con Google.

No hay `logout` en el servidor: el token de sesión no se guarda en ninguna
tabla (ver la nota en `auth_service.py`), así que no hay nada que revocar
del lado del servidor. Cerrar sesión es responsabilidad exclusiva del
cliente -descartar el token guardado.
"""

from fastapi import APIRouter, status

from app.business.services.auth_service import (
    IniciarSesionComando,
    RegistrarUsuarioComando,
)
from app.data.models.usuario import Usuario
from app.presentation.dependencies import ServicioDeAuth, UsuarioActualDependencia
from app.presentation.schemas import (
    CallbackGoogleRequest,
    CambiarContrasenaRequest,
    IniciarSesionRequest,
    RegistrarUsuarioRequest,
    SesionResponse,
    UrlDeAutorizacionResponse,
    UsuarioResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _respuesta_de_usuario(usuario: Usuario) -> UsuarioResponse:
    """`tiene_contrasena`/`google_vinculado` son derivadas, no columnas -ver schemas.py."""
    return UsuarioResponse(
        id=usuario.id,
        nombre_completo=usuario.nombre_completo,
        correo=usuario.correo,
        moneda_preferida=usuario.moneda_preferida,
        tiene_contrasena=usuario.contrasena_hash is not None,
        google_vinculado=usuario.google_id is not None,
    )


def _respuesta_de_sesion(token: str, usuario: Usuario) -> SesionResponse:
    return SesionResponse(token=token, usuario=_respuesta_de_usuario(usuario))


@router.post(
    "/registro",
    response_model=SesionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una cuenta nueva",
)
def registro(peticion: RegistrarUsuarioRequest, servicio: ServicioDeAuth) -> SesionResponse:
    """Crea la cuenta y devuelve una sesión ya iniciada -no hace falta loguearse aparte."""
    sesion = servicio.registrar(
        RegistrarUsuarioComando(
            nombre_completo=peticion.nombre_completo,
            correo=peticion.correo,
            contrasena=peticion.contrasena,
        )
    )
    return _respuesta_de_sesion(sesion.token, sesion.usuario)


@router.post("/iniciar-sesion", response_model=SesionResponse, summary="Iniciar sesión")
def iniciar_sesion(peticion: IniciarSesionRequest, servicio: ServicioDeAuth) -> SesionResponse:
    sesion = servicio.iniciar_sesion(
        IniciarSesionComando(correo=peticion.correo, contrasena=peticion.contrasena)
    )
    return _respuesta_de_sesion(sesion.token, sesion.usuario)


@router.get(
    "/yo", response_model=UsuarioResponse, summary="Quién es el titular de la sesión actual"
)
def yo(usuario_actual: UsuarioActualDependencia) -> UsuarioResponse:
    """Confirma un token guardado y trae los datos del titular -para no tener que
    volver a pedir correo y contraseña solo para saber si la sesión sigue viva.
    """
    return _respuesta_de_usuario(usuario_actual)


@router.post(
    "/contrasena",
    response_model=UsuarioResponse,
    summary="Cambiar la contraseña, o ponerle una por primera vez a una cuenta de solo Google",
)
def cambiar_contrasena(
    peticion: CambiarContrasenaRequest,
    servicio: ServicioDeAuth,
    usuario_actual: UsuarioActualDependencia,
) -> UsuarioResponse:
    servicio.cambiar_contrasena(
        usuario_actual, peticion.contrasena_actual, peticion.contrasena_nueva
    )
    return _respuesta_de_usuario(usuario_actual)


@router.get(
    "/google/iniciar",
    response_model=UrlDeAutorizacionResponse,
    summary="URL de Google para iniciar sesión (registro o login, según corresponda)",
)
def iniciar_login_google(servicio: ServicioDeAuth) -> UrlDeAutorizacionResponse:
    """Público: nadie está identificado todavía, es justamente lo que este flujo resuelve."""
    return UrlDeAutorizacionResponse(url_autorizacion=servicio.url_de_inicio_sesion_google())


@router.post(
    "/google/callback",
    response_model=SesionResponse,
    summary="Completar el login con Google (crea la cuenta si es la primera vez)",
)
def callback_login_google(
    peticion: CallbackGoogleRequest, servicio: ServicioDeAuth
) -> SesionResponse:
    sesion = servicio.iniciar_sesion_con_google(peticion.codigo, peticion.estado)
    return _respuesta_de_sesion(sesion.token, sesion.usuario)


@router.get(
    "/google/vincular/iniciar",
    response_model=UrlDeAutorizacionResponse,
    summary="URL de Google para vincular login con Google a la cuenta ya logueada",
)
def iniciar_vinculacion_google(
    servicio: ServicioDeAuth, usuario_actual: UsuarioActualDependencia
) -> UrlDeAutorizacionResponse:
    """El `usuario_id` viaja cifrado dentro del `state` -no como parámetro- por lo
    mismo que vincular un buzón en `cuentas_correo.py`: el callback que Google
    llama de vuelta no manda ningún encabezado de sesión, así que es el único
    lugar donde el backend puede recordar quién iba vinculando.
    """
    url = servicio.url_de_vinculacion_google(usuario_actual.id)
    return UrlDeAutorizacionResponse(url_autorizacion=url)


@router.post(
    "/google/vincular/callback",
    response_model=UsuarioResponse,
    summary="Completar la vinculación de Google a una cuenta",
)
def callback_vinculacion_google(
    peticion: CallbackGoogleRequest, servicio: ServicioDeAuth
) -> UsuarioResponse:
    usuario = servicio.vincular_google(peticion.codigo, peticion.estado)
    return _respuesta_de_usuario(usuario)


@router.delete(
    "/google/vincular",
    response_model=UsuarioResponse,
    summary="Desvincular Google como método de acceso",
)
def desvincular_google(
    servicio: ServicioDeAuth, usuario_actual: UsuarioActualDependencia
) -> UsuarioResponse:
    usuario = servicio.desvincular_google(usuario_actual)
    return _respuesta_de_usuario(usuario)
