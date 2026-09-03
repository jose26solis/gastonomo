"""La API de vinculación de correo, de punta a punta con un proveedor falso."""

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from app.business.errors import ErrorDeProveedorExterno
from app.business.services.tipo_cambio_service import TipoDeCambio
from app.data.models.comprobante import Comprobante
from app.data.models.enums import Moneda
from app.data.models.usuario import Usuario
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_tipo_cambio
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


def test_probar_conexion_de_una_cuenta_de_otro_titular_da_403(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion
) -> None:
    """`cliente_con_correo_falso` está autenticado como `usuario`; pedir `/probar` con
    el `usuario_id` de otro titular se rechaza en la capa de autenticación, antes de
    que el servicio llegue a mirar si esa cuenta es de ese otro titular. (Ese caso -ya
    autenticado como el titular correcto, pidiendo una cuenta que no es suya- sigue
    cubierto a nivel de servicio en
    test_cuenta_correo_service.py::test_no_deja_ver_una_cuenta_de_otro_titular.)
    """
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

    assert respuesta.status_code == 403


def test_el_resumen_combinado_trae_las_dos_cuentas_marcadas_con_su_origen(
    cliente_con_dos_buzones: TestClient, usuario: Usuario
) -> None:
    """El endpoint sin `cuenta_id` junta el historial de todos los buzones activos.

    Cada comprobante viaja marcado con el proveedor y la dirección de la que
    salió: es el dato que el frontend necesita para poder decir, en la lista
    de movimientos, si esa compra vino del Hotmail o del Gmail.
    """
    estado = _codificar_estado(usuario.id)
    for proveedor in ("outlook", "gmail"):
        cliente_con_dos_buzones.get(
            f"/api/cuentas-correo/{proveedor}/callback", params={"code": "c", "state": estado}
        )

    respuesta = cliente_con_dos_buzones.get(
        "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["comprobantes"]) == 2, "debe combinar los dos buzones, no elegir uno"
    assert {c["proveedor"] for c in cuerpo["comprobantes"]} == {"OUTLOOK", "GMAIL"}
    assert {c["direccion_cuenta"] for c in cuerpo["comprobantes"]} == {
        "titular@hotmail.com",
        "titular@gmail.com",
    }
    assert cuerpo["por_mes"][0]["cantidad_transacciones"] == 2


def test_el_resumen_combinado_sin_cuentas_vinculadas_no_falla(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"comprobantes": [], "por_mes": [], "conversion": None}


def _con_tipo_de_cambio(venta: str = "500.00"):
    """Una *fábrica* de servicio de tipo de cambio fijo, sin red.

    Devuelve un callable y no la instancia porque `dependency_overrides` espera
    algo que FastAPI pueda llamar para resolver la dependencia.
    """

    class _Fijo:
        def obtener(self, fecha=None):
            return TipoDeCambio(fecha=date(2026, 9, 2), compra=Decimal(venta), venta=Decimal(venta))

    return _Fijo


def test_el_resumen_puede_pedirse_convertido_a_una_sola_moneda(
    cliente_con_dos_buzones: TestClient, usuario: Usuario
) -> None:
    """Con `moneda`, todo se pasa a esa moneda y las monedas dejan de separarse.

    El comprobante del doble de prueba es de 7870.00 colones; a 500 por dólar
    son 15.74 dólares por buzón, 31.48 entre los dos.
    """
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _con_tipo_de_cambio()
    try:
        estado = _codificar_estado(usuario.id)
        for proveedor in ("outlook", "gmail"):
            cliente_con_dos_buzones.get(
                f"/api/cuentas-correo/{proveedor}/callback", params={"code": "c", "state": estado}
            )

        respuesta = cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero",
            params={"usuario_id": usuario.id, "moneda": "USD"},
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["por_mes"]) == 1, "convertido, el mes deja de tener una fila por moneda"
    assert cuerpo["por_mes"][0]["moneda"] == "USD"
    assert cuerpo["por_mes"][0]["total"] == "31.48"
    assert cuerpo["conversion"]["venta"] == "500.00", (
        "la tasa usada tiene que viajar en la respuesta"
    )
    # El monto que cobró el banco se conserva, no se pierde al convertir.
    movimiento = cuerpo["comprobantes"][0]
    assert movimiento["monto"] == "15.74"
    assert movimiento["monto_original"] == "7870.00"
    assert movimiento["moneda_original"] == "CRC"


def test_sin_el_parametro_moneda_no_se_convierte_nada(
    cliente_con_dos_buzones: TestClient, usuario: Usuario
) -> None:
    """El comportamiento por defecto no cambia: cada movimiento en su moneda."""
    estado = _codificar_estado(usuario.id)
    cliente_con_dos_buzones.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    )

    cuerpo = cliente_con_dos_buzones.get(
        "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
    ).json()

    assert cuerpo["conversion"] is None
    assert cuerpo["comprobantes"][0]["moneda"] == "CRC"
    assert cuerpo["comprobantes"][0]["monto_original"] is None


def test_al_sincronizar_se_guarda_el_tipo_de_cambio_del_dia(
    cliente_con_dos_buzones: TestClient, usuario: Usuario, sesion
) -> None:
    """Cada comprobante nuevo queda sellado con la tasa vigente al guardarlo.

    Es lo que permite convertirlo después sin pedirle al Banco Central una
    consulta histórica -que necesita suscripción y hoy ni siquiera responde.
    """
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _con_tipo_de_cambio("500.00")
    try:
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/outlook/callback",
            params={"code": "c", "state": _codificar_estado(usuario.id)},
        )
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    fila = sesion.query(Comprobante).first()
    assert fila.tipo_cambio_venta == Decimal("500.0000")
    assert fila.tipo_cambio_fecha == date(2026, 9, 2)


def test_se_convierte_con_la_tasa_guardada_y_no_con_la_de_hoy(
    cliente_con_dos_buzones: TestClient, usuario: Usuario, sesion
) -> None:
    """La tasa sellada gana sobre la del día de la consulta.

    Sin esto, un gasto de hace meses se reexpresaría con la tasa de hoy cada
    vez que se abre la pantalla, y el total del pasado cambiaría solo.
    """
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _con_tipo_de_cambio("500.00")
    try:
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/outlook/callback",
            params={"code": "c", "state": _codificar_estado(usuario.id)},
        )
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    # Hoy la tasa es otra: 1000, el doble de la que se guardó.
    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _con_tipo_de_cambio("1000.00")
    try:
        cuerpo = cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero",
            params={"usuario_id": usuario.id, "moneda": "USD"},
        ).json()
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    # 7870.00 / 500 = 15.74, con la tasa guardada. Con la de hoy serian 7.87.
    assert cuerpo["comprobantes"][0]["monto"] == "15.74"


def test_sin_tasa_guardada_se_cae_a_la_de_hoy(
    cliente_con_dos_buzones: TestClient, usuario: Usuario, sesion
) -> None:
    """Los comprobantes viejos, guardados antes de sellar, siguen funcionando.

    No se les inventa una tasa retroactiva: se convierten con la de hoy, igual
    que antes de este cambio.
    """
    cliente_con_dos_buzones.get(
        "/api/cuentas-correo/outlook/callback",
        params={"code": "c", "state": _codificar_estado(usuario.id)},
    )
    cliente_con_dos_buzones.get(
        "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
    )
    # Se simula un comprobante de los de antes: sin tasa guardada.
    fila = sesion.query(Comprobante).first()
    fila.tipo_cambio_venta = None
    fila.tipo_cambio_fecha = None
    sesion.commit()

    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _con_tipo_de_cambio("1000.00")
    try:
        cuerpo = cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero",
            params={"usuario_id": usuario.id, "moneda": "USD"},
        ).json()
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    assert cuerpo["comprobantes"][0]["monto"] == "7.87", "7870.00 / 1000, la tasa de hoy"


def test_si_no_hay_tipo_de_cambio_la_sincronizacion_no_falla(
    cliente_con_dos_buzones: TestClient, usuario: Usuario, sesion
) -> None:
    """Leer correo no puede depender de que el servicio de moneda responda."""

    class _Caido:
        def obtener(self, fecha=None):
            raise ErrorDeProveedorExterno("ni el BCCR ni Hacienda respondieron")

    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = _Caido
    try:
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/outlook/callback",
            params={"code": "c", "state": _codificar_estado(usuario.id)},
        )
        respuesta = cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    assert respuesta.status_code == 200
    assert len(respuesta.json()["comprobantes"]) == 1, "el gasto se guarda igual"
    assert sesion.query(Comprobante).first().tipo_cambio_venta is None


def test_un_timeout_del_tipo_de_cambio_no_tumba_la_sincronizacion(
    cliente_con_dos_buzones: TestClient, usuario: Usuario, sesion
) -> None:
    """Regresión: un `httpx.ReadTimeout` daba 500 en vez de guardar sin tasa."""

    class _ConTimeout:
        def obtener(self, fecha=None):
            raise httpx.ReadTimeout("read timeout")

    app.dependency_overrides[obtener_servicio_de_tipo_cambio] = lambda: _ConTimeout()
    try:
        cliente_con_dos_buzones.get(
            "/api/cuentas-correo/outlook/callback",
            params={"code": "c", "state": _codificar_estado(usuario.id)},
        )
        respuesta = cliente_con_dos_buzones.get(
            "/api/cuentas-correo/resumen-financiero", params={"usuario_id": usuario.id}
        )
    finally:
        del app.dependency_overrides[obtener_servicio_de_tipo_cambio]

    assert respuesta.status_code == 200
    assert len(respuesta.json()["comprobantes"]) == 1


def test_bancos_detectados_agrupa_por_dominio_y_marca_bac(
    cliente_con_correo_falso: TestClient, usuario: Usuario
) -> None:
    estado = _codificar_estado(usuario.id)
    cliente_con_correo_falso.get(
        "/api/cuentas-correo/outlook/callback", params={"code": "c", "state": estado}
    )

    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo/bancos", params={"usuario_id": usuario.id}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    dominios = {b["dominio"]: b for b in cuerpo}
    assert dominios["baccredomatic.cr"]["es_bac"] is True
    assert dominios["bncr.fi.cr"]["es_bac"] is False
    assert "pricesmart.com" not in dominios


def test_bancos_detectados_de_otro_titular_se_traduce_a_403(
    cliente_con_correo_falso: TestClient, usuario: Usuario, sesion
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona",
        correo="otra-persona-bancos@gastonomo.cr",
        contrasena_hash="hash",
    )
    sesion.add(otro)
    sesion.commit()

    respuesta = cliente_con_correo_falso.get(
        "/api/cuentas-correo/bancos", params={"usuario_id": otro.id}
    )

    assert respuesta.status_code == 403
