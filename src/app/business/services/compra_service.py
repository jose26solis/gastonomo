"""Lecturas de Compra que no encajan en ConciliacionService (que solo escribe).

Antes de esto, la única forma de "ver" una Compra real desde la API era
indirecta: los campos planos de `Comprobante` (que duplican casi lo mismo) o
los eventos de su bitácora en Mongo -nunca la Compra en sí, ni su
`requiere_revision`, ni con qué método de pago o categoría quedó. Este
servicio es lo que la hace un dato de primera clase: listable, filtrable por
"necesita revisión", y consultable una por una con sus nombres ya resueltos.

`_detallar` lee de las relaciones que `CompraRepository` ya trae cargadas
(`comercio`, `metodo_pago`, `lineas.categoria`) en vez de resolverlas con un
`obtener_por_id` propio por cada una: antes eran 1 + 4N consultas para listar
N compras (una por comercio, una por método de pago, una por sus renglones y
una por categoría, todas dentro del bucle); con la carga ansiosa del
repositorio son 2 consultas sin importar cuántas compras traiga la página.
"""

from dataclasses import dataclass

from app.business.errors import RecursoNoEncontrado
from app.data.models.compra import Compra
from app.data.repositories.compra_repository import CompraRepository, GastoPorCategoria


@dataclass(frozen=True)
class CompraDetallada:
    """Una Compra junto con los nombres de lo que hoy solo tiene como ids sueltos.

    `categoria_id`/`categoria_nombre` son "la categoría de la compra": la de
    su único renglón si solo tiene uno (el caso de siempre, ingerida por
    correo), la que comparten todos si el desglose manual (ver
    `ConciliacionService.desglosar_compra`) los dejó igual a todos, o
    `None`/"Varias categorías" si de verdad quedaron repartidos entre más de
    una -ahí ya no hay una sola categoría honesta que mostrar acá, hay que ir
    a `lineas` para el detalle real.
    """

    compra: Compra
    comercio_nombre: str
    metodo_pago_alias: str | None
    categoria_id: int | None
    categoria_nombre: str | None


class CompraService:
    """Consultas de compras reales ya conciliadas."""

    def __init__(self, compra_repository: CompraRepository) -> None:
        self.compras = compra_repository

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

    def gasto_por_categoria(
        self,
        usuario_id: int,
        anio: int | None = None,
        mes: int | None = None,
        comercio_id: int | None = None,
    ) -> list[GastoPorCategoria]:
        """Cuánto gastó el titular en cada categoría, con filtros opcionales de
        período y comercio. Ver `CompraRepository.gasto_por_categoria` -la suma
        la hace la base de datos, no este servicio."""
        return self.compras.gasto_por_categoria(usuario_id, anio, mes, comercio_id)

    def _detallar(self, compra: Compra) -> CompraDetallada:
        # Puro acceso a atributos: `comercio`, `metodo_pago` y `lineas` (con
        # su `categoria`) ya llegan cargados desde `CompraRepository`. Nada
        # de esto dispara una consulta nueva.
        categorias_distintas = {linea.categoria_id for linea in compra.lineas}
        if len(categorias_distintas) == 1:
            # Único valor -sea una categoría real que comparten todos los
            # renglones, o `None` si ninguno tiene: en los dos casos hay una
            # sola respuesta honesta que dar.
            (categoria_id,) = categorias_distintas
            linea_con_categoria = next(
                (linea for linea in compra.lineas if linea.categoria_id == categoria_id), None
            )
            categoria_nombre = (
                linea_con_categoria.categoria.nombre
                if linea_con_categoria and linea_con_categoria.categoria
                else None
            )
        else:
            # Sin renglones, o desglosada en más de una categoría real -no
            # hay una sola categoría que resuma la compra.
            categoria_id = None
            categoria_nombre = "Varias categorías" if categorias_distintas else None
        return CompraDetallada(
            compra=compra,
            comercio_nombre=compra.comercio.nombre if compra.comercio else "Comercio eliminado",
            metodo_pago_alias=compra.metodo_pago.alias if compra.metodo_pago else None,
            categoria_id=categoria_id,
            categoria_nombre=categoria_nombre,
        )
