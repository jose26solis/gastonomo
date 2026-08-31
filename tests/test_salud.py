"""El endpoint que confirma que el sistema esta en linea."""

from fastapi.testclient import TestClient


def test_salud_responde_que_el_sistema_esta_en_linea(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "estado": "OK - sistema en linea",
        "aplicacion": "Gastonomo",
        "version": "0.1.0",
    }
