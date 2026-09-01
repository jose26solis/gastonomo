"""La API de presupuestos, incluido el endpoint que combina límite con gasto real."""

from fastapi.testclient import TestClient

from app.data.models.usuario import Usuario
from app.presentation.routers.cuentas_correo import _codificar_estado


def _crear_categoria(cliente: TestClient, usuario_id: int, nombre: str) -> int:
    respuesta = cliente.post(
        "/api/categorias",
        json={"usuario_id": usuario_id, "nombre": nombre, "color_hex": "#2563EB"},
    )
    assert respuesta.status_code == 201
    return respuesta.json()["id"]


def test_crear_y_listar_presupuesto(cliente_con_correo_falso: TestClient, usuario: Usuario) -> None:
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")

    creacion = cliente_con_correo_falso.post(
        "/api/presupuestos",
        json={
            "usuario_id": usuario.id,
            "categoria_id": categoria_id,
            "anio": 2026,
            "mes": 8,
            "moneda": "CRC",
            "monto_limite": "220000.00",
        },
    )
    assert creacion.status_code == 200
    assert creacion.json()["umbral_alerta"] == 80

    listado = cliente_con_correo_falso.get(
        "/api/presupuestos", params={"usuario_id": usuario.id, "anio": 2026, "mes": 8}
    )
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_crear_presupuesto_con_limite_invalido_da_422(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")

    respuesta = cliente_con_correo_falso.post(
        "/api/presupuestos",
        json={
            "usuario_id": usuario.id,
            "categoria_id": categoria_id,
            "anio": 2026,
            "mes": 8,
            "moneda": "CRC",
            "monto_limite": "-5",
        },
    )

    assert respuesta.status_code == 422


def test_eliminar_presupuesto(cliente_con_correo_falso: TestClient, usuario: Usuario) -> None:
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")
    creacion = cliente_con_correo_falso.post(
        "/api/presupuestos",
        json={
            "usuario_id": usuario.id,
            "categoria_id": categoria_id,
            "anio": 2026,
            "mes": 8,
            "moneda": "CRC",
            "monto_limite": "220000.00",
        },
    ).json()

    respuesta = cliente_con_correo_falso.delete(
        f"/api/presupuestos/{creacion['id']}", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 204
    listado = cliente_con_correo_falso.get(
        "/api/presupuestos", params={"usuario_id": usuario.id, "anio": 2026, "mes": 8}
    ).json()
    assert listado == []


def test_presupuestos_del_periodo_combina_limite_con_gasto_real(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    """El doble de prueba trae un comprobante real de WALMART SAN SEBASTIAN por 7870.00 CRC."""
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")

    # Se necesita clasificar el comercio primero para que el gasto cuente.
    comercios = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    ).json()
    comercio_id = comercios[0]["comercio_id"]
    cliente_con_correo_falso.post(
        f"/api/comercios/{comercio_id}/categoria",
        json={"usuario_id": usuario.id, "categoria_id": categoria_id},
    )

    cliente_con_correo_falso.post(
        "/api/presupuestos",
        json={
            "usuario_id": usuario.id,
            "categoria_id": categoria_id,
            "anio": 2026,
            "mes": 8,
            "moneda": "CRC",
            "monto_limite": "5000.00",
        },
    )

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/presupuestos",
        params={"usuario_id": usuario.id, "anio": 2026, "mes": 8},
    )

    assert respuesta.status_code == 200
    estados = respuesta.json()
    assert len(estados) == 1
    assert estados[0]["categoria_nombre"] == "Alimentación"
    assert estados[0]["monto_consumido"] == "7870.00"
    assert estados[0]["estado"] == "EXCEDIDO"


def test_presupuestos_del_periodo_sin_ningun_presupuesto_devuelve_vacio(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/presupuestos",
        params={"usuario_id": usuario.id, "anio": 2026, "mes": 8},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == []
