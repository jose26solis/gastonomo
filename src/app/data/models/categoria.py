"""Entidad Categoria: clasificacion jerarquica del gasto."""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.models.base import Base
from app.data.models.usuario import Usuario


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

    usuario: Mapped[Usuario] = relationship(back_populates="categorias")
    categoria_padre: Mapped[Optional["Categoria"]] = relationship(
        back_populates="subcategorias", remote_side=[id]
    )
    subcategorias: Mapped[list["Categoria"]] = relationship(back_populates="categoria_padre")

    def __repr__(self) -> str:
        return f"Categoria(id={self.id!r}, nombre={self.nombre!r}, usuario_id={self.usuario_id!r})"
