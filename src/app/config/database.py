"""Motor de conexion, sesion por peticion y creacion del esquema."""

from collections.abc import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.business.seguridad.contrasenas import hashear_contrasena
from app.config.settings import obtener_configuracion
from app.data.models.base import Base
from app.data.models.enums import Moneda
from app.data.models.usuario import Usuario

# Solo para una base recién creada, en una instalación nueva -no es la
# contraseña de ninguna cuenta real ya existente (ver la nota de migración en
# el README, sección "Registro y varios usuarios").
_CORREO_DEMOSTRACION = "demo@gastonomo.cr"
_CONTRASENA_DEMOSTRACION = "demo1234"

_configuracion = obtener_configuracion()

# check_same_thread solo aplica a SQLite: uvicorn atiende las peticiones en un
# pool de hilos y SQLite, por defecto, prohibe usar la conexion desde otro hilo.
_argumentos_conexion = (
    {"check_same_thread": False} if _configuracion.url_base_datos.startswith("sqlite") else {}
)

motor = create_engine(_configuracion.url_base_datos, connect_args=_argumentos_conexion)

FabricaDeSesiones = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def crear_tablas() -> None:
    """Crea el esquema si no existe, en SQLite o en PostgreSQL según `url_base_datos`.

    No hay migraciones versionadas para este esquema todavía: `create_all`
    crea lo que falte pero nunca altera una columna existente, así que un
    cambio de modelo no se propaga solo a una base que ya tenía la tabla
    vieja. Mientras el proyecto siga en una sola persona por ambiente esto
    alcanza; herramientas como Alembic entran cuando eso deje de ser cierto.
    """
    Base.metadata.create_all(bind=motor)


def sembrar_usuario_de_demostracion() -> None:
    """Deja creado un usuario de prueba en una base recién creada, con contraseña real.

    Solo corre en una base vacía (ver el `if` de abajo): en cualquier base que
    ya tenga usuarios -como la de quien ya venía usando la app antes de que
    existiera el login- no toca nada. Antes esto sembraba un usuario con un
    `contrasena_hash` que no era un hash de nada ("pendiente-laboratorio-de-
    autenticacion"): servía mientras el `usuario_id` se escribía a mano en la
    URL, pero con login real ese valor nunca calzaría con ninguna contraseña.
    """
    with FabricaDeSesiones() as sesion:
        if sesion.scalars(select(Usuario).limit(1)).first() is not None:
            return
        sesion.add(
            Usuario(
                nombre_completo="Usuario de demostracion",
                correo=_CORREO_DEMOSTRACION,
                contrasena_hash=hashear_contrasena(_CONTRASENA_DEMOSTRACION),
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
