"""La API de carga manual de comprobantes: previsualizar el texto pegado y
confirmarlo como una Compra real -para bancos sin lector exacto."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.data.models.usuario import Usuario


def test_analizar_lee_lo_que_encuentra_en_el_texto(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/comprobantes-manuales/analizar",
        json={
            "banco": "Banco Popular",
            "texto": "Comercio: AUTOMERCADO ESCAZU\nMonto: CRC 15,420.50\nFecha: 05/09/2026",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["banco"] == "Banco Popular"
    assert cuerpo["comercio"] == "AUTOMERCADO ESCAZU"
    assert cuerpo["moneda"] == "CRC"
    assert Decimal(cuerpo["monto"]) == Decimal("15420.50")


def test_analizar_un_texto_sin_nada_reconocible_no_revienta(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/comprobantes-manuales/analizar",
        json={"banco": "Banco X", "texto": "hola, como estas"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["comercio"] is None
    assert cuerpo["monto"] is None
    assert cuerpo["confianza"] == 0.0


def test_analizar_sin_sesion_se_traduce_a_401(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/comprobantes-manuales/analizar",
        json={"banco": "Banco X", "texto": "algo"},
        headers={"Authorization": ""},
    )

    assert respuesta.status_code == 401


def test_crear_compra_manual_de_punta_a_punta(cliente: TestClient, usuario: Usuario) -> None:
    respuesta = cliente.post(
        "/api/compras/manual",
        json={
            "usuario_id": usuario.id,
            "banco": "Banco Popular",
            "comercio": "AUTOMERCADO ESCAZU",
            "fecha": "2026-09-05",
            "moneda": "CRC",
            "monto": "15420.50",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["comercio_nombre"] == "AUTOMERCADO ESCAZU"
    assert cuerpo["total"] == "15420.50"
    assert cuerpo["origen"] == "MANUAL"
    assert cuerpo["requiere_revision"] is True, "sin método de pago ni categoría"

    listado = cliente.get("/api/compras", params={"usuario_id": usuario.id})
    assert any(c["id"] == cuerpo["id"] for c in listado.json())


def test_crear_compra_manual_con_metodo_de_pago_y_categoria_explicitos(
    cliente: TestClient, usuario: Usuario
) -> None:
    metodo_pago = cliente.post(
        "/api/metodos-pago",
        json={"usuario_id": usuario.id, "alias": "Efectivo", "tipo": "EFECTIVO"},
    ).json()
    categoria = cliente.post(
        "/api/categorias",
        json={"usuario_id": usuario.id, "nombre": "Alimentación", "color_hex": "#16A34A"},
    ).json()

    respuesta = cliente.post(
        "/api/compras/manual",
        json={
            "usuario_id": usuario.id,
            "banco": "Banco Popular",
            "comercio": "AUTOMERCADO ESCAZU",
            "fecha": "2026-09-05",
            "moneda": "CRC",
            "monto": "15420.50",
            "metodo_pago_id": metodo_pago["id"],
            "categoria_id": categoria["id"],
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["metodo_pago_alias"] == "Efectivo"
    assert cuerpo["categoria_nombre"] == "Alimentación"
    assert cuerpo["requiere_revision"] is False


def test_crear_compra_manual_de_otro_titular_se_traduce_a_403(
    cliente: TestClient, usuario: Usuario, sesion
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona", correo="otra-manual@gastonomo.cr", contrasena_hash="hash"
    )
    sesion.add(otro)
    sesion.commit()

    respuesta = cliente.post(
        "/api/compras/manual",
        json={
            "usuario_id": otro.id,
            "banco": "Banco Popular",
            "comercio": "AUTOMERCADO ESCAZU",
            "fecha": "2026-09-05",
            "moneda": "CRC",
            "monto": "15420.50",
        },
    )

    assert respuesta.status_code == 403


def test_crear_compra_manual_con_metodo_de_pago_que_no_existe_da_404(
    cliente: TestClient, usuario: Usuario
) -> None:
    respuesta = cliente.post(
        "/api/compras/manual",
        json={
            "usuario_id": usuario.id,
            "banco": "Banco Popular",
            "comercio": "AUTOMERCADO ESCAZU",
            "fecha": "2026-09-05",
            "moneda": "CRC",
            "monto": "15420.50",
            "metodo_pago_id": 999999,
        },
    )

    assert respuesta.status_code == 404
