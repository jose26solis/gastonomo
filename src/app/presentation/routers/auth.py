"""Endpoints de registro e inicio de sesión.

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
from app.presentation.dependencies import ServicioDeAuth, UsuarioActualDependencia
from app.presentation.schemas import (
    IniciarSesionRequest,
    RegistrarUsuarioRequest,
    SesionResponse,
    UsuarioResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
    return SesionResponse(
        token=sesion.token, usuario=UsuarioResponse.model_validate(sesion.usuario)
    )


@router.post("/iniciar-sesion", response_model=SesionResponse, summary="Iniciar sesión")
def iniciar_sesion(peticion: IniciarSesionRequest, servicio: ServicioDeAuth) -> SesionResponse:
    sesion = servicio.iniciar_sesion(
        IniciarSesionComando(correo=peticion.correo, contrasena=peticion.contrasena)
    )
    return SesionResponse(
        token=sesion.token, usuario=UsuarioResponse.model_validate(sesion.usuario)
    )


@router.get(
    "/yo", response_model=UsuarioResponse, summary="Quién es el titular de la sesión actual"
)
def yo(usuario_actual: UsuarioActualDependencia) -> UsuarioResponse:
    """Confirma un token guardado y trae los datos del titular -para no tener que
    volver a pedir correo y contraseña solo para saber si la sesión sigue viva.
    """
    return UsuarioResponse.model_validate(usuario_actual)
