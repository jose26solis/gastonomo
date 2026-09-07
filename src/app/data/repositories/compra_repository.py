"""Consultas de Compra."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Numeric, cast, extract, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.data.models.categoria import Categoria
from app.data.models.compra import Compra
from app.data.models.linea_compra import LineaCompra
from app.data.repositories.base_repository import BaseRepository


@dataclass(frozen=True)
class GastoPorCategoria:
    """Lo gastado en una categoría, ya sumado y convertido a la moneda base de cada compra.

    `categoria_id` y `categoria_nombre` son `None` en el renglón que agrupa
    las líneas todavía sin categorizar -no se descartan: son justo las que
    hace falta ver para saber qué falta clasificar.
    """

    categoria_id: int | None
    categoria_nombre: str | None
    total: Decimal


class CompraRepository(BaseRepository[Compra]):
    """Acceso a las compras de un titular."""

    def __init__(self, sesion: Session) -> None:
        super().__init__(sesion, Compra)

    @staticmethod
    def _con_detalle_cargado(consulta):
        """Trae comercio, método de pago y renglones (con su categoría) en la misma consulta.

        `joinedload` para `comercio` y `metodo_pago`: son relaciones
        muchos-a-uno, así que el LEFT OUTER JOIN no multiplica filas de
        `Compra` -y tiene que ser OUTER, no INNER, porque `metodo_pago_id` es
        justo NULL en las compras que quedaron "requiere_revision".

        `selectinload` para `lineas` -y no `joinedload`- porque es una
        colección: con `joinedload` el `LIMIT` de `listar_de_usuario` se
        aplicaría a las filas del producto cartesiano, no a las compras, y
        una compra con varios renglones se comería varios lugares de la
        página. `selectinload` hace una segunda consulta con `IN (...)`
        sobre los ids ya paginados, así que el `LIMIT` sigue siendo por
        compra.
        """
        return consulta.options(
            joinedload(Compra.comercio),
            joinedload(Compra.metodo_pago),
            selectinload(Compra.lineas).joinedload(LineaCompra.categoria),
        )

    def obtener_de_usuario(self, identificador: int, usuario_id: int) -> Compra | None:
        consulta = select(Compra).where(Compra.id == identificador, Compra.usuario_id == usuario_id)
        return self.sesion.scalars(self._con_detalle_cargado(consulta)).first()

    def listar_de_usuario(
        self, usuario_id: int, requiere_revision: bool | None = None, limite: int = 50
    ) -> list[Compra]:
        """Las compras del titular, más recientes primero, con su detalle ya resuelto.

        `requiere_revision` filtra por esa columna cuando no es `None` -es lo
        que arma la lista de "compras que necesitan revisión" sin traer todo
        el historial para filtrarlo en Python.
        """
        consulta = select(Compra).where(Compra.usuario_id == usuario_id)
        if requiere_revision is not None:
            consulta = consulta.where(Compra.requiere_revision.is_(requiere_revision))
        consulta = consulta.order_by(Compra.fecha.desc(), Compra.id.desc()).limit(limite)
        return list(self.sesion.scalars(self._con_detalle_cargado(consulta)).unique())

    def gasto_por_categoria(
        self,
        usuario_id: int,
        anio: int | None = None,
        mes: int | None = None,
        comercio_id: int | None = None,
    ) -> list[GastoPorCategoria]:
        """Cuánto gastó el titular en cada categoría, sumado y agrupado en SQL.

        Suma `LineaCompra.subtotal` -no `Compra.total`- porque la categoría
        vive en el renglón, no en la compra: agrupar por el total de una
        compra desglosada en varias categorías la contaría completa en cada
        una. Cada renglón se multiplica por el `tipo_cambio_aplicado` de su
        propia compra -el que de verdad rigió esa compra- porque el subtotal
        está en la moneda de su compra: sumar colones y dólares sin convertir
        a la moneda base daría un número que no significa nada.

        `anio`, `mes` y `comercio_id` son filtros opcionales que se combinan
        -el equivalente de componer Specifications sin traer el historial
        completo a Python para filtrarlo ahí.
        """
        # cast a Numeric(14, 2): sin él, la escala del producto es la de
        # `tipo_cambio_aplicado` (Numeric(14, 6)), y el total saldría con más
        # decimales que el resto de los montos de la API (todos Numeric(14, 2)).
        gasto = cast(func.sum(LineaCompra.subtotal * Compra.tipo_cambio_aplicado), Numeric(14, 2))
        consulta = (
            select(LineaCompra.categoria_id, Categoria.nombre, gasto.label("total"))
            .join(Compra, LineaCompra.compra_id == Compra.id)
            .outerjoin(Categoria, LineaCompra.categoria_id == Categoria.id)
            .where(Compra.usuario_id == usuario_id)
        )
        if anio is not None:
            consulta = consulta.where(extract("year", Compra.fecha) == anio)
        if mes is not None:
            consulta = consulta.where(extract("month", Compra.fecha) == mes)
        if comercio_id is not None:
            consulta = consulta.where(Compra.comercio_id == comercio_id)
        consulta = consulta.group_by(LineaCompra.categoria_id, Categoria.nombre).order_by(
            gasto.desc()
        )
        return [
            GastoPorCategoria(categoria_id=categoria_id, categoria_nombre=nombre, total=total)
            for categoria_id, nombre, total in self.sesion.execute(consulta)
        ]
