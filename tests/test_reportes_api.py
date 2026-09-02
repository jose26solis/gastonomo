"""La API de exportación de reportes."""

import csv
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo
from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.data.models.enums import ProveedorCorreo
from app.data.models.usuario import Usuario
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_cuentas_correo
from app.presentation.routers.cuentas_correo import _codificar_estado
from app.presentation.routers.reportes import _pdf_de_resumen


def test_exportar_csv_trae_solo_lo_de_bac_con_encabezado(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    """El doble de prueba trae un correo de BAC (WALMART) y uno de PriceSmart (filtrado antes)."""
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/reportes/movimientos.csv",
        params={"usuario_id": usuario.id},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "gastonomo-movimientos.csv" in respuesta.headers["content-disposition"]

    # El BOM al inicio es a propósito -Excel en Windows lo necesita-; se
    # descarta acá para poder parsear el CSV con el módulo estándar.
    texto = respuesta.text.lstrip("﻿")
    filas = list(csv.reader(io.StringIO(texto)))

    assert filas[0] == [
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
    ]
    assert len(filas) == 2, "una sola fila de datos: el correo de PriceSmart no es de BAC"
    assert filas[1][1] == "WALMART SAN SEBASTIAN"
    assert filas[1][3] == "7870.00"
    assert filas[1][2] == "", "todavía no se asignó categoría a este comercio"


def test_exportar_csv_incluye_la_categoria_cuando_ya_se_asigno(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()
    categoria_id = cliente_con_correo_falso.post(
        "/api/categorias",
        json={"usuario_id": usuario.id, "nombre": "Alimentación", "color_hex": "#2563EB"},
    ).json()["id"]
    comercio_id = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    ).json()[0]["comercio_id"]
    cliente_con_correo_falso.post(
        f"/api/comercios/{comercio_id}/categoria",
        json={"usuario_id": usuario.id, "categoria_id": categoria_id},
    )

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/reportes/movimientos.csv",
        params={"usuario_id": usuario.id},
    )

    texto = respuesta.text.lstrip("﻿")
    filas = list(csv.reader(io.StringIO(texto)))
    assert filas[1][2] == "Alimentación"


def test_exportar_excel_trae_los_movimientos_reales(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/reportes/movimientos.xlsx",
        params={"usuario_id": usuario.id},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "gastonomo-movimientos.xlsx" in respuesta.headers["content-disposition"]

    libro = load_workbook(io.BytesIO(respuesta.content))
    hoja = libro.active
    encabezado = [c.value for c in hoja[1]]
    assert encabezado[:4] == ["Fecha", "Comercio", "Categoría", "Monto"]
    assert hoja.max_row == 2, "una sola fila de datos: el correo de PriceSmart no es de BAC"
    assert hoja.cell(row=2, column=2).value == "WALMART SAN SEBASTIAN"
    assert float(hoja.cell(row=2, column=4).value) == 7870.00


def test_exportar_pdf_devuelve_un_pdf_valido(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/reportes/resumen.pdf",
        params={"usuario_id": usuario.id},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "gastonomo-reporte.pdf" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"%PDF-")
    assert len(respuesta.content) > 500


class _ProveedorSinComprobantes:
    """Como `ProveedorDeCorreoFalso`, pero su bandeja nunca tiene nada de BAC."""

    def __init__(self) -> None:
        self.direccion = "vacio@ejemplo.cr"

    def url_de_autorizacion(self, estado: str) -> str:
        return f"https://proveedor.falso/autorizar?state={estado}"

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        return TokensDeCorreo(
            token_acceso="acceso-vacio",
            token_refresco="refresco-vacio",
            expira_en=datetime.now(UTC) + timedelta(hours=1),
        )

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        return self.intercambiar_codigo("")

    def obtener_direccion(self, token_acceso: str) -> str:
        return self.direccion

    def listar_mensajes_recientes(
        self, token_acceso: str, limite: int, remitente_contiene: str | None = None
    ) -> list[MensajeResumido]:
        return []

    def obtener_cuerpo_de_mensaje(self, token_acceso: str, identificador: str) -> str:
        raise AssertionError("no debería llamarse: nunca hay mensajes que leer")


def test_exportar_pdf_sin_comprobantes_reconocidos_da_409(
    cliente: TestClient, sesion: Session, usuario: Usuario
) -> None:
    """Sin ningún comprobante de BAC reconocido, el reporte no se arma -da 409, no un PDF vacío."""
    proveedor_vacio = _ProveedorSinComprobantes()
    app.dependency_overrides[obtener_servicio_de_cuentas_correo] = lambda: CuentaCorreoService(
        CuentaCorreoRepository(sesion),
        UsuarioRepository(sesion),
        {ProveedorCorreo.OUTLOOK: proveedor_vacio},
        ComprobanteRepository(sesion),
    )
    try:
        estado = _codificar_estado(usuario.id)
        vinculada = cliente.get(
            "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
        ).json()

        respuesta = cliente.get(
            f"/api/cuentas-correo/{vinculada['id']}/reportes/resumen.pdf",
            params={"usuario_id": usuario.id},
        )

        assert respuesta.status_code == 409
        assert "no hay comprobantes" in respuesta.json()["detalle"].lower()
    finally:
        del app.dependency_overrides[obtener_servicio_de_cuentas_correo]


def _cuerpo_bac(
    comercio: str,
    fecha: str,
    monto: str,
    moneda: str = "CRC",
    ciudad_pais: str = "SAN JOSE, Costa Rica",
) -> str:
    """Arma el cuerpo de una notificación de BAC sintética, con el mismo formato real."""
    return (
        f"Notificaci?n de transacci?n {comercio}\n"
        "From Notificaci?n BAC <NotificacionBAC@baccredomatic.cr>\n"
        "Hola PERSONA DE PRUEBA\n"
        "A continuaci?n le detallamos la transacci?n realizada:\n"
        f"Comercio: {comercio}\n"
        f"Ciudad y pa?s: {ciudad_pais}\n"
        f"Fecha: {fecha}\n"
        "AMEX: ***********4321\n"
        "Autorizaci?n: 100200\n"
        "Referencia: 99887766\n"
        "Tipo de Transacci?n: COMPRA\n"
        f"Monto: {moneda} {monto}\n"
    )


class _ProveedorConMensajesPersonalizados:
    """Como `ProveedorDeCorreoFalso`, pero con los mensajes de BAC que la prueba elija."""

    def __init__(self, cuerpos: dict[str, str]) -> None:
        self.direccion = "titular@ejemplo.cr"
        self._cuerpos = cuerpos

    def url_de_autorizacion(self, estado: str) -> str:
        return f"https://proveedor.falso/autorizar?state={estado}"

    def intercambiar_codigo(self, codigo: str) -> TokensDeCorreo:
        return TokensDeCorreo(
            token_acceso="acceso",
            token_refresco="refresco",
            expira_en=datetime.now(UTC) + timedelta(hours=1),
        )

    def refrescar(self, token_refresco: str) -> TokensDeCorreo:
        return self.intercambiar_codigo("")

    def obtener_direccion(self, token_acceso: str) -> str:
        return self.direccion

    def listar_mensajes_recientes(
        self, token_acceso: str, limite: int, remitente_contiene: str | None = None
    ) -> list[MensajeResumido]:
        return [
            MensajeResumido(
                identificador=id_,
                remitente="NotificacionBAC@baccredomatic.cr",
                asunto="",
                recibido_en=None,
            )
            for id_ in self._cuerpos
        ][:limite]

    def obtener_cuerpo_de_mensaje(self, token_acceso: str, identificador: str) -> str:
        return self._cuerpos[identificador]


def _cliente_con_mensajes(cliente: TestClient, sesion: Session, cuerpos: dict[str, str]) -> None:
    """Reemplaza el servicio de cuentas de correo por uno con estos mensajes exactos."""
    proveedor = _ProveedorConMensajesPersonalizados(cuerpos)
    app.dependency_overrides[obtener_servicio_de_cuentas_correo] = lambda: CuentaCorreoService(
        CuentaCorreoRepository(sesion),
        UsuarioRepository(sesion),
        {ProveedorCorreo.OUTLOOK: proveedor},
        ComprobanteRepository(sesion),
    )


def test_exportar_pdf_prefiere_colones_cuando_el_mes_tiene_dos_monedas(
    cliente: TestClient, sesion: Session, usuario: Usuario
) -> None:
    """Regresión: el mismo bug que Resumen.tsx, pero del lado del PDF.

    `resumen.por_mes` trae una fila por moneda; si el mes más reciente tuvo
    gasto en colones y en dólares, el reporte no puede elegir la moneda por
    orden alfabético (USD antes que CRC) -tiene que preferir colones.
    """
    _cliente_con_mensajes(
        cliente,
        sesion,
        {
            "1": _cuerpo_bac("DIP DEEP BURGER", "Set 1, 2026 , 17:14", "7,600.00", moneda="CRC"),
            "2": _cuerpo_bac("UBER BV USD-USD COSTA", "Set 1, 2026 , 20:50", "6.00", moneda="USD"),
        },
    )
    try:
        estado = _codificar_estado(usuario.id)
        vinculada = cliente.get(
            "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
        ).json()

        # El PDF que arma reportlab sale comprimido (Flate); en vez de
        # parsear bytes binarios, se espía con qué moneda y total se llamó
        # al armador -eso es exactamente lo que la selección del período
        # tenía que decidir bien.
        with patch(
            "app.presentation.routers.reportes._pdf_de_resumen", wraps=_pdf_de_resumen
        ) as espia:
            respuesta = cliente.get(
                f"/api/cuentas-correo/{vinculada['id']}/reportes/resumen.pdf",
                params={"usuario_id": usuario.id},
            )

        assert respuesta.status_code == 200
        argumentos = espia.call_args.kwargs
        assert argumentos["moneda"] == "CRC"
        assert argumentos["total_mes"] == Decimal("7600.00")
    finally:
        del app.dependency_overrides[obtener_servicio_de_cuentas_correo]


def test_exportar_csv_neutraliza_un_comercio_que_empieza_como_formula(
    cliente: TestClient, sesion: Session, usuario: Usuario
) -> None:
    """Regresión: CSV Injection (OWASP) -un comercio no es un dato que la app controle.

    El nombre del comercio viene tal cual del cuerpo de un correo real; si
    empezara con '=', Excel lo interpretaría como fórmula al abrir el CSV.
    """
    _cliente_con_mensajes(
        cliente,
        sesion,
        {"1": _cuerpo_bac("=cmd|'/c calc'!A1", "Ago 30, 2026 , 13:27", "1,000.00")},
    )
    try:
        estado = _codificar_estado(usuario.id)
        vinculada = cliente.get(
            "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
        ).json()

        respuesta = cliente.get(
            f"/api/cuentas-correo/{vinculada['id']}/reportes/movimientos.csv",
            params={"usuario_id": usuario.id},
        )

        texto = respuesta.text.lstrip("﻿")
        filas = list(csv.reader(io.StringIO(texto)))
        comercio_exportado = filas[1][1]

        assert comercio_exportado.startswith("'"), (
            "debe quedar neutralizado con una comilla adelante"
        )
        assert comercio_exportado == "'=cmd|'/c calc'!A1"
    finally:
        del app.dependency_overrides[obtener_servicio_de_cuentas_correo]


def test_exportar_excel_neutraliza_un_comercio_que_empieza_como_formula(
    cliente: TestClient, sesion: Session, usuario: Usuario
) -> None:
    _cliente_con_mensajes(
        cliente,
        sesion,
        {"1": _cuerpo_bac("+1234567 SOSPECHOSO", "Ago 30, 2026 , 13:27", "1,000.00")},
    )
    try:
        estado = _codificar_estado(usuario.id)
        vinculada = cliente.get(
            "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
        ).json()

        respuesta = cliente.get(
            f"/api/cuentas-correo/{vinculada['id']}/reportes/movimientos.xlsx",
            params={"usuario_id": usuario.id},
        )

        libro = load_workbook(io.BytesIO(respuesta.content))
        hoja = libro.active
        comercio_exportado = hoja.cell(row=2, column=2).value

        assert comercio_exportado == "'+1234567 SOSPECHOSO"
    finally:
        del app.dependency_overrides[obtener_servicio_de_cuentas_correo]
