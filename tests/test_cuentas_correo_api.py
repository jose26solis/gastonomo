"""La API de vinculación de correo, de punta a punta con un proveedor falso."""

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.data.models.enums import Moneda
from app.data.models.usuario import Usuario
from app.presentation.routers.cuentas_correo import _codificar_estado


def test_iniciar_devuelve_una_url_hacia_el_proveedor_falso(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/iniciar", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["url_autorizacion"].startswith("https://proveedor.falso/autorizar")


def test_el_flujo_completo_de_vinculacion_crea_la_cuenta(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    inicio = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/iniciar", params={"usuario_id": usuario.id}
    )
    url = inicio.json()["url_autorizacion"]
    # Se decodifica la URL para sacar el `state` tal como viajaría de vuelta
    # cuando el proveedor real redirige al navegador a nuestro callback.
    estado = parse_qs(urlparse(url).query)["state"][0]

    callback = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback",
        params={"code": "codigo-de-autorizacion", "state": estado},
    )

    assert callback.status_code == 200
    cuerpo = callback.json()
    assert cuerpo["direccion"] == "titular@ejemplo.cr"
    assert cuerpo["proveedor"] == "OUTLOOK"
    assert cuerpo["estado"] == "ACTIVA"
    assert "token" not in cuerpo, "la respuesta nunca debe traer datos de token"


def test_un_state_invalido_se_traduce_a_422(cliente_con_correo_falso: TestClient) -> None:
    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback",
        params={"code": "codigo-cualquiera", "state": "esto-no-es-un-state-valido"},
    )

    assert respuesta.status_code == 422


def test_listar_muestra_las_cuentas_vinculadas(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    )

    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


def test_probar_conexion_devuelve_los_mensajes(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/probar", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    mensajes = respuesta.json()
    assert len(mensajes) == 1
    assert mensajes[0]["remitente"] == "NotificacionBAC@baccredomatic.cr"


def test_resumen_financiero_devuelve_comprobantes_y_totales(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/resumen-financiero",
        params={"usuario_id": usuario.id},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["comprobantes"]) == 1
    assert len(cuerpo["por_mes"]) == 1
    assert cuerpo["por_mes"][0]["total"] == "7870.00"


def test_sincronizar_trae_lo_nuevo_y_no_repite_en_la_segunda_llamada(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    primera = cliente_con_correo_falso.post(
        f"/api/cuentas-correo/{vinculada['id']}/sincronizar",
        params={"usuario_id": usuario.id},
    )
    segunda = cliente_con_correo_falso.post(
        f"/api/cuentas-correo/{vinculada['id']}/sincronizar",
        params={"usuario_id": usuario.id},
    )

    assert primera.status_code == 200
    assert primera.json()["comprobantes_nuevos"] == 1
    assert primera.json()["comprobantes_totales"] == 1
    assert segunda.json()["comprobantes_nuevos"] == 0
    assert segunda.json()["comprobantes_totales"] == 1


def test_leer_comprobante_devuelve_los_campos_parseados(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/comprobante",
        params={"usuario_id": usuario.id, "mensaje_id": "1"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["banco"] == "BAC Credomatic"
    assert cuerpo["comercio"] == "WALMART SAN SEBASTIAN"
    assert cuerpo["es_compra"] is True
    assert cuerpo["es_confiable"] is True


def test_desvincular_devuelve_204_y_ya_no_aparece_en_el_listado(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.delete(
        f"/api/cuentas-correo/{vinculada['id']}", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 204
    listado = cliente_con_correo_falso.get(
        "/api/cuentas-correo", params={"usuario_id": usuario.id}
    ).json()
    assert listado[0]["estado"] == "DESVINCULADA"


def test_probar_conexion_de_una_cuenta_de_otro_titular_da_404(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona",
        correo="otra-persona-api@gastonomo.cr",
        contrasena_hash="hash",
        moneda_preferida=Moneda.CRC,
    )
    sesion.add(otro)
    sesion.commit()

    estado = _codificar_estado(usuario.id)
    vinculada = cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    ).json()

    respuesta = cliente_con_correo_falso.get(
        f"/api/cuentas-correo/{vinculada['id']}/probar", params={"usuario_id": otro.id}
    )

    assert respuesta.status_code == 404
