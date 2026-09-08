"""La API de la bitácora de trazabilidad de una compra."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.business.services.bitacora_service import Actor, BitacoraComprasService
from app.data.models.compra import Compra
from app.data.models.usuario import Usuario
from app.data.repositories.bitacora_repository import BitacoraRepository
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_bitacora
from app.presentation.routers.cuentas_correo import _codificar_estado


class _ColeccionFalsa:
    """Mismo doble mínimo que `test_bitacora_service.py` -in-memory, sin red."""

    def __init__(self) -> None:
        self.documentos: dict[int, dict] = {}

    def find_one(self, filtro: dict, proyeccion: dict | None = None):
        return self.documentos.get(filtro["compra_id"])

    def update_one(self, filtro: dict, actualizacion: dict, upsert: bool = False) -> None:
        compra_id = filtro["compra_id"]
        documento = self.documentos.setdefault(
            compra_id, {**actualizacion.get("$setOnInsert", {}), "eventos": []}
        )
        documento.update(actualizacion.get("$set", {}))
        if "$push" in actualizacion:
            documento["eventos"].append(actualizacion["$push"]["eventos"])


def test_bitacora_de_una_compra_real(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    coleccion = _ColeccionFalsa()
    servicio = BitacoraComprasService(BitacoraRepository(coleccion))
    app.dependency_overrides[obtener_servicio_de_bitacora] = lambda: servicio
    try:
        estado = _codificar_estado(usuario.id)
        cliente_con_correo_falso.get(
            "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
        )
        # Vincular el buzón no sincroniza solo -eso pasa al pedir el
        # resumen, igual que en el resto de las pruebas de este archivo.
        cliente_con_correo_falso.get(
            "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
        )
        compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()
        assert compra is not None, "el comprobante de prueba debió conciliar una compra real"

        servicio.registrar_evento(
            compra_id=compra.id,
            usuario_id=usuario.id,
            estado_actual="REGISTRADA",
            tipo="PARSEO_COMPROBANTE",
            datos={"confianza": 1.0},
            actor=Actor(tipo="SERVICIO", nombre="ingesta-correo"),
        )

        respuesta = cliente_con_correo_falso.get(
            f"/api/compras/{compra.id}/bitacora", params={"usuario_id": usuario.id}
        )

        assert respuesta.status_code == 200
        eventos = respuesta.json()
        assert len(eventos) == 1
        assert eventos[0]["tipo"] == "PARSEO_COMPROBANTE"
        assert eventos[0]["datos"] == {"confianza": 1.0}
    finally:
        del app.dependency_overrides[obtener_servicio_de_bitacora]


def test_bitacora_de_una_compra_sin_eventos_da_404(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    estado = _codificar_estado(usuario.id)
    cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    )
    cliente_con_correo_falso.get(
        "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
    )
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()
    assert compra is not None

    # Sin override: usa el BitacoraComprasService(None) por default de `cliente`.
    respuesta = cliente_con_correo_falso.get(
        f"/api/compras/{compra.id}/bitacora", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 404


def test_bitacora_de_una_compra_de_otro_titular_se_traduce_a_403(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona", correo="otra-compras@gastonomo.cr", contrasena_hash="hash"
    )
    sesion.add(otro)
    sesion.commit()

    respuesta = cliente_con_correo_falso.get(
        "/api/compras/1/bitacora", params={"usuario_id": otro.id}
    )

    assert respuesta.status_code == 403


def test_bitacora_de_una_compra_que_no_existe_da_404(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente_con_correo_falso.get(
        "/api/compras/999999/bitacora", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 404


def _vincular_y_sincronizar(cliente: TestClient, usuario: Usuario) -> None:
    estado = _codificar_estado(usuario.id)
    cliente.get("/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado})
    cliente.get("/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id})


def test_listar_compras_del_titular(cliente_con_correo_falso: TestClient, usuario: Usuario) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)

    respuesta = cliente_con_correo_falso.get("/api/compras", params={"usuario_id": usuario.id})

    assert respuesta.status_code == 200
    compras = respuesta.json()
    assert len(compras) == 1
    assert compras[0]["comercio_nombre"] == "WALMART SAN SEBASTIAN"
    assert compras[0]["total"] == "7870.00"
    assert compras[0]["requiere_revision"] is True, "sin método de pago ni categoría todavía"


def test_listar_compras_filtra_por_requiere_revision(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)

    todas = cliente_con_correo_falso.get("/api/compras", params={"usuario_id": usuario.id})
    resueltas = cliente_con_correo_falso.get(
        "/api/compras", params={"usuario_id": usuario.id, "requiere_revision": False}
    )
    pendientes = cliente_con_correo_falso.get(
        "/api/compras", params={"usuario_id": usuario.id, "requiere_revision": True}
    )

    assert len(todas.json()) == 1
    assert len(resueltas.json()) == 0
    assert len(pendientes.json()) == 1


def test_detalle_de_una_compra(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()

    respuesta = cliente_con_correo_falso.get(
        f"/api/compras/{compra.id}", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == compra.id
    assert cuerpo["metodo_pago_id"] is None
    assert cuerpo["categoria_id"] is None


def test_detalle_de_compra_de_otro_titular_da_404(cliente: TestClient, usuario: Usuario) -> None:
    respuesta = cliente.get("/api/compras/999999", params={"usuario_id": usuario.id})

    assert respuesta.status_code == 404


def test_resolver_revision_asigna_metodo_de_pago(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()
    metodo_pago = cliente_con_correo_falso.post(
        "/api/metodos-pago",
        json={
            "usuario_id": usuario.id,
            "alias": "Amex",
            "tipo": "CREDITO",
            "ultimos_cuatro": "4321",
        },
    ).json()

    respuesta = cliente_con_correo_falso.post(
        f"/api/compras/{compra.id}/resolver",
        params={"usuario_id": usuario.id},
        json={"metodo_pago_id": metodo_pago["id"]},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["metodo_pago_id"] == metodo_pago["id"]
    assert cuerpo["metodo_pago_alias"] == "Amex"
    assert cuerpo["requiere_revision"] is True, "todavía sin categoría"


def test_resolver_revision_sin_campos_da_422(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()

    respuesta = cliente_con_correo_falso.post(
        f"/api/compras/{compra.id}/resolver", params={"usuario_id": usuario.id}, json={}
    )

    assert respuesta.status_code == 422


def test_listar_compras_de_otro_titular_se_traduce_a_403(
    cliente: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente.get("/api/compras", params={"usuario_id": usuario.id + 1})

    assert respuesta.status_code == 403


def test_detalle_de_una_compra_trae_sus_renglones(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()

    respuesta = cliente_con_correo_falso.get(
        f"/api/compras/{compra.id}", params={"usuario_id": usuario.id}
    )

    cuerpo = respuesta.json()
    assert len(cuerpo["lineas"]) == 1
    assert Decimal(cuerpo["lineas"][0]["subtotal"]) == Decimal("7870.00")
    assert cuerpo["lineas"][0]["categoria_id"] is None


def test_desglosar_una_compra_en_dos_categorias(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()
    alimentacion = cliente_con_correo_falso.post(
        "/api/categorias",
        json={"usuario_id": usuario.id, "nombre": "Alimentación", "color_hex": "#16A34A"},
    ).json()
    limpieza = cliente_con_correo_falso.post(
        "/api/categorias",
        json={"usuario_id": usuario.id, "nombre": "Limpieza", "color_hex": "#0EA5E9"},
    ).json()

    respuesta = cliente_con_correo_falso.post(
        f"/api/compras/{compra.id}/desglosar",
        params={"usuario_id": usuario.id},
        json={
            "lineas": [
                {
                    "descripcion": "Víveres",
                    "cantidad": "1",
                    "precio_unitario": "5000.00",
                    "categoria_id": alimentacion["id"],
                },
                {
                    "descripcion": "Artículos de limpieza",
                    "cantidad": "1",
                    "precio_unitario": "2870.00",
                    "categoria_id": limpieza["id"],
                },
            ]
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["lineas"]) == 2
    assert cuerpo["categoria_nombre"] == "Varias categorías"
    assert {linea["descripcion"] for linea in cuerpo["lineas"]} == {
        "Víveres",
        "Artículos de limpieza",
    }


def test_desglosar_con_suma_que_no_calza_da_422(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()

    respuesta = cliente_con_correo_falso.post(
        f"/api/compras/{compra.id}/desglosar",
        params={"usuario_id": usuario.id},
        json={
            "lineas": [{"descripcion": "Víveres", "cantidad": "1", "precio_unitario": "5000.00"}]
        },
    )

    assert respuesta.status_code == 422


def test_desglosar_sin_renglones_da_422_de_forma(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion: Session
) -> None:
    """El mínimo de un renglón lo exige el esquema (`Field(min_length=1)`), antes
    de que el servicio llegue a correr -por eso 422 de forma, no de negocio."""
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)
    compra = sesion.scalars(select(Compra).where(Compra.usuario_id == usuario.id)).first()

    respuesta = cliente_con_correo_falso.post(
        f"/api/compras/{compra.id}/desglosar",
        params={"usuario_id": usuario.id},
        json={"lineas": []},
    )

    assert respuesta.status_code == 422


def test_gasto_por_categoria_no_queda_enmascarado_por_el_detalle(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    """`/gasto-por-categoria` está declarado antes de `/{compra_id}` en el
    router -si el orden se invirtiera, FastAPI intentaría convertir
    "gasto-por-categoria" a `int` para `compra_id` y esto daría 422, no 200."""
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)

    respuesta = cliente_con_correo_falso.get(
        "/api/compras/gasto-por-categoria", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    gastos = respuesta.json()
    assert len(gastos) == 1
    assert gastos[0]["categoria_id"] is None
    assert gastos[0]["categoria_nombre"] == "Sin categoría", "sin categoria todavia al conciliar"
    # No comparo contra el string exacto: la escala del producto es la de
    # `tipo_cambio_aplicado` (Numeric(14, 6)), no la de `total` -"7870.000000"
    # es el mismo monto que "7870.00", solo con más ceros de precisión.
    assert Decimal(gastos[0]["total"]) == Decimal("7870.00")


def test_gasto_por_categoria_filtra_por_comercio_sin_resultados(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    _vincular_y_sincronizar(cliente_con_correo_falso, usuario)

    respuesta = cliente_con_correo_falso.get(
        "/api/compras/gasto-por-categoria",
        params={"usuario_id": usuario.id, "comercio_id": 999999},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == []
