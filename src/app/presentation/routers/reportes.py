"""Endpoints de exportación de reportes.

Aparte de `cuentas_correo.py` porque acá la respuesta no es JSON -es un
archivo para descargar- y eso cambia cómo se arma: encabezados de
`Content-Disposition`, texto CSV en vez de un `response_model` de Pydantic.
La URL sigue bajo `/api/cuentas-correo/{cuenta_id}/...` para que sea
consistente con el resto de endpoints que necesitan leer una bandeja real.
"""

import csv
import io
from decimal import Decimal

from fastapi import APIRouter, Query, Response
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.business.errors import ReglaDeNegocioViolada
from app.business.services.comercio_service import ComercioClasificado, MovimientoDetallado
from app.business.services.resumen_service import entrada_preferida_del_periodo
from app.data.models.enums import EstadoCuentaCorreo
from app.presentation.dependencies import ServicioDeComercios, ServicioDeCuentasCorreo

router = APIRouter(prefix="/api/cuentas-correo", tags=["reportes"])

_MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
)  # fmt: skip


@router.get(
    "/{cuenta_id}/reportes/movimientos.csv",
    summary="Exportar los movimientos reconocidos a CSV",
)
def exportar_movimientos_csv(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
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


@router.get(
    "/{cuenta_id}/reportes/movimientos.xlsx",
    summary="Exportar los movimientos reconocidos a Excel",
)
def exportar_movimientos_excel(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Lo mismo que el CSV, pero como una hoja de Excel de verdad -con
    encabezado en negrita, columnas anchas y el monto como número, no texto.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    movimientos = servicio_comercios.detallar_comprobantes(usuario_id, resumen.comprobantes)
    contenido = _excel_de_movimientos(movimientos)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-movimientos.xlsx"'},
    )


@router.get(
    "/{cuenta_id}/reportes/resumen.pdf",
    summary="Exportar un reporte de gastos en PDF",
)
def exportar_resumen_pdf(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Arma un reporte de una página: KPIs y desglose por comercio del mes más
    reciente que tenga comprobantes reconocidos.

    No recibe año/mes por parámetro a propósito -mismo criterio que
    `Resumen.tsx` en el frontend: toma el mes más reciente de lo que
    realmente hay, en vez de dejar pedir un período que puede no tener datos.

    Si ese mes tuvo movimientos en más de una moneda -`resumen.por_mes` trae
    una fila por moneda, nunca las mezcla-, se prefiere colones y el reporte
    queda de esa moneda; no hay espacio en una página de una sola moneda para
    mostrar las dos.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    if not resumen.por_mes:
        raise ReglaDeNegocioViolada(
            "No hay comprobantes de BAC reconocidos todavía para armar un reporte."
        )
    anio_mas_reciente = resumen.por_mes[0].anio
    mes_mas_reciente = resumen.por_mes[0].mes
    mes_actual = entrada_preferida_del_periodo(resumen.por_mes, anio_mas_reciente, mes_mas_reciente)
    assert mes_actual is not None  # por_mes[0] es de ese mismo período, siempre hay al menos uno
    prefijo_mes = f"{mes_actual.anio}-{mes_actual.mes:02d}"
    comprobantes_del_mes = [
        c
        for c in resumen.comprobantes
        if c.fecha and c.fecha.strftime("%Y-%m") == prefijo_mes and c.moneda == mes_actual.moneda
    ]
    comercios = servicio_comercios.clasificar_comprobantes(usuario_id, comprobantes_del_mes)

    cuenta = next((c for c in servicio.listar(usuario_id) if c.id == cuenta_id), None)
    direccion = cuenta.direccion if cuenta else ""

    contenido = _pdf_de_resumen(
        direccion_cuenta=direccion,
        anio=mes_actual.anio,
        mes=mes_actual.mes,
        moneda=mes_actual.moneda,
        total_mes=mes_actual.total,
        cantidad_transacciones=mes_actual.cantidad_transacciones,
        comercios=comercios,
    )
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-reporte.pdf"'},
    )


@router.get(
    "/reportes/movimientos.csv",
    summary="Exportar a CSV los movimientos de todas las cuentas activas del titular",
)
def exportar_movimientos_csv_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Igual que `/{cuenta_id}/reportes/movimientos.csv`, pero combinando todas
    las cuentas activas del titular en vez de exportar una sola bandeja.
    """
    resumen = servicio.resumen_financiero_de_usuario(usuario_id, limite)
    movimientos = servicio_comercios.detallar_comprobantes(usuario_id, resumen.comprobantes)
    contenido = _csv_de_movimientos(movimientos)
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-movimientos.csv"'},
    )


@router.get(
    "/reportes/movimientos.xlsx",
    summary="Exportar a Excel los movimientos de todas las cuentas activas del titular",
)
def exportar_movimientos_excel_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Igual que `/{cuenta_id}/reportes/movimientos.xlsx`, pero combinando todas
    las cuentas activas del titular en vez de exportar una sola bandeja.
    """
    resumen = servicio.resumen_financiero_de_usuario(usuario_id, limite)
    movimientos = servicio_comercios.detallar_comprobantes(usuario_id, resumen.comprobantes)
    contenido = _excel_de_movimientos(movimientos)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-movimientos.xlsx"'},
    )


@router.get(
    "/reportes/resumen.pdf",
    summary="Exportar un reporte en PDF combinando todas las cuentas activas del titular",
)
def exportar_resumen_pdf_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> Response:
    """Igual que `/{cuenta_id}/reportes/resumen.pdf`, pero sobre el gasto
    combinado de todas las cuentas activas del titular.
    """
    resumen = servicio.resumen_financiero_de_usuario(usuario_id, limite)
    if not resumen.por_mes:
        raise ReglaDeNegocioViolada(
            "No hay comprobantes de BAC reconocidos todavía para armar un reporte."
        )
    anio_mas_reciente = resumen.por_mes[0].anio
    mes_mas_reciente = resumen.por_mes[0].mes
    mes_actual = entrada_preferida_del_periodo(resumen.por_mes, anio_mas_reciente, mes_mas_reciente)
    assert mes_actual is not None  # por_mes[0] es de ese mismo período, siempre hay al menos uno
    prefijo_mes = f"{mes_actual.anio}-{mes_actual.mes:02d}"
    comprobantes_del_mes = [
        c
        for c in resumen.comprobantes
        if c.fecha and c.fecha.strftime("%Y-%m") == prefijo_mes and c.moneda == mes_actual.moneda
    ]
    comercios = servicio_comercios.clasificar_comprobantes(usuario_id, comprobantes_del_mes)

    direcciones = [
        c.direccion for c in servicio.listar(usuario_id) if c.estado == EstadoCuentaCorreo.ACTIVA
    ]

    contenido = _pdf_de_resumen(
        direccion_cuenta=", ".join(direcciones),
        anio=mes_actual.anio,
        mes=mes_actual.mes,
        moneda=mes_actual.moneda,
        total_mes=mes_actual.total,
        cantidad_transacciones=mes_actual.cantidad_transacciones,
        comercios=comercios,
    )
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="gastonomo-reporte.pdf"'},
    )


def _truncar(valor: str, largo_maximo: int = 40) -> str:
    """Corta un valor largo antes de meterlo en una celda del PDF de ancho fijo.

    El nombre de un comercio viene tal cual del cuerpo de un correo real, sin
    ningún largo garantizado. Estas celdas son texto plano -no un
    `Paragraph`, que sí ajusta línea- así que un nombre inusualmente largo
    desbordaría la columna en vez de arruinar el layout con un salto raro.
    """
    return valor if len(valor) <= largo_maximo else valor[: largo_maximo - 1] + "…"


_CARACTERES_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _celda_segura(valor: str) -> str:
    """Neutraliza una posible inyección de fórmula (CSV/Excel).

    Un valor que empieza con `=`, `+`, `-`, `@` o un tabulador/retorno de
    carro se interpreta como fórmula al abrirlo en Excel o LibreOffice -y el
    nombre de un comercio es texto que viene tal cual del cuerpo de un
    correo, no un dato que esta aplicación controle. Anteponerle una comilla
    simple es la mitigación estándar (OWASP: CSV Injection): fuerza texto
    literal sin cambiar lo que el usuario termina viendo en la celda.
    """
    if valor and valor[0] in _CARACTERES_DE_FORMULA:
        return "'" + valor
    return valor


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
                _celda_segura(movimiento.comercio),
                _celda_segura(movimiento.categoria_nombre or ""),
                str(movimiento.monto),
                movimiento.moneda,
                _celda_segura(movimiento.marca_tarjeta or ""),
                movimiento.ultimos_cuatro or "",
                _celda_segura(movimiento.ciudad or ""),
                _celda_segura(movimiento.pais or ""),
                _celda_segura(movimiento.banco),
                movimiento.autorizacion or "",
                movimiento.referencia or "",
            ]
        )
    return buffer.getvalue()


_ENCABEZADOS_EXCEL = (
    "Fecha",
    "Comercio",
    "Categoría",
    "Monto",
    "Moneda",
    "Marca",
    "Últimos 4",
    "Ciudad",
    "País",
    "Banco",
    "Autorización",
    "Referencia",
)


def _excel_de_movimientos(movimientos: list[MovimientoDetallado]) -> bytes:
    """Arma el libro de Excel en memoria y lo devuelve como bytes, listo para la respuesta."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Movimientos"

    hoja.append(_ENCABEZADOS_EXCEL)
    for celda in hoja[1]:
        celda.font = Font(bold=True)

    for movimiento in movimientos:
        hoja.append(
            [
                movimiento.fecha,
                _celda_segura(movimiento.comercio),
                _celda_segura(movimiento.categoria_nombre or ""),
                movimiento.monto,
                movimiento.moneda,
                _celda_segura(movimiento.marca_tarjeta or ""),
                movimiento.ultimos_cuatro or "",
                _celda_segura(movimiento.ciudad or ""),
                _celda_segura(movimiento.pais or ""),
                _celda_segura(movimiento.banco),
                movimiento.autorizacion or "",
                movimiento.referencia or "",
            ]
        )

    for indice, encabezado in enumerate(_ENCABEZADOS_EXCEL, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = max(len(encabezado) + 4, 14)
    # Columna "Monto": con separador de miles y dos decimales.
    for fila in range(2, hoja.max_row + 1):
        hoja.cell(row=fila, column=4).number_format = "#,##0.00"

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _pdf_de_resumen(
    direccion_cuenta: str,
    anio: int,
    mes: int,
    moneda: str,
    total_mes: Decimal,
    cantidad_transacciones: int,
    comercios: list[ComercioClasificado],
) -> bytes:
    """Arma un reporte de una página con reportlab y lo devuelve como bytes."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm)
    estilos = getSampleStyleSheet()
    elementos: list = []

    elementos.append(Paragraph("Reporte de gastos · Gastonomo", estilos["Title"]))
    elementos.append(
        Paragraph(f"{_MESES_ES[mes - 1]} {anio} · {direccion_cuenta}", estilos["Normal"])
    )
    elementos.append(Spacer(1, 0.6 * cm))

    tabla_kpis = Table(
        [
            ["Gasto total", "Transacciones", "Comercios"],
            [f"{moneda} {total_mes:,.2f}", str(cantidad_transacciones), str(len(comercios))],
        ],
        colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
    )
    tabla_kpis.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
            ]
        )
    )
    elementos.append(tabla_kpis)
    elementos.append(Spacer(1, 0.8 * cm))

    elementos.append(Paragraph("Por comercio", estilos["Heading2"]))
    filas = [["Comercio", "Categoría", "Transacciones", "Total"]]
    for comercio in comercios:
        filas.append(
            [
                _truncar(comercio.nombre),
                _truncar(comercio.categoria_nombre or "Sin clasificar"),
                str(comercio.cantidad_transacciones),
                f"{comercio.moneda} {comercio.total:,.2f}",
            ]
        )
    tabla = Table(filas, colWidths=[6 * cm, 4.5 * cm, 3 * cm, 3 * cm], repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elementos.append(tabla)

    documento.build(elementos)
    return buffer.getvalue()
