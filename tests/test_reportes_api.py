"""La API de exportación de reportes."""

import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.business.services.correo.proveedor import MensajeResumido, TokensDeCorreo
from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.data.models.enums import ProveedorCorreo
from app.data.models.usuario import Usuario
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_cuentas_correo
from app.presentation.routers.cuentas_correo import _codificar_estado


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
