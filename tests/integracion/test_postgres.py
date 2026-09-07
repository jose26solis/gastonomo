"""Lo que SQLite no puede probar igual de bien, contra un postgres:16-alpine real.

Cada prueba de acá tiene un motivo concreto para no vivir en `tests/` a
secas -está en su propio docstring- y todas comparten el mismo trasfondo:
esta app corre en producción sobre PostgreSQL (`psycopg`), pero toda la
suite corría hasta ahora sobre SQLite en memoria. Rápido y correcto para
probar reglas de negocio, pero no prueba la base.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.data.models.base import Base
from app.data.models.categoria import Categoria
from app.data.models.comercio import Comercio
from app.data.models.compra import Compra
from app.data.models.enums import Moneda, TipoMetodoPago
from app.data.models.linea_compra import LineaCompra
from app.data.models.metodo_pago import MetodoPago
from app.data.models.usuario import Usuario
from app.data.repositories.compra_repository import CompraRepository

pytestmark = pytest.mark.integracion


def _usuario(sesion: Session, correo: str = "titular@gastonomo.cr") -> Usuario:
    usuario = Usuario(nombre_completo="Titular de prueba", correo=correo, contrasena_hash="hash")
    sesion.add(usuario)
    sesion.flush()
    return usuario


def test_el_esquema_completo_se_crea_y_se_consulta(sesion_postgres: Session) -> None:
    """El equivalente más básico de `ddl-auto=validate`: que las 14 entidades
    mapeadas generen DDL que Postgres de verdad acepta -no solo SQLite, que es
    mucho más permisivo con tipos y longitudes. `sesion_postgres` ya corrió
    `create_all` para llegar hasta acá; esto además confirma que las 14 tablas
    resultantes se pueden consultar, una por una, sin que ninguna haya quedado
    mal formada."""
    entidades = [mapper.class_ for mapper in Base.registry.mappers]
    assert len(entidades) == 14

    for entidad in entidades:
        conteo = sesion_postgres.scalar(select(func.count()).select_from(entidad))
        assert conteo == 0


def test_numeric_guarda_el_valor_exacto(sesion_postgres: Session) -> None:
    """`Numeric(14, 6)` en SQLite se guarda con la afinidad que SQLAlchemy le
    de -en la práctica, buena parte de la aritmética la resuelve como
    `REAL` (punto flotante). Postgres tiene un tipo `NUMERIC` real, con
    precisión decimal exacta. Se ve al hacer aritmética en SQL, que es
    justo lo que hace `gasto_por_categoria`."""
    usuario = _usuario(sesion_postgres)
    comercio = Comercio(nombre="Uber", nombre_normalizado="UBER")
    sesion_postgres.add(comercio)
    sesion_postgres.flush()

    compra = Compra(
        usuario_id=usuario.id,
        comercio_id=comercio.id,
        fecha=date(2026, 3, 1),
        tipo_cambio_aplicado=Decimal("536.784512"),
    )
    sesion_postgres.add(compra)
    sesion_postgres.flush()
    sesion_postgres.add(
        LineaCompra(
            compra_id=compra.id,
            descripcion="Carrera",
            precio_unitario=Decimal("10.10"),
            subtotal=Decimal("10.10"),
        )
    )
    sesion_postgres.commit()

    total = CompraRepository(sesion_postgres).gasto_por_categoria(usuario.id)[0].total
    # 10.10 * 536.784512 = 5421.523771 (redondeado a 2 decimales por el cast
    # de la consulta). Sobre SQLite esta cuenta puede arrastrar el error de
    # redondeo binario de un float; sobre Postgres es aritmética decimal exacta.
    assert total == Decimal("5421.52")


def test_on_delete_cascade_borra_los_renglones_de_verdad(sesion_postgres: Session) -> None:
    """`LineaCompra.compra_id` declara `ondelete="CASCADE"` desde el modelo,
    pero SQLite ignora esa cláusula sin `PRAGMA foreign_keys=ON` -y esta app
    nunca lo enciende. Borra la `Compra` con un `DELETE` en bruto (sin pasar
    por el `cascade="all, delete-orphan"` del ORM) para probar la restricción
    de la base en sí, no la del ORM."""
    usuario = _usuario(sesion_postgres)
    comercio = Comercio(nombre="Walmart", nombre_normalizado="WALMART")
    sesion_postgres.add(comercio)
    sesion_postgres.flush()
    compra = Compra(usuario_id=usuario.id, comercio_id=comercio.id, fecha=date(2026, 1, 1))
    sesion_postgres.add(compra)
    sesion_postgres.flush()
    linea = LineaCompra(
        compra_id=compra.id,
        descripcion="Mercado",
        precio_unitario=Decimal("100"),
        subtotal=Decimal("100"),
    )
    sesion_postgres.add(linea)
    sesion_postgres.commit()
    compra_id, linea_id = compra.id, linea.id

    sesion_postgres.execute(delete(Compra).where(Compra.id == compra_id))
    sesion_postgres.commit()

    # `.get()` mira primero el mapa de identidad y devolvería el objeto ya
    # cargado sin volver a preguntarle a la base -un `select` fresco sí
    # refleja que la fila ya no está.
    restante = sesion_postgres.scalars(
        select(LineaCompra).where(LineaCompra.id == linea_id)
    ).first()
    assert restante is None


def test_restringe_borrar_un_comercio_referenciado(sesion_postgres: Session) -> None:
    """`Compra.comercio_id` no tiene `ondelete`, así que Postgres aplica su
    default (`NO ACTION`, equivalente a `RESTRICT` dentro de la transacción):
    no se puede borrar un comercio con compras. SQLite sin el `PRAGMA` deja
    borrarlo igual, dejando un `comercio_id` huérfano apuntando a nada."""
    usuario = _usuario(sesion_postgres)
    comercio = Comercio(nombre="Walmart", nombre_normalizado="WALMART")
    sesion_postgres.add(comercio)
    sesion_postgres.flush()
    sesion_postgres.add(Compra(usuario_id=usuario.id, comercio_id=comercio.id, fecha=date.today()))
    sesion_postgres.commit()

    with pytest.raises(IntegrityError):
        sesion_postgres.execute(delete(Comercio).where(Comercio.id == comercio.id))
        sesion_postgres.commit()
    sesion_postgres.rollback()


def test_varchar_rechaza_un_valor_mas_largo_que_la_columna(sesion_postgres: Session) -> None:
    """`MetodoPago.alias` es `String(60)`. Postgres corta con `DataError` al
    intentar guardar más de 60 caracteres; SQLite no tiene un tipo `VARCHAR`
    real y acepta cualquier largo -es la misma clase de bug que el commit
    32deefc corrigió con el token de Outlook."""
    usuario = _usuario(sesion_postgres)
    sesion_postgres.add(
        MetodoPago(
            usuario_id=usuario.id,
            alias="A" * 61,
            tipo=TipoMetodoPago.EFECTIVO,
            moneda=Moneda.CRC,
        )
    )
    with pytest.raises(DataError):
        sesion_postgres.flush()
    sesion_postgres.rollback()


def test_rollback_real_no_deja_nada_a_medias(sesion_postgres: Session) -> None:
    """Dos categorías del mismo titular con el mismo nombre violan la
    restricción `UNIQUE(usuario_id, nombre)` -pero la violación se detecta
    recién al confirmar. El `ROLLBACK` tiene que deshacer **las dos**
    inserciones de esta transacción, no solo la que falló; es justo lo que
    depende la conciliación real, que escribe en cinco tablas a la vez."""
    usuario = _usuario(sesion_postgres)
    sesion_postgres.add(Categoria(usuario_id=usuario.id, nombre="Mascotas", color_hex="#65A30D"))
    sesion_postgres.add(Categoria(usuario_id=usuario.id, nombre="Mascotas", color_hex="#111111"))

    with pytest.raises(IntegrityError):
        sesion_postgres.commit()
    sesion_postgres.rollback()

    categorias = sesion_postgres.scalars(
        select(Categoria).where(Categoria.usuario_id == usuario.id)
    ).all()
    assert list(categorias) == [], "ninguna de las dos debió quedar, ni siquiera la valida"
