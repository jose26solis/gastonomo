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

from app.business.services.auth_service import (
    AuthService,
    IniciarSesionComando,
    RegistrarUsuarioComando,
)
from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.config.database import obtener_sesion
from app.data.models.base import Base
from app.data.models.enums import ProveedorCorreo
from app.data.models.usuario import Usuario
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository
from app.main import app
from app.presentation.dependencies import (
    obtener_servicio_de_cuentas_correo,
    obtener_servicio_de_tipo_cambio,
)
from tests.apoyos_correo import ProveedorDeCorreoFalso

# Contraseña del usuario de la fixture `usuario`. Vive acá -no en `usuario`
# mismo, que solo expone el modelo ya creado- porque `cliente` la necesita
# para iniciar sesión y conseguir un token real sin duplicar el registro.
CONTRASENA_DE_PRUEBA = "contrasena-de-prueba"


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
    """Titular dueno de los datos de la prueba.

    Se crea vía `AuthService.registrar` -la misma ruta que un titular real- en
    vez de insertar la fila a mano: así el hash de la contraseña es uno de
    verdad, y `cliente` puede iniciar sesión con `CONTRASENA_DE_PRUEBA` para
    conseguir un token real sin duplicar cómo se arma uno.
    """
    resultado = AuthService(UsuarioRepository(sesion)).registrar(
        RegistrarUsuarioComando(
            nombre_completo="Titular de prueba",
            correo="titular@gastonomo.cr",
            contrasena=CONTRASENA_DE_PRUEBA,
        )
    )
    return resultado.usuario


@pytest.fixture
def cliente(sesion: Session, usuario: Usuario) -> Iterator[TestClient]:
    """Cliente HTTP contra la app real, con la base de la prueba inyectada.

    Ya autenticado como `usuario` por defecto -es la inmensa mayoría de los
    casos: una prueba que llama un endpoint protegido casi siempre quiere
    probarlo "como este titular", no la falta de sesión. Una prueba que sí
    necesita otra cosa (otro titular, sin token, un token vencido) puede
    pisar el encabezado `Authorization` en la llamada puntual.

    El cliente se usa sin `with` a proposito: asi no se dispara el ciclo de vida
    de la aplicacion, que crearia el archivo SQLite de desarrollo. Las tablas de
    la prueba ya las creo la fixture `sesion`, en memoria.
    """
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    sesion_de_auth = AuthService(UsuarioRepository(sesion)).iniciar_sesion(
        IniciarSesionComando(correo=usuario.correo, contrasena=CONTRASENA_DE_PRUEBA)
    )
    cliente_de_prueba = TestClient(app)
    cliente_de_prueba.headers["Authorization"] = f"Bearer {sesion_de_auth.token}"
    yield cliente_de_prueba
    app.dependency_overrides.clear()


@pytest.fixture
def proveedor_correo_falso() -> ProveedorDeCorreoFalso:
    """Doble de prueba de un proveedor de correo, sin tocar la red."""
    return ProveedorDeCorreoFalso()


def _tipo_de_cambio_de_la_prueba():
    """El servicio de tipo de cambio que la prueba haya sustituido, si sustituyó alguno.

    Estos fixtures arman `CuentaCorreoService` a mano en vez de dejar que lo
    resuelva la inyección de dependencias, así que un
    `dependency_overrides[obtener_servicio_de_tipo_cambio]` puesto por la
    prueba no llegaría solo hasta acá. Por defecto queda en `None`: la mayoría
    de las pruebas no tienen nada que ver con monedas y no deberían necesitar
    un doble para que la sincronización funcione.
    """
    fabrica = app.dependency_overrides.get(obtener_servicio_de_tipo_cambio)
    return fabrica() if fabrica else None


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
            ComprobanteRepository(sesion),
            _tipo_de_cambio_de_la_prueba(),
        )

    app.dependency_overrides[obtener_servicio_de_cuentas_correo] = _armar_servicio
    yield cliente
    del app.dependency_overrides[obtener_servicio_de_cuentas_correo]


@pytest.fixture
def cliente_con_dos_buzones(cliente: TestClient, sesion: Session) -> Iterator[TestClient]:
    """Cliente HTTP con Outlook y Gmail como dos buzones distintos, cada uno con su dirección.

    A diferencia de `cliente_con_correo_falso` -que usa el mismo doble para
    los dos proveedores- acá cada proveedor devuelve una dirección propia,
    que es lo que pasa de verdad cuando alguien vincula su Hotmail y su
    Gmail. Hace falta para probar todo lo que combina varias cuentas: con la
    misma dirección en ambos, la segunda vinculación chocaría contra el
    UNIQUE de `(usuario_id, direccion)`.
    """

    def _armar_servicio() -> CuentaCorreoService:
        return CuentaCorreoService(
            CuentaCorreoRepository(sesion),
            UsuarioRepository(sesion),
            {
                ProveedorCorreo.OUTLOOK: ProveedorDeCorreoFalso(direccion="titular@hotmail.com"),
                ProveedorCorreo.GMAIL: ProveedorDeCorreoFalso(direccion="titular@gmail.com"),
            },
            ComprobanteRepository(sesion),
            _tipo_de_cambio_de_la_prueba(),
        )

    app.dependency_overrides[obtener_servicio_de_cuentas_correo] = _armar_servicio
    yield cliente
    del app.dependency_overrides[obtener_servicio_de_cuentas_correo]
