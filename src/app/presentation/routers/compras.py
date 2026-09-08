"""Endpoints de Compra: listado, detalle, corrección manual y bitácora.

Antes de esto, `Compra` -el resultado real de conciliar un comprobante-
solo se podía "ver" indirectamente, a través de los campos planos de
`Comprobante` o de los eventos sueltos de su bitácora en Mongo. Nunca su
propio estado (`requiere_revision`, con qué método de pago y categoría
quedó). Estos endpoints son lo que la hace un dato de primera clase: se
puede listar, filtrar por "necesita revisión", ver en detalle, y corregir a
mano -y ahí sí, bajar hasta el comprobante que la generó (`/bitacora`, el
diferenciador declarado del dominio, ver ADR-002).
"""

from datetime import datetime

from fastapi import APIRouter, Query

from app.business.errors import RecursoNoEncontrado
from app.business.parsers.comprobante_bac import ComprobanteParseado
from app.business.services.compra_service import CompraDetallada
from app.business.services.conciliacion_service import LineaDesgloseComando
from app.presentation.dependencies import (
    ServicioDeBitacora,
    ServicioDeCompras,
    ServicioDeConciliacion,
    UsuarioActualDependencia,
    VerificarTitular,
    verificar_mismo_usuario,
)
from app.presentation.schemas import (
    CompraResponse,
    CrearComprobanteManualRequest,
    DesglosarCompraRequest,
    EventoBitacoraResponse,
    GastoPorCategoriaResponse,
    LineaCompraResponse,
    ResolverRevisionCompraRequest,
)

router = APIRouter(prefix="/api/compras", tags=["compras"])


def _respuesta(detalle: CompraDetallada) -> CompraResponse:
    compra = detalle.compra
    return CompraResponse(
        id=compra.id,
        usuario_id=compra.usuario_id,
        comercio_id=compra.comercio_id,
        comercio_nombre=detalle.comercio_nombre,
        metodo_pago_id=compra.metodo_pago_id,
        metodo_pago_alias=detalle.metodo_pago_alias,
        categoria_id=detalle.categoria_id,
        categoria_nombre=detalle.categoria_nombre,
        fecha=compra.fecha,
        descripcion=compra.descripcion,
        moneda=compra.moneda,
        total=compra.total,
        total_moneda_base=compra.total_moneda_base,
        tipo_cambio_aplicado=compra.tipo_cambio_aplicado,
        estado=compra.estado,
        origen=compra.origen,
        requiere_revision=compra.requiere_revision,
        creado_en=compra.creado_en,
        lineas=[
            LineaCompraResponse(
                id=linea.id,
                descripcion=linea.descripcion,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
                descuento=linea.descuento,
                exento_impuesto=linea.exento_impuesto,
                subtotal=linea.subtotal,
                categoria_id=linea.categoria_id,
                categoria_nombre=linea.categoria.nombre if linea.categoria else None,
                categorizada_automaticamente=linea.categorizada_automaticamente,
            )
            for linea in compra.lineas
        ],
    )


@router.get(
    "", response_model=list[CompraResponse], summary="Listar las compras reales del titular"
)
def listar(
    servicio: ServicioDeCompras,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    requiere_revision: bool | None = Query(
        default=None,
        description="True trae solo las que quedaron sin método de pago o sin categoría.",
    ),
    limite: int = Query(default=50, gt=0, le=200),
) -> list[CompraResponse]:
    return [
        _respuesta(detalle)
        for detalle in servicio.listar_del_titular(usuario_id, requiere_revision, limite)
    ]


@router.get(
    "/gasto-por-categoria",
    response_model=list[GastoPorCategoriaResponse],
    summary="Gasto agregado por categoría, sumado y agrupado en la base de datos",
)
def gasto_por_categoria(
    servicio: ServicioDeCompras,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    comercio_id: int | None = Query(default=None, gt=0, le=2_147_483_647),
) -> list[GastoPorCategoriaResponse]:
    """Declarado antes de `/{compra_id}` a propósito: FastAPI resuelve las rutas
    en el orden en que se registran, y como `{compra_id}` es `int`,
    `gasto-por-categoria` nunca calzaría con él -pero si este endpoint se
    registrara después, el intento de convertirlo a `int` lo enmascararía
    con un 422 en vez de responder.
    """
    return [
        GastoPorCategoriaResponse(
            categoria_id=gasto.categoria_id,
            categoria_nombre=gasto.categoria_nombre or "Sin categoría",
            total=gasto.total,
        )
        for gasto in servicio.gasto_por_categoria(usuario_id, anio, mes, comercio_id)
    ]


@router.post(
    "/manual",
    response_model=CompraResponse,
    summary="Crear una compra real a partir de un comprobante cargado a mano",
)
def crear_manual(
    peticion: CrearComprobanteManualRequest,
    servicio: ServicioDeCompras,
    conciliacion: ServicioDeConciliacion,
    usuario_actual: UsuarioActualDependencia,
) -> CompraResponse:
    """Declarado antes de `/{compra_id}` por el mismo motivo que
    `gasto-por-categoria` -acá `usuario_id` viaja en el cuerpo, no en la URL,
    así que se verifica a mano en vez de con `VerificarTitular`.

    Los campos ya vienen confirmados (o corregidos) por el titular sobre la
    previsualización de `POST /api/comprobantes-manuales/analizar` -acá no se
    vuelve a parsear texto, solo se arma el `ComprobanteParseado` que
    `ConciliacionService.conciliar_manual` espera.
    """
    verificar_mismo_usuario(usuario_actual, peticion.usuario_id)
    parseado = ComprobanteParseado(
        banco=peticion.banco,
        comercio=peticion.comercio,
        ciudad=None,
        pais=None,
        fecha=datetime.combine(peticion.fecha, datetime.min.time()),
        marca_tarjeta=None,
        ultimos_cuatro=peticion.ultimos_cuatro,
        autorizacion=None,
        referencia=None,
        tipo_transaccion="COMPRA",
        moneda=peticion.moneda.value,
        monto=peticion.monto,
        confianza=1.0,  # ya confirmado por el titular -no hace falta pesarlo
    )
    resultado = conciliacion.conciliar_manual(
        peticion.usuario_id, parseado, peticion.metodo_pago_id, peticion.categoria_id
    )
    return _respuesta(
        servicio.obtener_detalle_del_titular(peticion.usuario_id, resultado.compra_id)
    )


@router.get("/{compra_id}", response_model=CompraResponse, summary="Detalle de una compra real")
def detalle(
    compra_id: int,
    servicio: ServicioDeCompras,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> CompraResponse:
    return _respuesta(servicio.obtener_detalle_del_titular(usuario_id, compra_id))


@router.post(
    "/{compra_id}/resolver",
    response_model=CompraResponse,
    summary="Corregir a mano el método de pago y/o la categoría de una compra",
)
def resolver(
    compra_id: int,
    peticion: ResolverRevisionCompraRequest,
    servicio: ServicioDeCompras,
    conciliacion: ServicioDeConciliacion,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> CompraResponse:
    conciliacion.resolver_revision(
        usuario_id, compra_id, peticion.metodo_pago_id, peticion.categoria_id
    )
    return _respuesta(servicio.obtener_detalle_del_titular(usuario_id, compra_id))


@router.post(
    "/{compra_id}/desglosar",
    response_model=CompraResponse,
    summary="Partir una compra en varios renglones, cada uno con su propia categoría",
)
def desglosar(
    compra_id: int,
    peticion: DesglosarCompraRequest,
    servicio: ServicioDeCompras,
    conciliacion: ServicioDeConciliacion,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> CompraResponse:
    conciliacion.desglosar_compra(
        usuario_id,
        compra_id,
        [
            LineaDesgloseComando(
                descripcion=linea.descripcion,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
                descuento=linea.descuento,
                exento_impuesto=linea.exento_impuesto,
                categoria_id=linea.categoria_id,
            )
            for linea in peticion.lineas
        ],
    )
    return _respuesta(servicio.obtener_detalle_del_titular(usuario_id, compra_id))


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
