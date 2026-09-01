"""La API de exportación de reportes."""

import csv
import io

from fastapi.testclient import TestClient

from app.data.models.usuario import Usuario
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
