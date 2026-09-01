"""Entidad Comercio: el establecimiento donde se compró."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.data.models.base import Base


class Comercio(Base):
    """Comercio del catálogo compartido -no es un dato de un usuario, sino del
    establecimiento en sí. El mismo Walmart lo compran titulares distintos, y
    todos tienen que resolver a la misma fila.

    `nombre_normalizado` es la clave real de identidad: dos notificaciones que
    digan `WALMART SAN SEBASTIAN ` y `Walmart San Sebastián` tienen que
    resolver al mismo comercio, no crear uno nuevo por cada variante de
    mayúsculas o acentos.
    """

    __tablename__ = "comercio"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    nombre_normalizado: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    identificacion_tributaria: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def __repr__(self) -> str:
        return f"Comercio(id={self.id!r}, nombre={self.nombre!r})"
