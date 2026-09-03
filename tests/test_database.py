"""`sembrar_usuario_de_demostracion`: crea el usuario de prueba con las
credenciales configuradas, y solo en una base vacía.

No tenía ninguna prueba todavía. Vale la pena fijarla ahora que el correo y
la contraseña salen de `Configuracion` (`.env`) en vez de una constante en
el archivo -si alguien rompe esa lectura, esto lo dice antes de que se
note en producción como "el usuario de demostración no puede entrar".
"""

from dataclasses import replace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.business.seguridad.contrasenas import verificar_contrasena
from app.config import database
from app.data.models.base import Base
from app.data.models.categoria_estandar import CategoriaEstandar
from app.data.models.usuario import Usuario


@pytest.fixture
def base_vacia(monkeypatch: pytest.MonkeyPatch):
    """Sustituye `FabricaDeSesiones` del módulo por una sobre una base en memoria propia."""
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=motor)
    fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "FabricaDeSesiones", fabrica)
    return fabrica


def test_siembra_el_usuario_con_las_credenciales_configuradas(
    base_vacia, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        database,
        "_configuracion",
        replace(
            database._configuracion, demo_correo="otra@correo.cr", demo_contrasena="otra-clave-123"
        ),
    )

    database.sembrar_usuario_de_demostracion()

    with base_vacia() as sesion:
        usuario = sesion.scalars(select(Usuario)).one()
        assert usuario.correo == "otra@correo.cr"
        assert verificar_contrasena("otra-clave-123", usuario.contrasena_hash)


def test_no_hace_nada_si_la_base_ya_tiene_algun_usuario(base_vacia) -> None:
    with base_vacia() as sesion:
        sesion.add(
            Usuario(
                nombre_completo="Ya existía", correo="existente@correo.cr", contrasena_hash="hash"
            )
        )
        sesion.commit()

    database.sembrar_usuario_de_demostracion()

    with base_vacia() as sesion:
        correos = sesion.scalars(select(Usuario.correo)).all()
        assert correos == ["existente@correo.cr"], "no debió agregar el usuario de demostración"


def test_siembra_las_quince_categorias_estandar(base_vacia) -> None:
    database.sembrar_categorias_estandar()

    with base_vacia() as sesion:
        codigos = set(sesion.scalars(select(CategoriaEstandar.codigo)))
        assert len(codigos) == 15
        assert "ALIMENTACION" in codigos
        assert "OTROS" in codigos


def test_sembrar_categorias_estandar_es_idempotente(base_vacia) -> None:
    database.sembrar_categorias_estandar()
    database.sembrar_categorias_estandar()

    with base_vacia() as sesion:
        assert sesion.scalar(select(func.count()).select_from(CategoriaEstandar)) == 15


def test_sembrar_categorias_estandar_agrega_solo_lo_que_falta(base_vacia) -> None:
    """Una base que ya tenía algunas -de una siembra anterior con menos filas,
    o cargadas a mano- no las duplica ni las pisa."""
    with base_vacia() as sesion:
        sesion.add(
            CategoriaEstandar(
                codigo="ALIMENTACION", nombre="Nombre editado a mano", color_hex="#000000", orden=1
            )
        )
        sesion.commit()

    database.sembrar_categorias_estandar()

    with base_vacia() as sesion:
        total = sesion.scalar(select(func.count()).select_from(CategoriaEstandar))
        assert total == 15
        alimentacion = sesion.scalars(
            select(CategoriaEstandar).where(CategoriaEstandar.codigo == "ALIMENTACION")
        ).one()
        assert alimentacion.nombre == "Nombre editado a mano", "no pisa lo que ya existía"
