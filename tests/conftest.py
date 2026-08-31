"""Fixtures compartidas.

Las pruebas corren contra SQLite en memoria: no tocan ningun archivo ni
necesitan infraestructura, y cada prueba arranca con la base vacia.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.config.database import obtener_sesion
from app.data.models.base import Base
from app.data.models.enums import Moneda, ProveedorCorreo
from app.data.models.usuario import Usuario
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository
from app.main import app
from app.presentation.dependencies import obtener_servicio_de_cuentas_correo
from tests.apoyos_correo import ProveedorDeCorreoFalso


@pytest.fixture
def sesion() -> Iterator[Session]:
    """Base limpia en memoria para una sola prueba.

    StaticPool obliga a que todas las conexiones compartan la misma base en
    memoria; sin el, cada conexion nueva arrancaria con una base vacia distinta.
    """
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=motor)
    fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    with fabrica() as sesion_de_prueba:
        yield sesion_de_prueba
    Base.metadata.drop_all(bind=motor)


@pytest.fixture
def usuario(sesion: Session) -> Usuario:
    """Titular dueno de los datos de la prueba."""
    titular = Usuario(
        nombre_completo="Titular de prueba",
        correo="titular@gastonomo.cr",
        contrasena_hash="hash-de-prueba",
        moneda_preferida=Moneda.CRC,
    )
    sesion.add(titular)
    sesion.commit()
    return titular


@pytest.fixture
def cliente(sesion: Session) -> Iterator[TestClient]:
    """Cliente HTTP contra la app real, con la base de la prueba inyectada.

    El cliente se usa sin `with` a proposito: asi no se dispara el ciclo de vida
    de la aplicacion, que crearia el archivo SQLite de desarrollo. Las tablas de
    la prueba ya las creo la fixture `sesion`, en memoria.
    """
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def proveedor_correo_falso() -> ProveedorDeCorreoFalso:
    """Doble de prueba de un proveedor de correo, sin tocar la red."""
    return ProveedorDeCorreoFalso()


@pytest.fixture
def cliente_con_correo_falso(
    cliente: TestClient, sesion: Session, proveedor_correo_falso: ProveedorDeCorreoFalso
) -> Iterator[TestClient]:
    """Cliente HTTP con Outlook y Gmail reemplazados por un doble de prueba.

    Sirve para probar los endpoints de `/api/cuentas-correo` sin que la
    petición HTTP real salga hacia Microsoft o Google.
    """

    def _armar_servicio() -> CuentaCorreoService:
        return CuentaCorreoService(
            CuentaCorreoRepository(sesion),
            UsuarioRepository(sesion),
            {
                ProveedorCorreo.OUTLOOK: proveedor_correo_falso,
                ProveedorCorreo.GMAIL: proveedor_correo_falso,
            },
        )

    app.dependency_overrides[obtener_servicio_de_cuentas_correo] = _armar_servicio
    yield cliente
    del app.dependency_overrides[obtener_servicio_de_cuentas_correo]
