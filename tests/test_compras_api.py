"""La API de la bitácora de trazabilidad de una compra."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.business.services.bitacora_service import Actor, BitacoraComprasService
from app.data.models.compra import Compra
from app.data.models.usuario import Usuario
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
    servicio = BitacoraComprasService(coleccion)
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
