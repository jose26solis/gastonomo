"""Endpoint de salud: confirma que el sistema esta en linea."""

from fastapi import APIRouter

from app.config.settings import obtener_configuracion
from app.presentation.schemas import SaludResponse

router = APIRouter(prefix="/api", tags=["salud"])


@router.get("/salud", response_model=SaludResponse, summary="Estado del sistema")
def consultar_salud() -> SaludResponse:
    """Responde si la aplicacion levanto. Es lo que verifica la integracion continua."""
    configuracion = obtener_configuracion()
    return SaludResponse(
        estado="OK - sistema en linea",
        aplicacion=configuracion.nombre_aplicacion,
        version=configuracion.version,
    )
