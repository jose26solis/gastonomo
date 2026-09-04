"""Lecturas de Compra que no encajan en ConciliacionService (que solo escribe).

Antes de esto, la única forma de "ver" una Compra real desde la API era
indirecta: los campos planos de `Comprobante` (que duplican casi lo mismo) o
los eventos de su bitácora en Mongo -nunca la Compra en sí, ni su
`requiere_revision`, ni con qué método de pago o categoría quedó. Este
servicio es lo que la hace un dato de primera clase: listable, filtrable por
"necesita revisión", y consultable una por una con sus nombres ya resueltos.
"""

from dataclasses import dataclass

from app.business.errors import RecursoNoEncontrado
from app.data.models.compra import Compra
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.comercio_repository import ComercioRepository
from app.data.repositories.compra_repository import CompraRepository
from app.data.repositories.linea_compra_repository import LineaCompraRepository
from app.data.repositories.metodo_pago_repository import MetodoPagoRepository
from app.data.repositories.usuario_repository import UsuarioRepository


@dataclass(frozen=True)
class CompraDetallada:
    """Una Compra junto con los nombres de lo que hoy solo tiene como ids sueltos.

    La categoría sale de su primera línea -toda compra ingerida por correo
    nace con una sola (ver `LineaCompra`)- así que "la categoría de la
    compra" todavía es una simplificación honesta, no una mentira: el día
    que exista desglose manual en varias líneas, esto deja de alcanzar.
    """

    compra: Compra
    comercio_nombre: str
    metodo_pago_alias: str | None
    categoria_id: int | None
    categoria_nombre: str | None


class CompraService:
    """Consultas de compras reales ya conciliadas."""

    def __init__(
        self,
        compra_repository: CompraRepository,
        linea_compra_repository: LineaCompraRepository,
        comercio_repository: ComercioRepository,
        metodo_pago_repository: MetodoPagoRepository,
        categoria_repository: CategoriaRepository,
        usuario_repository: UsuarioRepository,
    ) -> None:
        self.compras = compra_repository
        self.lineas = linea_compra_repository
        self.comercios = comercio_repository
        self.metodos_pago = metodo_pago_repository
        self.categorias = categoria_repository
        self.usuarios = usuario_repository

    def obtener_del_titular(self, usuario_id: int, compra_id: int) -> Compra:
        """La compra, solo si pertenece al titular indicado.

        Es la validación que impide que un titular vea la bitácora de la
        compra de otra persona pasando un id ajeno -Mongo, a diferencia de
        PostgreSQL, no tiene ninguna noción de "de quién es esto" propia.
        """
        compra = self.compras.obtener_de_usuario(compra_id, usuario_id)
        if compra is None:
            raise RecursoNoEncontrado(f"La compra {compra_id} no existe en esta cuenta.")
        return compra

    def listar_del_titular(
        self, usuario_id: int, requiere_revision: bool | None = None, limite: int = 50
    ) -> list[CompraDetallada]:
        """Las compras reales del titular, más recientes primero.

        `requiere_revision=True` filtra solo las que quedaron sin método de
        pago o sin categoría al conciliar -la lista que de verdad hace falta
        para que esa marca deje de ser invisible. `None` trae todas.
        """
        compras = self.compras.listar_de_usuario(usuario_id, requiere_revision, limite)
        return [self._detallar(compra) for compra in compras]

    def obtener_detalle_del_titular(self, usuario_id: int, compra_id: int) -> CompraDetallada:
        return self._detallar(self.obtener_del_titular(usuario_id, compra_id))

    def _detallar(self, compra: Compra) -> CompraDetallada:
        comercio = self.comercios.obtener_por_id(compra.comercio_id)
        metodo_pago = (
            self.metodos_pago.obtener_por_id(compra.metodo_pago_id)
            if compra.metodo_pago_id
            else None
        )
        lineas = self.lineas.listar_de_compra(compra.id)
        # Una compra ingerida por correo siempre nace con una sola línea -ver
        # el docstring de CompraDetallada.
        categoria_id = lineas[0].categoria_id if lineas else None
        categoria_nombre = None
        if categoria_id is not None:
            categoria = self.categorias.obtener_por_id(categoria_id)
            categoria_nombre = categoria.nombre if categoria else None
        return CompraDetallada(
            compra=compra,
            comercio_nombre=comercio.nombre if comercio else "Comercio eliminado",
            metodo_pago_alias=metodo_pago.alias if metodo_pago else None,
            categoria_id=categoria_id,
            categoria_nombre=categoria_nombre,
        )
