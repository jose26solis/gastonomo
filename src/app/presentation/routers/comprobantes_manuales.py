"""Endpoint de previsualización para cargar a mano un comprobante de compra.

Solo BAC tiene un lector exacto, validado contra una notificación real (ver
`comprobante_bac.py`). Para cualquier otro banco -mientras no exista esa
notificación real para construirle uno propio- el titular pega el texto de
la notificación en la pantalla "Cargar comprobante", este endpoint corre el
lector genérico (`comprobante_generico.py`) y devuelve una previsualización
para que la confirme o la corrija. La creación real de la `Compra` -ya con
los campos confirmados- es `POST /api/compras/manual`, en `compras.py`: este
endpoint no persiste nada, solo lee.
"""

from fastapi import APIRouter

from app.business.parsers.comprobante_generico import parsear_comprobante_generico
from app.presentation.dependencies import UsuarioActualDependencia
from app.presentation.schemas import (
    AnalizarComprobanteManualRequest,
    ComprobanteManualAnalizadoResponse,
)

router = APIRouter(prefix="/api/comprobantes-manuales", tags=["comprobantes-manuales"])


@router.post(
    "/analizar",
    response_model=ComprobanteManualAnalizadoResponse,
    summary="Leer lo que se pueda del texto de un comprobante pegado a mano",
)
def analizar(
    peticion: AnalizarComprobanteManualRequest,
    _: UsuarioActualDependencia,
) -> ComprobanteManualAnalizadoResponse:
    """Requiere sesión iniciada -no importa de quién, no toca ningún dato de un
    titular en particular- solo para que este análisis de texto no quede
    abierto a cualquiera sin loguearse, igual que el resto de la API."""
    parseado = parsear_comprobante_generico(peticion.banco, peticion.texto)
    return ComprobanteManualAnalizadoResponse(
        banco=parseado.banco,
        comercio=parseado.comercio,
        fecha=parseado.fecha,
        marca_tarjeta=parseado.marca_tarjeta,
        ultimos_cuatro=parseado.ultimos_cuatro,
        autorizacion=parseado.autorizacion,
        referencia=parseado.referencia,
        moneda=parseado.moneda,
        monto=parseado.monto,
        confianza=parseado.confianza,
    )
