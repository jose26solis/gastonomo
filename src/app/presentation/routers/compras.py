"""Endpoint de la bitácora de trazabilidad de una compra.

El diferenciador declarado del dominio: de cualquier total en pantalla se
puede bajar hasta el comprobante que lo generó, pasando por el tipo de
cambio y la regla de categorización que se aplicaron. Ver ADR-002.
"""

from fastapi import APIRouter, Query

from app.business.errors import RecursoNoEncontrado
from app.presentation.dependencies import ServicioDeBitacora, ServicioDeCompras, VerificarTitular
from app.presentation.schemas import EventoBitacoraResponse

router = APIRouter(prefix="/api/compras", tags=["compras"])


@router.get(
    "/{compra_id}/bitacora",
    response_model=list[EventoBitacoraResponse],
    summary="La trazabilidad completa de una compra: de qué correo nació y cómo se clasificó",
)
def bitacora_de_compra(
    compra_id: int,
    servicio: ServicioDeCompras,
    bitacora: ServicioDeBitacora,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> list[EventoBitacoraResponse]:
    """Lista de eventos en el orden en que ocurrieron.

    404 si la compra no existe o no pertenece a este titular -verificado
    contra PostgreSQL, que sí sabe de quién es cada compra; Mongo no filtra
    por dueño por sí solo. También 404 si Mongo no tiene nada guardado para
    ella todavía -por ejemplo, si se conciliaron antes de que Mongo
    estuviera disponible.
    """
    servicio.obtener_del_titular(usuario_id, compra_id)
    eventos = bitacora.bitacora_de(compra_id)
    if eventos is None:
        raise RecursoNoEncontrado(f"No hay bitácora para la compra {compra_id}.")
    return [EventoBitacoraResponse(**evento) for evento in eventos]
