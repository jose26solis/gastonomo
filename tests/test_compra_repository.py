"""`CompraRepository.gasto_por_categoria`: la consulta agregada de negocio.

Arma las filas directo con el ORM -sin pasar por `ConciliacionService`- para
poder controlar exactamente qué categoría, comercio, fecha y tipo de cambio
tiene cada renglón, que es lo que hace falta para probar la agregación y sus
filtros sin el ruido de parsear un comprobante.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.data.models.categoria import Categoria
from app.data.models.comercio import Comercio
from app.data.models.compra import Compra
from app.data.models.linea_compra import LineaCompra
from app.data.models.usuario import Usuario
from app.data.repositories.compra_repository import CompraRepository


def _sembrar(sesion: Session, usuario: Usuario) -> tuple[Comercio, Comercio, Categoria, Categoria]:
    """Dos comercios, dos categorías, y tres compras repartidas entre ellos:

    - Walmart / Alimentación, enero, en colones (tipo de cambio 1).
    - Uber / Transporte, enero, en dólares -tipo de cambio 500, para probar
      que la conversión de moneda se aplica antes de sumar.
    - Walmart / sin categoría, febrero -para probar que lo sin categorizar
      no se pierde, y que el filtro de mes lo separa de las de enero.
    """
    walmart = Comercio(nombre="Walmart", nombre_normalizado="WALMART")
    uber = Comercio(nombre="Uber", nombre_normalizado="UBER")
    alimentacion = Categoria(usuario_id=usuario.id, nombre="Alimentacion", color_hex="#16A34A")
    transporte = Categoria(usuario_id=usuario.id, nombre="Transporte", color_hex="#2563EB")
    sesion.add_all([walmart, uber, alimentacion, transporte])
    sesion.flush()

    compra_alimentacion = Compra(
        usuario_id=usuario.id,
        comercio_id=walmart.id,
        fecha=date(2026, 1, 15),
        tipo_cambio_aplicado=Decimal("1"),
    )
    compra_transporte = Compra(
        usuario_id=usuario.id,
        comercio_id=uber.id,
        fecha=date(2026, 1, 20),
        tipo_cambio_aplicado=Decimal("500"),
    )
    compra_sin_categoria = Compra(
        usuario_id=usuario.id,
        comercio_id=walmart.id,
        fecha=date(2026, 2, 5),
        tipo_cambio_aplicado=Decimal("1"),
    )
    sesion.add_all([compra_alimentacion, compra_transporte, compra_sin_categoria])
    sesion.flush()

    sesion.add_all(
        [
            LineaCompra(
                compra_id=compra_alimentacion.id,
                categoria_id=alimentacion.id,
                descripcion="Mercado",
                precio_unitario=Decimal("1000.00"),
                subtotal=Decimal("1000.00"),
            ),
            LineaCompra(
                compra_id=compra_transporte.id,
                categoria_id=transporte.id,
                descripcion="Carrera",
                precio_unitario=Decimal("10.00"),
                subtotal=Decimal("10.00"),
            ),
            LineaCompra(
                compra_id=compra_sin_categoria.id,
                categoria_id=None,
                descripcion="Sin clasificar",
                precio_unitario=Decimal("300.00"),
                subtotal=Decimal("300.00"),
            ),
        ]
    )
    sesion.commit()
    return walmart, uber, alimentacion, transporte


def _totales(sesion: Session, usuario: Usuario, **filtros: int | None) -> dict[str | None, Decimal]:
    repositorio = CompraRepository(sesion)
    filas = repositorio.gasto_por_categoria(usuario.id, **filtros)
    return {fila.categoria_nombre: Decimal(str(fila.total)) for fila in filas}


def test_suma_y_convierte_por_categoria(sesion: Session, usuario: Usuario) -> None:
    _sembrar(sesion, usuario)

    totales = _totales(sesion, usuario)

    assert totales["Alimentacion"] == Decimal("1000.00")
    # 10 dolares * 500 de tipo de cambio: la conversion se aplica antes de sumar.
    assert totales["Transporte"] == Decimal("5000.00")
    assert totales[None] == Decimal("300.00"), "lo sin categorizar no se pierde"


def test_ordena_de_mayor_a_menor_gasto(sesion: Session, usuario: Usuario) -> None:
    _sembrar(sesion, usuario)

    nombres = [
        fila.categoria_nombre for fila in CompraRepository(sesion).gasto_por_categoria(usuario.id)
    ]

    assert nombres == ["Transporte", "Alimentacion", None]


def test_filtra_por_anio_y_mes(sesion: Session, usuario: Usuario) -> None:
    _sembrar(sesion, usuario)

    totales = _totales(sesion, usuario, anio=2026, mes=1)

    assert set(totales) == {"Alimentacion", "Transporte"}, "febrero queda fuera"


def test_filtra_por_comercio(sesion: Session, usuario: Usuario) -> None:
    walmart, _uber, _alimentacion, _transporte = _sembrar(sesion, usuario)

    totales = _totales(sesion, usuario, comercio_id=walmart.id)

    assert set(totales) == {"Alimentacion", None}, "Uber (Transporte) queda fuera"


def test_sin_compras_da_lista_vacia(sesion: Session, usuario: Usuario) -> None:
    assert CompraRepository(sesion).gasto_por_categoria(usuario.id) == []
