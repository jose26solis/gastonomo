"""Entidad Presupuesto: el tope de gasto de una categoría para un mes."""

from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.data.models.base import Base
from app.data.models.enums import Moneda


class Presupuesto(Base):
    """Tope de gasto de una categoría de un titular en un año y mes concretos.

    Solo guarda el **límite** -no `monto_consumido`-. La propuesta de dominio
    original lo modela como un campo que Proceso 2 va acumulando con cada
    compra, pero esa tubería transaccional todavía no existe: hoy no hay
    ninguna `Compra` persistida, el gasto se lee del correo real en el
    momento. Guardar un `monto_consumido` que nada actualiza sería peor que
    no tenerlo -quedaría desactualizado desde el primer día. En su lugar, el
    consumo se calcula cada vez que se consulta, combinando este límite con
    los comercios reales ya clasificados (`ComercioService.clasificar_comprobantes`)
    del mismo período. Ver `PresupuestoService.calcular_estado`.
    """

    __tablename__ = "presupuesto"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "categoria_id",
            "anio",
            "mes",
            name="uq_presupuesto_usuario_categoria_periodo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False, index=True)
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categoria.id"), nullable=False, index=True
    )
    anio: Mapped[int] = mapped_column(nullable=False)
    mes: Mapped[int] = mapped_column(nullable=False)
    moneda: Mapped[Moneda] = mapped_column(Enum(Moneda), nullable=False)
    monto_limite: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    umbral_alerta: Mapped[int] = mapped_column(nullable=False, default=80)

    def __repr__(self) -> str:
        return (
            f"Presupuesto(usuario_id={self.usuario_id!r}, categoria_id={self.categoria_id!r}, "
            f"{self.anio}-{self.mes:02d})"
        )
