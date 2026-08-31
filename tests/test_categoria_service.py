"""Reglas de negocio de las categorias, probadas sin pasar por HTTP."""

import pytest
from sqlalchemy.orm import Session

from app.business.errors import DatosInvalidos, RecursoNoEncontrado, ReglaDeNegocioViolada
from app.business.services.categoria_service import CategoriaService, CrearCategoriaComando
from app.data.models.enums import Moneda
from app.data.models.usuario import Usuario
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.usuario_repository import UsuarioRepository


@pytest.fixture
def servicio(sesion: Session) -> CategoriaService:
    return CategoriaService(CategoriaRepository(sesion), UsuarioRepository(sesion))


def test_crea_una_categoria_hoja_y_activa(servicio: CategoriaService, usuario: Usuario) -> None:
    categoria = servicio.crear(
        CrearCategoriaComando(usuario_id=usuario.id, nombre="Alimentacion", color_hex="#2563eb")
    )

    assert categoria.id is not None
    assert categoria.es_hoja is True
    assert categoria.activa is True
    assert categoria.color_hex == "#2563EB", "el color se normaliza a mayusculas"


def test_colgar_una_subcategoria_convierte_a_la_padre_en_totalizadora(
    servicio: CategoriaService, usuario: Usuario
) -> None:
    padre = servicio.crear(
        CrearCategoriaComando(usuario_id=usuario.id, nombre="Alimentacion", color_hex="#2563EB")
    )

    hija = servicio.crear(
        CrearCategoriaComando(
            usuario_id=usuario.id,
            nombre="Supermercado",
            color_hex="#16A34A",
            categoria_padre_id=padre.id,
        )
    )

    assert padre.es_hoja is False, "las categorias padre totalizan, no reciben gasto directo"
    assert hija.es_hoja is True
    assert hija.categoria_padre_id == padre.id


def test_rechaza_un_nombre_repetido_en_la_misma_cuenta(
    servicio: CategoriaService, usuario: Usuario
) -> None:
    servicio.crear(
        CrearCategoriaComando(usuario_id=usuario.id, nombre="Alimentacion", color_hex="#2563EB")
    )

    with pytest.raises(ReglaDeNegocioViolada):
        servicio.crear(
            CrearCategoriaComando(usuario_id=usuario.id, nombre="alimentacion", color_hex="#111111")
        )


def test_rechaza_un_color_que_no_es_hexadecimal(
    servicio: CategoriaService, usuario: Usuario
) -> None:
    with pytest.raises(DatosInvalidos):
        servicio.crear(
            CrearCategoriaComando(usuario_id=usuario.id, nombre="Transporte", color_hex="azul")
        )


def test_rechaza_un_nombre_en_blanco(servicio: CategoriaService, usuario: Usuario) -> None:
    with pytest.raises(DatosInvalidos):
        servicio.crear(
            CrearCategoriaComando(usuario_id=usuario.id, nombre="   ", color_hex="#2563EB")
        )


def test_no_deja_colgar_una_categoria_de_la_padre_de_otra_cuenta(
    servicio: CategoriaService, usuario: Usuario, sesion: Session
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona",
        correo="otra@gastonomo.cr",
        contrasena_hash="hash",
        moneda_preferida=Moneda.CRC,
    )
    sesion.add(otro)
    sesion.commit()
    ajena = servicio.crear(
        CrearCategoriaComando(usuario_id=otro.id, nombre="Alimentacion", color_hex="#2563EB")
    )

    with pytest.raises(RecursoNoEncontrado):
        servicio.crear(
            CrearCategoriaComando(
                usuario_id=usuario.id,
                nombre="Supermercado",
                color_hex="#16A34A",
                categoria_padre_id=ajena.id,
            )
        )


def test_rechaza_un_usuario_que_no_existe(servicio: CategoriaService) -> None:
    with pytest.raises(RecursoNoEncontrado):
        servicio.crear(
            CrearCategoriaComando(usuario_id=9999, nombre="Alimentacion", color_hex="#2563EB")
        )


def test_lista_solo_las_categorias_activas_del_titular(
    servicio: CategoriaService, usuario: Usuario, sesion: Session
) -> None:
    activa = servicio.crear(
        CrearCategoriaComando(usuario_id=usuario.id, nombre="Alimentacion", color_hex="#2563EB")
    )
    desactivada = servicio.crear(
        CrearCategoriaComando(usuario_id=usuario.id, nombre="Mascotas", color_hex="#F59E0B")
    )
    desactivada.activa = False
    sesion.commit()

    listadas = servicio.listar_activas(usuario.id)

    assert [categoria.id for categoria in listadas] == [activa.id]
