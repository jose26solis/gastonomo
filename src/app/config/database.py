"""Motor de conexion, sesion por peticion y creacion del esquema."""

from collections.abc import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import obtener_configuracion
from app.data.models.base import Base
from app.data.models.enums import Moneda
from app.data.models.usuario import Usuario

_configuracion = obtener_configuracion()

# check_same_thread solo aplica a SQLite: uvicorn atiende las peticiones en un
# pool de hilos y SQLite, por defecto, prohibe usar la conexion desde otro hilo.
_argumentos_conexion = (
    {"check_same_thread": False} if _configuracion.url_base_datos.startswith("sqlite") else {}
)

motor = create_engine(_configuracion.url_base_datos, connect_args=_argumentos_conexion)

FabricaDeSesiones = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def crear_tablas() -> None:
    """Crea el esquema si no existe.

    Sirve para el Laboratorio 1. Cuando el proyecto pase a PostgreSQL, este paso
    lo reemplazan las migraciones de Alembic descritas en el ADR-001.
    """
    Base.metadata.create_all(bind=motor)


def sembrar_usuario_de_demostracion() -> None:
    """Deja creado el usuario 1 para poder probar la API sin pantalla de registro.

    El registro de cuentas es trabajo de un laboratorio posterior; mientras tanto
    este usuario es el dueno de las categorias que se creen desde Swagger o curl.
    """
    with FabricaDeSesiones() as sesion:
        if sesion.scalars(select(Usuario).limit(1)).first() is not None:
            return
        sesion.add(
            Usuario(
                nombre_completo="Usuario de demostracion",
                correo="demo@gastonomo.cr",
                contrasena_hash="pendiente-laboratorio-de-autenticacion",
                moneda_preferida=Moneda.CRC,
            )
        )
        sesion.commit()


def obtener_sesion() -> Iterator[Session]:
    """Entrega una sesion por peticion y la cierra siempre, pase lo que pase.

    Nunca confirma: el commit es responsabilidad de la capa de negocio, que es la
    unica que sabe si la operacion completa termino bien.
    """
    sesion = FabricaDeSesiones()
    try:
        yield sesion
    finally:
        sesion.close()
