"""Entidad Usuario: la raiz de aislamiento del sistema."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.models.base import Base
from app.data.models.enums import Moneda
from app.data.models.tipos import FechaHoraUTC

if TYPE_CHECKING:
    from app.data.models.categoria import Categoria
    from app.data.models.cuenta_correo import CuentaCorreo


class Usuario(Base):
    """Persona duena de su cuenta y de sus datos.

    Toda consulta del sistema se filtra por usuario: es lo que permite que
    cualquiera se registre sin ver los datos de nadie mas.
    """

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    moneda_preferida: Mapped[Moneda] = mapped_column(
        Enum(Moneda), nullable=False, default=Moneda.CRC
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        FechaHoraUTC, nullable=False, default=lambda: datetime.now(UTC)
    )

    categorias: Mapped[list["Categoria"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    cuentas_correo: Mapped[list["CuentaCorreo"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Usuario(id={self.id!r}, correo={self.correo!r})"
