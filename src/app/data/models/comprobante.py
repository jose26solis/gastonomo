"""Entidad Comprobante: el resultado ya parseado de un mensaje de BAC, guardado.

Antes de esto, cada pantalla que necesitaba el gasto real -resumen, comercios,
presupuestos, reportes- releía y reparseaba la bandeja completa del proveedor
en cada petición: con una bandeja de más de cien mensajes, eso son cien
peticiones HTTP a Microsoft o Google por cada carga de pantalla, cada vez.
Esta tabla es la caché de ese trabajo: el resultado de `parsear_comprobante_bac`
se guarda una sola vez por mensaje, y las pantallas leen de aquí, no del correo.

Lo único que sigue tocando la red es `CuentaCorreoService.sincronizar`, y solo
para los mensajes que todavía no están en esta tabla -`mensaje_id` es la clave
de deduplicación. Sincronizar de nuevo una bandeja ya al día no vuelve a pedir
ningún cuerpo de mensaje, porque no encuentra ningún `mensaje_id` nuevo con qué
hacerlo.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.data.models.base import Base


class Comprobante(Base):
    """Un mensaje de BAC ya leído y parseado, listo para sumar sin volver al correo.

    Es un espejo de `ComprobanteParseado` -el mismo resultado de lectura, ahora
    persistido- no una entidad de negocio nueva: no valida reglas de dominio ni
    se relaciona con `Categoria` o `Comercio`. Esa clasificación se sigue
    resolviendo en memoria con `ComercioService`, ahora sobre estas filas en
    vez de sobre una respuesta del proveedor.
    """

    __tablename__ = "comprobante"
    __table_args__ = (
        UniqueConstraint("cuenta_correo_id", "mensaje_id", name="uq_comprobante_cuenta_mensaje"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_correo_id: Mapped[int] = mapped_column(
        ForeignKey("cuenta_correo.id"), nullable=False, index=True
    )
    mensaje_id: Mapped[str] = mapped_column(String(300), nullable=False)

    banco: Mapped[str] = mapped_column(String(80), nullable=False)
    comercio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pais: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Naive a propósito: el parser la extrae del texto del correo sin zona
    # horaria (es la hora local de Costa Rica que BAC escribe en la
    # notificación), y todo lo que la usa -agrupar_por_mes, filtrar_del_periodo-
    # solo mira año y mes. FechaHoraUTC no aplica aquí: es para timestamps del
    # propio sistema (expiración de token, última sincronización), no para un
    # dato de negocio que nunca se compara contra la hora actual.
    fecha: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    marca_tarjeta: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ultimos_cuatro: Mapped[str | None] = mapped_column(String(4), nullable=True)
    autorizacion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    referencia: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tipo_transaccion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    moneda: Mapped[str | None] = mapped_column(String(3), nullable=True)
    monto: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    confianza: Mapped[float] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return (
            f"Comprobante(cuenta_correo_id={self.cuenta_correo_id!r}, "
            f"mensaje_id={self.mensaje_id!r}, comercio={self.comercio!r})"
        )
