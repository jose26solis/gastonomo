"""Endpoints de exportación de reportes.

Aparte de `cuentas_correo.py` porque acá la respuesta no es JSON -es un
archivo para descargar- y eso cambia cómo se arma: encabezados de
`Content-Disposition`, texto CSV en vez de un `response_model` de Pydantic.
La URL sigue bajo `/api/cuentas-correo/{cuenta_id}/...` para que sea
consistente con el resto de endpoints que necesitan leer una bandeja real.
"""

import csv
import io

from fastapi import APIRouter, Query, Response

from app.business.services.comercio_service import MovimientoDetallado
from app.presentation.dependencies import ServicioDeComercios, ServicioDeCuentasCorreo

router = APIRouter(prefix="/api/cuentas-correo", tags=["reportes"])


@router.get(
    "/{cuenta_id}/reportes/movimientos.csv",
    summary="Exportar los movimientos reconocidos a CSV",
)
def exportar_movimientos_csv(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Trae los comprobantes de BAC reconocidos y los exporta a CSV, un renglón por movimiento.

    Solo incluye compras que el parser entendió con confianza -mismo filtro
    que el resto del sistema- para no exportar una cifra que no se está
    seguro de haber leído bien. Puede tardar varios segundos: lee cada
    comprobante de la bandeja real, igual que `/resumen-financiero`.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    movimientos = servicio_comercios.detallar_comprobantes(usuario_id, resumen.comprobantes)
    contenido = _csv_de_movimientos(movimientos)
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-movimientos.csv"'},
    )


_ENCABEZADOS = (
    "fecha",
    "comercio",
    "categoria",
    "monto",
    "moneda",
    "marca_tarjeta",
    "ultimos_cuatro",
    "ciudad",
    "pais",
    "banco",
    "autorizacion",
    "referencia",
)


def _csv_de_movimientos(movimientos: list[MovimientoDetallado]) -> str:
    """Arma el texto del CSV.

    El BOM (`﻿`) al inicio es para Excel en Windows: sin él, asume la
    codificación de la página de códigos local en vez de UTF-8 y los acentos
    de categorías y comercios salen ilegibles.
    """
    buffer = io.StringIO()
    buffer.write("﻿")
    escritor = csv.writer(buffer)
    escritor.writerow(_ENCABEZADOS)
    for movimiento in movimientos:
        escritor.writerow(
            [
                movimiento.fecha.isoformat(),
                movimiento.comercio,
                movimiento.categoria_nombre or "",
                str(movimiento.monto),
                movimiento.moneda,
                movimiento.marca_tarjeta or "",
                movimiento.ultimos_cuatro or "",
                movimiento.ciudad or "",
                movimiento.pais or "",
                movimiento.banco,
                movimiento.autorizacion or "",
                movimiento.referencia or "",
            ]
        )
    return buffer.getvalue()
