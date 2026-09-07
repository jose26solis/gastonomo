"""Entidad Categoria: clasificacion jerarquica del gasto."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.models.base import Base
from app.data.models.categoria_estandar import CategoriaEstandar
from app.data.models.usuario import Usuario

if TYPE_CHECKING:
    from app.data.models.comercio_categoria_sugerida import ComercioCategoriaSugerida
    from app.data.models.linea_compra import LineaCompra
    from app.data.models.presupuesto import Presupuesto
    from app.data.models.regla_categorizacion import ReglaCategorizacion


class Categoria(Base):
    """Clasificacion del gasto de un usuario, jerarquica (Alimentacion -> Supermercado).

    Solo las categorias hoja reciben gasto directo; las padre existen para
    totalizar. Por eso `es_hoja` es un dato persistido y no algo que se calcule
    en cada consulta: el frontend lo necesita para saber donde deja clasificar.
    """

    __tablename__ = "categoria"
    __table_args__ = (
        # Dos categorias con el mismo nombre en la misma cuenta harian el reporte
        # ambiguo. El servicio ademas lo valida antes, para dar un error legible.
        UniqueConstraint("usuario_id", "nombre", name="uq_categoria_usuario_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False, index=True)
    categoria_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria.id"), nullable=True
    )
    # De qué categoría de la taxonomía global (`CategoriaEstandar`) nació
    # esta -NULL cuando el titular la creó él mismo, sin partir de la
    # semilla. Es lo que permite que la sugerencia de un comercio compartido
    # aterrice en la categoría propia de cada titular.
    categoria_estandar_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria_estandar.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    es_hoja: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    usuario: Mapped[Usuario] = relationship(back_populates="categorias", lazy="select")
    categoria_padre: Mapped[Optional["Categoria"]] = relationship(
        back_populates="subcategorias", remote_side=[id], lazy="select"
    )
    subcategorias: Mapped[list["Categoria"]] = relationship(
        back_populates="categoria_padre", lazy="select"
    )
    # Sin cascade en ninguna de las siguientes: la duena real es Usuario (ver
    # su cascade="all, delete-orphan"), esta es la vista desde Categoria del
    # mismo vinculo, no una segunda relacion de propiedad.
    categoria_estandar: Mapped[CategoriaEstandar | None] = relationship(
        back_populates="categorias", lazy="select"
    )
    sugerencias_comercio: Mapped[list["ComercioCategoriaSugerida"]] = relationship(
        back_populates="categoria", lazy="select"
    )
    presupuestos: Mapped[list["Presupuesto"]] = relationship(
        back_populates="categoria", lazy="select"
    )
    reglas_categorizacion: Mapped[list["ReglaCategorizacion"]] = relationship(
        back_populates="categoria_destino", lazy="select"
    )
    lineas_compra: Mapped[list["LineaCompra"]] = relationship(
        back_populates="categoria", lazy="select"
    )

    def __repr__(self) -> str:
        return f"Categoria(id={self.id!r}, nombre={self.nombre!r}, usuario_id={self.usuario_id!r})"
