"""Endpoints del catálogo de comercios y su categoría sugerida por titular."""

from fastapi import APIRouter

from app.presentation.dependencies import ServicioDeComercios
from app.presentation.schemas import AsignarCategoriaComercioRequest, ComercioResponse

router = APIRouter(prefix="/api/comercios", tags=["comercios"])


@router.post(
    "/{comercio_id}/categoria",
    response_model=ComercioResponse,
    summary="Asignar o corregir la categoría sugerida de un comercio",
)
def asignar_categoria(
    comercio_id: int,
    peticion: AsignarCategoriaComercioRequest,
    servicio: ServicioDeComercios,
) -> ComercioResponse:
    """ "Corregir crea la regla": la próxima vez que este comercio aparezca en un
    comprobante de este mismo titular, esta es la categoría que se va a sugerir.
    No afecta a ningún otro titular que compre en el mismo comercio.
    """
    servicio.asignar_categoria(peticion.usuario_id, comercio_id, peticion.categoria_id)
    return ComercioResponse.model_validate(servicio.obtener(comercio_id))
