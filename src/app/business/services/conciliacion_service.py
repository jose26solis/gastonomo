"""Conciliación transaccional de un comprobante en una Compra real de negocio.

Implementa los pasos 4-9 del Proceso 2 del dominio (ver
docs/propuesta-dominio.md): emparejar método de pago, resolver comercio,
categorizar, crear la `Compra` y su línea, acumular el presupuesto, y dejar
el comprobante ligado a su compra. Los pasos 1-3 -leer el correo, guardar el
`Comprobante`, parsearlo- ya los hace
`CuentaCorreoService._sincronizar_comprobantes` antes de llamar acá.

**Es aditivo, no reemplaza nada.** `Comprobante` conserva todas sus columnas
de siempre (banco, comercio, monto...) y sigue alimentando Resumen,
Comercios, Presupuestos "de antes" y los reportes exportables tal cual; solo
gana un `compra_id` que apunta a la `Compra` real que esta conciliación creó.

Todo lo que este método escribe en PostgreSQL -`Compra`, `LineaCompra`, el
contador de la regla que acertó, `Presupuesto.monto_consumido`,
`Comprobante.compra_id`- queda en una sola transacción: si algo falla a
mitad de camino, se revierte todo -nunca queda un comprobante marcado como
conciliado sin que su gasto se haya sumado al presupuesto. La resolución del
`Comercio` (`ComercioService.resolver_o_crear`) confirma aparte, con su
propio commit: es un catálogo compartido entre titulares, y su creación no
es parte de la conciliación de uno en particular -en el Proceso 2 del
dominio, "se resuelve el Comercio" es un paso previo a "se crea la Compra".

La bitácora de Mongo se escribe **después** de confirmar en PostgreSQL, y
nunca puede hacer fallar la conciliación -ver `BitacoraComprasService`.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.business.errors import (
    DatosInvalidos,
    ErrorDeProveedorExterno,
    RecursoNoEncontrado,
    ReglaDeNegocioViolada,
)
from app.business.parsers.comprobante_bac import ComprobanteParseado
from app.business.services.bitacora_service import Actor, BitacoraComprasService
from app.business.services.comercio_service import ComercioService
from app.business.services.presupuesto_service import PresupuestoService
from app.business.services.tipo_cambio_service import TipoCambioService
from app.data.models.compra import Compra
from app.data.models.comprobante import Comprobante
from app.data.models.enums import EstadoCompra, EstadoPresupuesto, Moneda, OrigenCompra
from app.data.models.linea_compra import LineaCompra
from app.data.models.regla_categorizacion import ReglaCategorizacion
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.comercio_categoria_repository import ComercioCategoriaRepository
from app.data.repositories.compra_repository import CompraRepository
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.linea_compra_repository import LineaCompraRepository
from app.data.repositories.metodo_pago_repository import MetodoPagoRepository
from app.data.repositories.presupuesto_repository import PresupuestoRepository
from app.data.repositories.regla_categorizacion_repository import ReglaCategorizacionRepository
from app.data.repositories.tipo_cambio_repository import TipoCambioRepository

_MONEDA_BASE = Moneda.CRC


@dataclass(frozen=True)
class ResultadoConciliacion:
    """Lo que produjo conciliar un comprobante."""

    compra_id: int
    requiere_revision: bool
    presupuesto_alertado: bool


@dataclass(frozen=True)
class LineaDesgloseComando:
    """Un renglón pedido para `ConciliacionService.desglosar_compra`."""

    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal
    exento_impuesto: bool
    categoria_id: int | None


class ConciliacionService:
    """Aplica el Proceso 2 del dominio sobre un comprobante ya parseado."""

    def __init__(
        self,
        compra_repository: CompraRepository,
        linea_compra_repository: LineaCompraRepository,
        metodo_pago_repository: MetodoPagoRepository,
        regla_categorizacion_repository: ReglaCategorizacionRepository,
        presupuesto_repository: PresupuestoRepository,
        categoria_repository: CategoriaRepository,
        comercio_categoria_repository: ComercioCategoriaRepository,
        tipo_cambio_repository: TipoCambioRepository,
        comprobante_repository: ComprobanteRepository,
        comercio_service: ComercioService,
        tipo_cambio_service: TipoCambioService | None,
        bitacora: BitacoraComprasService,
    ) -> None:
        self.compras = compra_repository
        self.lineas = linea_compra_repository
        self.metodos_pago = metodo_pago_repository
        self.reglas = regla_categorizacion_repository
        self.presupuestos = presupuesto_repository
        self.categorias = categoria_repository
        self.sugerencias = comercio_categoria_repository
        self.tipos_cambio = tipo_cambio_repository
        self.comprobantes = comprobante_repository
        self.comercios_servicio = comercio_service
        self.tipo_cambio_servicio = tipo_cambio_service
        self.bitacora = bitacora

    def conciliar(
        self, usuario_id: int, comprobante: Comprobante, parseado: ComprobanteParseado
    ) -> ResultadoConciliacion | None:
        """Corre los pasos 4-9 del Proceso 2. `None` si el comprobante no alcanza
        para conciliar solo -queda para revisión manual, no se inventa nada."""
        if not (
            parseado.es_compra
            and parseado.es_confiable
            and parseado.comercio
            and parseado.monto is not None
            and parseado.moneda
            and parseado.fecha is not None
        ):
            return None

        # Paso 4: emparejar método de pago -nunca se crea uno solo, ver MetodoPago.
        metodo_pago = None
        if parseado.ultimos_cuatro:
            metodo_pago = self.metodos_pago.buscar_por_ultimos_cuatro(
                usuario_id, parseado.ultimos_cuatro
            )

        # Paso 5: resolver el comercio (catálogo compartido, confirma con su propio commit).
        comercio = self.comercios_servicio.resolver_o_crear(parseado.comercio)

        # Paso 6 (categorización): regla activa por prioridad, si no hay,
        # la sugerencia que este titular ya le puso a este comercio.
        categoria_id, regla_aplicada = self._categorizar(usuario_id, comercio.nombre_normalizado)
        if categoria_id is None:
            categoria_id = self.comercios_servicio.categoria_sugerida_para(usuario_id, comercio.id)

        moneda = Moneda(parseado.moneda) if parseado.moneda in Moneda.__members__ else None
        if moneda is None:
            return None  # una moneda que el sistema no reconoce no se inventa a qué tasa vale

        total = parseado.monto
        tipo_cambio_aplicado = Decimal("1")
        if moneda != _MONEDA_BASE:
            tipo_cambio_aplicado = self._tasa_de_conversion(moneda, parseado.fecha.date())
        total_moneda_base = (total * tipo_cambio_aplicado).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        requiere_revision = metodo_pago is None or categoria_id is None

        compra = Compra(
            usuario_id=usuario_id,
            comercio_id=comercio.id,
            metodo_pago_id=metodo_pago.id if metodo_pago else None,
            fecha=parseado.fecha.date(),
            descripcion=comercio.nombre,
            moneda=moneda,
            estado=EstadoCompra.REGISTRADA,
            origen=OrigenCompra.INGESTA_CORREO,
            subtotal=total,
            descuento=Decimal("0"),
            impuesto=Decimal("0"),
            impuesto_desglosado=False,
            total=total,
            tipo_cambio_aplicado=tipo_cambio_aplicado,
            total_moneda_base=total_moneda_base,
            requiere_revision=requiere_revision,
        )
        self.compras.agregar(compra)  # flush: ya tiene compra.id de acá en adelante

        self.lineas.agregar(
            LineaCompra(
                compra_id=compra.id,
                categoria_id=categoria_id,
                descripcion=comercio.nombre,
                cantidad=Decimal("1"),
                precio_unitario=total,
                descuento=Decimal("0"),
                exento_impuesto=False,
                subtotal=total,
                categorizada_automaticamente=categoria_id is not None,
            )
        )

        if regla_aplicada is not None:
            regla_aplicada.veces_aplicada += 1

        alerta_presupuesto = False
        presupuesto = None
        consumido_antes = consumido_despues = None
        if categoria_id is not None:
            presupuesto = self.presupuestos.buscar(
                usuario_id, categoria_id, compra.fecha.year, compra.fecha.month
            )
            # Solo se acumula si el presupuesto está en la MISMA moneda que la
            # compra -mezclar monedas en una suma daría un número inventado.
            if presupuesto is not None and presupuesto.moneda == moneda:
                consumido_antes = presupuesto.monto_consumido
                porcentaje_antes, _ = PresupuestoService.calcular_estado(
                    consumido_antes, presupuesto.monto_limite, presupuesto.umbral_alerta
                )
                presupuesto.monto_consumido = presupuesto.monto_consumido + total
                consumido_despues = presupuesto.monto_consumido
                porcentaje_despues, estado_despues = PresupuestoService.calcular_estado(
                    consumido_despues, presupuesto.monto_limite, presupuesto.umbral_alerta
                )
                alerta_presupuesto = (
                    estado_despues != EstadoPresupuesto.EN_RANGO
                    and porcentaje_antes < presupuesto.umbral_alerta
                )

        comprobante.compra_id = compra.id

        # Un solo commit: todo lo de arriba, o nada.
        self.comprobantes.sesion.commit()

        self._escribir_bitacora(
            compra=compra,
            usuario_id=usuario_id,
            parseado=parseado,
            metodo_pago_id=metodo_pago.id if metodo_pago else None,
            comercio_nombre=comercio.nombre,
            comercio_normalizado=comercio.nombre_normalizado,
            categoria_id=categoria_id,
            regla_aplicada=regla_aplicada,
            tipo_cambio_aplicado=tipo_cambio_aplicado,
            requiere_revision=requiere_revision,
            presupuesto_id=presupuesto.id if presupuesto else None,
            consumido_antes=consumido_antes,
            consumido_despues=consumido_despues,
            alerta_presupuesto=alerta_presupuesto,
        )

        return ResultadoConciliacion(
            compra_id=compra.id,
            requiere_revision=requiere_revision,
            presupuesto_alertado=alerta_presupuesto,
        )

    def conciliar_manual(
        self,
        usuario_id: int,
        parseado: ComprobanteParseado,
        metodo_pago_id: int | None = None,
        categoria_id: int | None = None,
    ) -> ResultadoConciliacion:
        """Crea una Compra real a mano, a partir de un comprobante cargado desde la
        pantalla "Cargar comprobante" -no leído de ningún buzón vinculado.

        Mismo Proceso 2 que `conciliar()` (pasos 5-9: resolver comercio,
        categorizar, convertir, crear la Compra y acumular el presupuesto),
        con tres diferencias: no hay `Comprobante` que marcar -`compra.origen`
        queda `MANUAL` en vez de `INGESTA_CORREO`, y no hace falta el paso 1-3
        de leer y guardar ningún correo-; el método de pago y la categoría
        pueden venir explícitos del formulario en vez de emparejarse solos
        (si no vienen, cae al mismo emparejamiento por últimos 4 dígitos y a
        la misma categorización automática que `conciliar()`); y el actor de
        la bitácora es el propio titular, no la ingesta.
        """
        if not (parseado.monto is not None and parseado.moneda and parseado.fecha is not None):
            raise DatosInvalidos(
                "Hace falta al menos el monto, la moneda y la fecha del comprobante."
            )
        moneda = Moneda(parseado.moneda) if parseado.moneda in Moneda.__members__ else None
        if moneda is None:
            raise DatosInvalidos(f"«{parseado.moneda}» no es una moneda que el sistema reconozca.")

        # Paso 4 (método de pago): explícito si lo mandó el formulario -mismas
        # validaciones que `resolver_revision`-, si no, el mismo
        # emparejamiento automático por últimos 4 dígitos que `conciliar()`.
        metodo_pago = None
        if metodo_pago_id is not None:
            metodo_pago = self.metodos_pago.obtener_de_usuario(metodo_pago_id, usuario_id)
            if metodo_pago is None:
                raise RecursoNoEncontrado(
                    f"El método de pago {metodo_pago_id} no existe en esta cuenta."
                )
            if not metodo_pago.activo:
                raise ReglaDeNegocioViolada("Ese método de pago está desactivado.")
        elif parseado.ultimos_cuatro:
            metodo_pago = self.metodos_pago.buscar_por_ultimos_cuatro(
                usuario_id, parseado.ultimos_cuatro
            )

        # Paso 5: resolver el comercio -mismo catálogo compartido que conciliar().
        comercio = self.comercios_servicio.resolver_o_crear(
            parseado.comercio or "Comercio sin nombre"
        )

        # Paso 6 (categorización): explícita si la eligió el titular en el
        # formulario -mismas validaciones que `resolver_revision`-, si no, la
        # misma regla-luego-sugerencia que `conciliar()`.
        categoria_explicita = categoria_id is not None
        regla_aplicada = None
        if categoria_explicita:
            categoria = self.categorias.obtener_de_usuario(categoria_id, usuario_id)
            if categoria is None:
                raise RecursoNoEncontrado(f"La categoría {categoria_id} no existe en esta cuenta.")
            if not categoria.es_hoja:
                raise ReglaDeNegocioViolada("La categoría tiene que ser una hoja, no un grupo.")
        else:
            categoria_id, regla_aplicada = self._categorizar(
                usuario_id, comercio.nombre_normalizado
            )
            if categoria_id is None:
                categoria_id = self.comercios_servicio.categoria_sugerida_para(
                    usuario_id, comercio.id
                )

        total = parseado.monto
        tipo_cambio_aplicado = Decimal("1")
        if moneda != _MONEDA_BASE:
            tipo_cambio_aplicado = self._tasa_de_conversion(moneda, parseado.fecha.date())
        total_moneda_base = (total * tipo_cambio_aplicado).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        requiere_revision = metodo_pago is None or categoria_id is None

        compra = Compra(
            usuario_id=usuario_id,
            comercio_id=comercio.id,
            metodo_pago_id=metodo_pago.id if metodo_pago else None,
            fecha=parseado.fecha.date(),
            descripcion=comercio.nombre,
            moneda=moneda,
            estado=EstadoCompra.REGISTRADA,
            origen=OrigenCompra.MANUAL,
            subtotal=total,
            descuento=Decimal("0"),
            impuesto=Decimal("0"),
            impuesto_desglosado=False,
            total=total,
            tipo_cambio_aplicado=tipo_cambio_aplicado,
            total_moneda_base=total_moneda_base,
            requiere_revision=requiere_revision,
        )
        self.compras.agregar(compra)  # flush: ya tiene compra.id de acá en adelante

        self.lineas.agregar(
            LineaCompra(
                compra_id=compra.id,
                categoria_id=categoria_id,
                descripcion=comercio.nombre,
                cantidad=Decimal("1"),
                precio_unitario=total,
                descuento=Decimal("0"),
                exento_impuesto=False,
                subtotal=total,
                # Solo cuenta como "automática" la que puso una regla o la
                # sugerencia del comercio -no la que el titular eligió a mano
                # en el formulario, mismo criterio que `resolver_revision`.
                categorizada_automaticamente=(not categoria_explicita) and categoria_id is not None,
            )
        )

        if regla_aplicada is not None:
            regla_aplicada.veces_aplicada += 1

        alerta_presupuesto = False
        presupuesto = None
        consumido_antes = consumido_despues = None
        if categoria_id is not None:
            presupuesto = self.presupuestos.buscar(
                usuario_id, categoria_id, compra.fecha.year, compra.fecha.month
            )
            if presupuesto is not None and presupuesto.moneda == moneda:
                consumido_antes = presupuesto.monto_consumido
                porcentaje_antes, _ = PresupuestoService.calcular_estado(
                    consumido_antes, presupuesto.monto_limite, presupuesto.umbral_alerta
                )
                presupuesto.monto_consumido = presupuesto.monto_consumido + total
                consumido_despues = presupuesto.monto_consumido
                porcentaje_despues, estado_despues = PresupuestoService.calcular_estado(
                    consumido_despues, presupuesto.monto_limite, presupuesto.umbral_alerta
                )
                alerta_presupuesto = (
                    estado_despues != EstadoPresupuesto.EN_RANGO
                    and porcentaje_antes < presupuesto.umbral_alerta
                )

        # Un solo commit: todo lo de arriba, o nada -mismo criterio que conciliar().
        self.compras.sesion.commit()

        self._escribir_bitacora(
            compra=compra,
            usuario_id=usuario_id,
            parseado=parseado,
            metodo_pago_id=metodo_pago.id if metodo_pago else None,
            comercio_nombre=comercio.nombre,
            comercio_normalizado=comercio.nombre_normalizado,
            categoria_id=categoria_id,
            regla_aplicada=regla_aplicada,
            tipo_cambio_aplicado=tipo_cambio_aplicado,
            requiere_revision=requiere_revision,
            presupuesto_id=presupuesto.id if presupuesto else None,
            consumido_antes=consumido_antes,
            consumido_despues=consumido_despues,
            alerta_presupuesto=alerta_presupuesto,
            actor=Actor(tipo="TITULAR", usuario_id=usuario_id),
        )

        return ResultadoConciliacion(
            compra_id=compra.id,
            requiere_revision=requiere_revision,
            presupuesto_alertado=alerta_presupuesto,
        )

    def recategorizar_compras_de_comercio(
        self, usuario_id: int, comercio_id: int, categoria_id: int
    ) -> int:
        """Aplica una categoría recién asignada a un comercio sobre las compras que
        ya se conciliaron sin categoría -"corregir crea la regla" también corrige
        lo que ya pasó, no solo lo que viene.

        Se llama después de `ComercioService.asignar_categoria`, desde el mismo
        endpoint. Solo toca renglones sin categoría -una compra que sí tenía
        una (una regla la puso, o una corrección anterior) no se pisa sola.
        Devuelve cuántas compras se corrigieron.
        """
        afectadas = self.lineas.listar_sin_categoria_de_comercio(usuario_id, comercio_id)
        if not afectadas:
            return 0

        actor = Actor(tipo="TITULAR", usuario_id=usuario_id)
        for linea, compra in afectadas:
            categoria_anterior_id = linea.categoria_id
            linea.categoria_id = categoria_id
            linea.categorizada_automaticamente = False
            compra.requiere_revision = compra.metodo_pago_id is None

            presupuesto = self.presupuestos.buscar(
                usuario_id, categoria_id, compra.fecha.year, compra.fecha.month
            )
            consumido_antes = consumido_despues = None
            if presupuesto is not None and presupuesto.moneda == compra.moneda:
                consumido_antes = presupuesto.monto_consumido
                presupuesto.monto_consumido = presupuesto.monto_consumido + compra.total
                consumido_despues = presupuesto.monto_consumido

            self.comprobantes.sesion.commit()

            self.bitacora.registrar_evento(
                compra_id=compra.id,
                usuario_id=usuario_id,
                estado_actual=compra.estado.value,
                tipo="CORRECCION_MANUAL",
                datos={
                    "linea_id": linea.id,
                    "categoria_anterior_id": categoria_anterior_id,
                    "categoria_nueva_id": categoria_id,
                },
                actor=actor,
            )
            if presupuesto is not None and consumido_antes is not None:
                self.bitacora.registrar_evento(
                    compra_id=compra.id,
                    usuario_id=usuario_id,
                    estado_actual=compra.estado.value,
                    tipo="IMPACTO_PRESUPUESTO",
                    datos={
                        "presupuesto_id": presupuesto.id,
                        "consumido_antes": str(consumido_antes),
                        "consumido_despues": str(consumido_despues),
                    },
                    actor=actor,
                )

        return len(afectadas)

    def resolver_revision(
        self,
        usuario_id: int,
        compra_id: int,
        metodo_pago_id: int | None,
        categoria_id: int | None,
    ) -> Compra:
        """Corrige a mano el método de pago y/o la categoría de una compra real
        -pensada para las que quedaron `requiere_revision=True` porque la
        ingesta no pudo resolver alguno de los dos solo, aunque corre igual
        sobre cualquier compra si hiciera falta corregir un emparejamiento
        equivocado.

        Ninguno de los dos campos se inventa el otro: si solo se manda uno,
        el otro queda tal como estaba. Si la compra ya tenía categoría y se
        manda una distinta, se corrige el dato pero **no se toca ningún
        presupuesto** -moverla de un presupuesto a otro exigiría revertir lo
        que ya se acumuló en el anterior, que es una operación aparte que
        esto no cubre. Solo se acumula cuando la categoría estaba vacía: ese
        gasto todavía no había impactado ningún presupuesto.
        """
        if metodo_pago_id is None and categoria_id is None:
            raise DatosInvalidos("Hay que corregir al menos el método de pago o la categoría.")

        compra = self.compras.obtener_de_usuario(compra_id, usuario_id)
        if compra is None:
            raise RecursoNoEncontrado(f"La compra {compra_id} no existe en esta cuenta.")

        actor = Actor(tipo="TITULAR", usuario_id=usuario_id)
        metodo_pago_anterior_id = compra.metodo_pago_id

        if metodo_pago_id is not None:
            metodo_pago = self.metodos_pago.obtener_de_usuario(metodo_pago_id, usuario_id)
            if metodo_pago is None:
                raise RecursoNoEncontrado(
                    f"El método de pago {metodo_pago_id} no existe en esta cuenta."
                )
            if not metodo_pago.activo:
                raise ReglaDeNegocioViolada("Ese método de pago está desactivado.")
            # Por la relación, no por la columna: `compra` ya llegó con
            # `metodo_pago` cargado (la trae `CompraRepository.obtener_de_usuario`
            # con joinedload), y asignar solo `metodo_pago_id` dejaría ese
            # atributo desactualizado -la siguiente lectura en esta misma
            # sesión seguiría viendo el método de pago viejo.
            compra.metodo_pago = metodo_pago

        lineas = self.lineas.listar_de_compra(compra.id)
        linea_principal = lineas[0] if lineas else None
        categoria_anterior_id = linea_principal.categoria_id if linea_principal else None
        presupuesto_id = consumido_antes = consumido_despues = None

        if categoria_id is not None:
            categoria = self.categorias.obtener_de_usuario(categoria_id, usuario_id)
            if categoria is None:
                raise RecursoNoEncontrado(f"La categoría {categoria_id} no existe en esta cuenta.")
            if not categoria.es_hoja:
                raise ReglaDeNegocioViolada("La categoría tiene que ser una hoja, no un grupo.")
            if linea_principal is None:
                raise ReglaDeNegocioViolada("Esta compra no tiene ningún renglón que categorizar.")
            # Por la relación, no por la columna -mismo motivo que
            # `compra.metodo_pago` unas líneas arriba: `linea_principal` ya
            # llegó con `categoria` cargada (vía `compra.lineas` en
            # `obtener_de_usuario`).
            linea_principal.categoria = categoria
            linea_principal.categorizada_automaticamente = False

            if categoria_anterior_id is None:
                presupuesto = self.presupuestos.buscar(
                    usuario_id, categoria.id, compra.fecha.year, compra.fecha.month
                )
                if presupuesto is not None and presupuesto.moneda == compra.moneda:
                    presupuesto_id = presupuesto.id
                    consumido_antes = presupuesto.monto_consumido
                    presupuesto.monto_consumido = presupuesto.monto_consumido + compra.total
                    consumido_despues = presupuesto.monto_consumido

        # SQLAlchemy solo sincroniza la columna de la llave foránea (`metodo_pago_id`,
        # `categoria_id`) a partir de la relación en el flush -asignar
        # `compra.metodo_pago`/`linea_principal.categoria` arriba no las deja
        # listas todavía para las comparaciones de abajo sin este flush.
        self.compras.sesion.flush()

        requiere_revision_antes = compra.requiere_revision
        compra.requiere_revision = compra.metodo_pago_id is None or (
            linea_principal is None or linea_principal.categoria_id is None
        )

        self.comprobantes.sesion.commit()

        self.bitacora.registrar_evento(
            compra_id=compra.id,
            usuario_id=usuario_id,
            estado_actual=compra.estado.value,
            tipo="CORRECCION_MANUAL",
            datos={
                "metodo_pago_anterior_id": metodo_pago_anterior_id,
                "metodo_pago_nuevo_id": compra.metodo_pago_id,
                "categoria_anterior_id": categoria_anterior_id,
                "categoria_nueva_id": linea_principal.categoria_id if linea_principal else None,
                "requiere_revision_antes": requiere_revision_antes,
                "requiere_revision_despues": compra.requiere_revision,
            },
            actor=actor,
        )
        if presupuesto_id is not None:
            self.bitacora.registrar_evento(
                compra_id=compra.id,
                usuario_id=usuario_id,
                estado_actual=compra.estado.value,
                tipo="IMPACTO_PRESUPUESTO",
                datos={
                    "presupuesto_id": presupuesto_id,
                    "consumido_antes": str(consumido_antes),
                    "consumido_despues": str(consumido_despues),
                },
                actor=actor,
            )

        return compra

    def desglosar_compra(
        self, usuario_id: int, compra_id: int, lineas: list[LineaDesgloseComando]
    ) -> Compra:
        """Reemplaza TODOS los renglones de una compra real por los que se manden
        -"partir un cargo" en varios, cada uno con su propia categoría.

        Una compra ingerida por correo nace con un único renglón por el monto
        total -el comprobante nunca trae el detalle de qué se compró, ver
        `LineaCompra`- esto es el refinamiento manual que ese renglón único
        dejaba pendiente. La suma de los renglones nuevos tiene que calzar
        exacto con `compra.subtotal`: desglosar reparte cuánto costó la
        compra, nunca lo cambia.

        Revierte el impacto que los renglones viejos ya hubieran dejado en
        algún presupuesto (por su propia categoría y período) y aplica el de
        los nuevos -mismo criterio de "solo si la moneda calza" que
        `conciliar`. Si un renglón nuevo repite la categoría de uno viejo, el
        resultado neto es cero: revertir y reaplicar da lo mismo que no
        tocar nada, sin necesitar codificar esa coincidencia aparte.
        """
        if not lineas:
            raise DatosInvalidos("Una compra necesita al menos un renglón.")

        compra = self.compras.obtener_de_usuario(compra_id, usuario_id)
        if compra is None:
            raise RecursoNoEncontrado(f"La compra {compra_id} no existe en esta cuenta.")

        suma = sum((datos.cantidad * datos.precio_unitario - datos.descuento) for datos in lineas)
        suma = suma.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if suma != compra.subtotal:
            raise DatosInvalidos(
                f"Los renglones suman {suma}, pero la compra es de {compra.subtotal}."
            )

        # Valida cada categoría una sola vez, aunque se repita entre renglones.
        categorias_validadas: set[int] = set()
        for datos in lineas:
            if datos.categoria_id is None or datos.categoria_id in categorias_validadas:
                continue
            categoria = self.categorias.obtener_de_usuario(datos.categoria_id, usuario_id)
            if categoria is None:
                raise RecursoNoEncontrado(
                    f"La categoría {datos.categoria_id} no existe en esta cuenta."
                )
            if not categoria.es_hoja:
                raise ReglaDeNegocioViolada("La categoría tiene que ser una hoja, no un grupo.")
            categorias_validadas.add(datos.categoria_id)

        actor = Actor(tipo="TITULAR", usuario_id=usuario_id)
        lineas_anteriores = self.lineas.listar_de_compra(compra.id)
        impactos_presupuesto: list[tuple[int, Decimal, Decimal]] = []

        def _ajustar_presupuesto(categoria_id: int, delta: Decimal) -> None:
            presupuesto = self.presupuestos.buscar(
                usuario_id, categoria_id, compra.fecha.year, compra.fecha.month
            )
            if presupuesto is not None and presupuesto.moneda == compra.moneda:
                antes = presupuesto.monto_consumido
                presupuesto.monto_consumido = presupuesto.monto_consumido + delta
                impactos_presupuesto.append((presupuesto.id, antes, presupuesto.monto_consumido))

        for linea_vieja in lineas_anteriores:
            if linea_vieja.categoria_id is not None:
                _ajustar_presupuesto(linea_vieja.categoria_id, -linea_vieja.subtotal)

        compra.lineas.clear()  # cascade="all, delete-orphan" se encarga de los viejos
        self.compras.sesion.flush()

        nuevas: list[LineaCompra] = []
        for datos in lineas:
            subtotal_linea = (datos.cantidad * datos.precio_unitario - datos.descuento).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            linea_nueva = LineaCompra(
                compra_id=compra.id,
                categoria_id=datos.categoria_id,
                descripcion=datos.descripcion,
                cantidad=datos.cantidad,
                precio_unitario=datos.precio_unitario,
                descuento=datos.descuento,
                exento_impuesto=datos.exento_impuesto,
                subtotal=subtotal_linea,
                categorizada_automaticamente=False,
            )
            self.lineas.agregar(linea_nueva)
            # Por la relación, no solo por la columna `compra_id` de arriba
            # -mismo motivo que `compra.metodo_pago` en `resolver_revision`:
            # la sesión no tiene `expire_on_commit`, así que si esta compra
            # ya traía `lineas` cargado (lo trae: esta misma consulta lo
            # cargó unas líneas arriba), la colección en memoria se queda
            # vacía para siempre después de `compra.lineas.clear()` a menos
            # que se le agreguen los renglones nuevos acá también -si no, un
            # `SELECT` posterior sobre esta misma compra en esta sesión ni
            # se molesta en volver a traer `lineas`, porque ya la ve "cargada".
            compra.lineas.append(linea_nueva)
            nuevas.append(linea_nueva)
            if datos.categoria_id is not None:
                _ajustar_presupuesto(datos.categoria_id, subtotal_linea)

        requiere_revision_antes = compra.requiere_revision
        compra.requiere_revision = compra.metodo_pago_id is None or any(
            linea.categoria_id is None for linea in nuevas
        )

        self.comprobantes.sesion.commit()

        self.bitacora.registrar_evento(
            compra_id=compra.id,
            usuario_id=usuario_id,
            estado_actual=compra.estado.value,
            tipo="DESGLOSE_MANUAL",
            datos={
                "renglones_anteriores": len(lineas_anteriores),
                "renglones_nuevos": len(nuevas),
                "requiere_revision_antes": requiere_revision_antes,
                "requiere_revision_despues": compra.requiere_revision,
            },
            actor=actor,
        )
        for presupuesto_id, consumido_antes, consumido_despues in impactos_presupuesto:
            self.bitacora.registrar_evento(
                compra_id=compra.id,
                usuario_id=usuario_id,
                estado_actual=compra.estado.value,
                tipo="IMPACTO_PRESUPUESTO",
                datos={
                    "presupuesto_id": presupuesto_id,
                    "consumido_antes": str(consumido_antes),
                    "consumido_despues": str(consumido_despues),
                },
                actor=actor,
            )

        return compra

    def _categorizar(
        self, usuario_id: int, comercio_normalizado: str
    ) -> tuple[int | None, ReglaCategorizacion | None]:
        """Primera regla activa (prioridad ascendente) cuyo patrón está contenido en el
        nombre normalizado del comercio. `None` si ninguna coincide -cae a la
        sugerencia del comercio, resuelta por quien llama."""
        for regla in self.reglas.listar_activas_ordenadas(usuario_id):
            if regla.patron.upper() in comercio_normalizado:
                return regla.categoria_destino_id, regla
        return None, None

    def _tasa_de_conversion(self, moneda: Moneda, fecha: date) -> Decimal:
        """La tasa aplicada a esta compra, guardada como histórico real -no la caché
        en memoria de `TipoCambioService`. Si el servicio de moneda no está
        disponible, se usa 1 -mejor un total sin convertir de más que perder el
        gasto por completo (mismo criterio que `CuentaCorreoService._tipo_de_cambio_de_hoy`)."""
        if self.tipo_cambio_servicio is None:
            return Decimal("1")
        try:
            tipo_de_cambio = self.tipo_cambio_servicio.obtener(fecha)
        except ErrorDeProveedorExterno:
            return Decimal("1")
        self.tipos_cambio.guardar_tasa(
            moneda_origen=moneda,
            moneda_destino=_MONEDA_BASE,
            fecha=tipo_de_cambio.fecha,
            tasa=tipo_de_cambio.venta,
            fuente="BCCR",
        )
        return tipo_de_cambio.venta

    def _escribir_bitacora(
        self,
        compra: Compra,
        usuario_id: int,
        parseado: ComprobanteParseado,
        metodo_pago_id: int | None,
        comercio_nombre: str,
        comercio_normalizado: str,
        categoria_id: int | None,
        regla_aplicada: ReglaCategorizacion | None,
        tipo_cambio_aplicado: Decimal,
        requiere_revision: bool,
        presupuesto_id: int | None,
        consumido_antes: Decimal | None,
        consumido_despues: Decimal | None,
        alerta_presupuesto: bool,
        actor: Actor | None = None,
    ) -> None:
        # Por default, "lo hizo la ingesta automática" -el caso de siempre.
        # `conciliar_manual` pasa un actor `TITULAR`: fue la persona, no un
        # buzón, quien pegó este comprobante.
        actor = actor or Actor(tipo="SERVICIO", nombre="ingesta-correo")

        def registrar(tipo: str, datos: dict) -> None:
            self.bitacora.registrar_evento(
                compra_id=compra.id,
                usuario_id=usuario_id,
                estado_actual=compra.estado.value,
                tipo=tipo,
                datos=datos,
                actor=actor,
            )

        registrar(
            "PARSEO_COMPROBANTE",
            {
                "confianza": parseado.confianza,
                "campos_extraidos": [
                    campo
                    for campo in ("comercio", "monto", "moneda", "fecha", "ultimos_cuatro")
                    if getattr(parseado, campo, None) is not None
                ],
            },
        )
        registrar(
            "EMPAREJAMIENTO_METODO_PAGO",
            {
                "ultimos_cuatro": parseado.ultimos_cuatro,
                "resultado": "EMPAREJADO" if metodo_pago_id else "SIN_COINCIDENCIA",
                "metodo_pago_id": metodo_pago_id,
            },
        )
        registrar(
            "RESOLUCION_COMERCIO",
            {
                "nombre_crudo": parseado.comercio,
                "nombre_normalizado": comercio_normalizado,
                "comercio_id": compra.comercio_id,
            },
        )
        registrar(
            "CATEGORIZACION_AUTOMATICA",
            {
                "origen": "REGLA" if regla_aplicada else ("COMERCIO" if categoria_id else None),
                "regla_id": regla_aplicada.id if regla_aplicada else None,
                "categoria_id": categoria_id,
            },
        )
        if tipo_cambio_aplicado != Decimal("1"):
            registrar(
                "CONVERSION_MONEDA",
                {
                    "moneda_origen": compra.moneda.value,
                    "moneda_destino": _MONEDA_BASE.value,
                    "tasa": str(tipo_cambio_aplicado),
                    "monto_antes": str(compra.total),
                    "monto_despues": str(compra.total_moneda_base),
                },
            )
        registrar(
            "CAMBIO_ESTADO",
            {"anterior": None, "nuevo": compra.estado.value},
        )
        if presupuesto_id is not None and consumido_antes is not None:
            registrar(
                "IMPACTO_PRESUPUESTO",
                {
                    "presupuesto_id": presupuesto_id,
                    "consumido_antes": str(consumido_antes),
                    "consumido_despues": str(consumido_despues),
                },
            )
        if alerta_presupuesto:
            registrar("ALERTA_PRESUPUESTO", {"presupuesto_id": presupuesto_id})
        if requiere_revision:
            registrar(
                "REVISION_REQUERIDA",
                {
                    "motivo": "SIN_METODO_DE_PAGO" if metodo_pago_id is None else "SIN_CATEGORIA",
                },
            )
