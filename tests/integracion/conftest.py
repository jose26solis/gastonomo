"""Fixtures de las pruebas de integración: un postgres:16-alpine real, por sesión.

El contenedor se levanta una sola vez para toda la corrida -arrancarlo tarda
varios segundos, y nada de lo que estas pruebas verifican depende de que sea
uno nuevo por prueba- pero cada prueba recibe su propio esquema, creado y
destruido alrededor de ella, para no arrastrar datos de una prueba a la
siguiente.

Si Docker no está disponible, `postgres_url` se salta con `pytest.skip` en
vez de fallar: es lo que le permite a `pytest` (sin filtrar por marcador)
seguir corriendo en cualquier máquina, incluida la de quien no tiene Docker
instalado. En el CI sí hay Docker, y ahí corren de verdad -ver `ci.yml`.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.data.models.base import Base


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    try:
        contenedor = PostgresContainer("postgres:16-alpine", driver="psycopg")
        contenedor.start()
    except Exception as error:  # cualquier fallo acá significa "no hay Docker"
        pytest.skip(
            f"No se pudo levantar Postgres con Testcontainers (¿Docker corriendo?): {error}"
        )
    try:
        yield contenedor.get_connection_url()
    finally:
        contenedor.stop()


@pytest.fixture
def sesion_postgres(postgres_url: str) -> Iterator[Session]:
    """Esquema recién creado en el Postgres real del contenedor, para una sola prueba."""
    motor = create_engine(postgres_url)
    Base.metadata.create_all(bind=motor)
    fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    try:
        with fabrica() as sesion:
            yield sesion
    finally:
        Base.metadata.drop_all(bind=motor)
        motor.dispose()
