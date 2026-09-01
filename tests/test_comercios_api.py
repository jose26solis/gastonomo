"""La API del catálogo de comercios y su clasificación por titular."""

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


def test_comercios_clasificados_agrupa_los_comprobantes_reales(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    """El doble de prueba trae un correo de BAC (WALMART) y uno de PriceSmart (filtrado antes)."""
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    comercios = respuesta.json()
    assert len(comercios) == 1
    assert comercios[0]["nombre"] == "WALMART SAN SEBASTIAN"
    assert comercios[0]["categoria_id"] is None
    assert comercios[0]["total"] == "7870.00"


def test_asignar_categoria_a_un_comercio_y_verla_en_la_clasificacion(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")

    comercios = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    ).json()
    comercio_id = comercios[0]["comercio_id"]

    asignacion = cliente_con_correo_falso.post(
        f"/api/comercios/{comercio_id}/categoria",
        json={"usuario_id": usuario.id, "categoria_id": categoria_id},
    )
    assert asignacion.status_code == 200
    assert asignacion.json()["nombre"] == "WALMART SAN SEBASTIAN"

    comercios_despues = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    ).json()
    assert comercios_despues[0]["categoria_id"] == categoria_id
    assert comercios_despues[0]["categoria_nombre"] == "Alimentación"


def test_asignar_categoria_padre_a_un_comercio_da_409(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()
    padre_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")
    cliente_con_correo_falso.post(
        "/api/categorias",
        json={
            "usuario_id": usuario.id,
            "nombre": "Supermercado",
            "color_hex": "#16A34A",
            "categoria_padre_id": padre_id,
        },
    )

    comercios = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comercios", params={"usuario_id": usuario.id}
    ).json()
    comercio_id = comercios[0]["comercio_id"]

    respuesta = cliente_con_correo_falso.post(
        f"/api/comercios/{comercio_id}/categoria",
        json={"usuario_id": usuario.id, "categoria_id": padre_id},
    )

    assert respuesta.status_code == 409


def test_asignar_categoria_a_un_comercio_inexistente_da_404(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    categoria_id = _crear_categoria(cliente_con_correo_falso, usuario.id, "Alimentación")

    respuesta = cliente_con_correo_falso.post(
        "/api/comercios/9999/categoria",
        json={"usuario_id": usuario.id, "categoria_id": categoria_id},
    )

    assert respuesta.status_code == 404
