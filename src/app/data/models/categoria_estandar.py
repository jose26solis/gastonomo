"""Entidad CategoriaEstandar: la taxonomía global con la que se siembra toda cuenta nueva.

Existe además por una razón de integridad: el catálogo de `Comercio` es
compartido entre todos los titulares, mientras que `Categoria` es propia de
cada uno. Si `Comercio` apuntara directo a `Categoria`, la sugerencia de un
comercio compartido señalaría la categoría de un titular cualquiera. El
comercio sugiere (indirectamente, hoy vía `ComercioCategoriaSugerida`) una
categoría de esta taxonomía global; cada titular la resuelve contra la suya
propia mediante `Categoria.categoria_estandar_id`.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.data.models.base import Base


class CategoriaEstandar(Base):
    """Una de las ~15 categorías semilla. Global, no pertenece a ningún titular."""

    __tablename__ = "categoria_estandar"

    id: Mapped[int] = mapped_column(primary_key=True)
    # El código, y no el nombre, es la llave estable: el nombre visible puede
    # reescribirse sin romper las referencias.
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#6B7280")
    orden: Mapped[int] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"CategoriaEstandar(codigo={self.codigo!r}, nombre={self.nombre!r})"
