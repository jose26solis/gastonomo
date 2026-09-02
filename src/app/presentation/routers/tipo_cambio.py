"""Endpoint del tipo de cambio de referencia (colones/dólares)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.presentation.dependencies import ServicioDeTipoCambio
from app.presentation.schemas import TipoDeCambioResponse

router = APIRouter(prefix="/api/tipo-cambio", tags=["tipo-cambio"])


@router.get(
    "",
    response_model=TipoDeCambioResponse,
    summary="Tipo de cambio de referencia del colón contra el dólar",
)
def obtener_tipo_de_cambio(
    servicio: ServicioDeTipoCambio,
    fecha: Annotated[date | None, Query(description="Por defecto, hoy")] = None,
) -> TipoDeCambioResponse:
    """Trae el tipo de cambio del Banco Central para la fecha pedida (hoy, si no se indica).

    Da 502 si el servicio del BCCR no está configurado (falta suscribirse,
    ver el README) o si el Banco Central no responde -es información de
    referencia, no algo que la aplicación pueda inventar si el proveedor
    externo no está disponible.
    """
    return TipoDeCambioResponse.model_validate(servicio.obtener(fecha))
