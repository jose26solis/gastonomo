"""Reglas de negocio de las cuentas de correo vinculadas."""

import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from app.business.errors import ErrorDeProveedorExterno, RecursoNoEncontrado, ReglaDeNegocioViolada
from app.business.parsers.comprobante_bac import (
    DOMINIO_REMITENTE_BAC,
    ComprobanteParseado,
    parsear_comprobante_bac,
)
from app.business.seguridad.cifrado import cifrar, descifrar
from app.business.services.correo.proveedor import MensajeResumido, ProveedorDeCorreo
from app.business.services.resumen_service import ResumenFinanciero, agrupar_por_mes
from app.business.services.tipo_cambio_service import (
    TipoCambioService,
    TipoDeCambio,
    convertir,
)
from app.data.models.comprobante import Comprobante
from app.data.models.cuenta_correo import CuentaCorreo
from app.data.models.enums import EstadoCuentaCorreo, ProveedorCorreo
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository


@dataclass(frozen=True)
class VincularCuentaComando:
    """Orden que recibe el negocio tras volver del proveedor con un código."""

    usuario_id: int
    proveedor: ProveedorCorreo
    codigo: str


@dataclass(frozen=True)
class ResultadoDeSincronizacion:
    """Lo que devuelve pedir explícitamente que se traiga el correo nuevo."""

    comprobantes_nuevos: int
    comprobantes_totales: int
    sincronizado_en: datetime


@dataclass(frozen=True)
class ComprobanteConFuente:
    """Un comprobante ya sincronizado, junto con la cuenta de la que vino.

    Con una sola cuenta vinculada nunca hizo falta saber esto -todo salía del
    mismo lugar. Con varias (Outlook y Gmail a la vez, por ejemplo),
    `comprobantes_de_usuario` combina el historial de todas y sin esta
    etiqueta no habría forma de mostrar de qué bandeja vino cada movimiento.
    """

    comprobante: ComprobanteParseado
    cuenta_correo_id: int
    proveedor: ProveedorCorreo
    direccion: str
    # El tipo de cambio que se guardó junto al comprobante al sincronizarlo, si
    # lo hubo. Es el que se prefiere al convertir: es más cercano a la fecha de
    # la compra que el de hoy.
    tipo_cambio_venta: Decimal | None = None
    tipo_cambio_fecha: date | None = None
    # Lo que decía el comprobante antes de convertirlo, cuando se pidió el
    # resumen en una sola moneda. Se conserva para poder mostrar "$6.00" y no
    # solo el equivalente: el monto convertido es una referencia, el que el
    # banco cobró de verdad es este.
    monto_original: Decimal | None = None
    moneda_original: str | None = None


def convertidos_a(
    items: list[ComprobanteConFuente], moneda_destino: str, tipo_de_cambio: TipoDeCambio
) -> list[ComprobanteConFuente]:
    """Pasa todos los comprobantes a una sola moneda, guardando el monto original.

    Sirve para responder "cuánto gasté en total", sin más: sumar colones y
    dólares sin convertir daría un número inventado, y mostrarlos separados
    no responde la pregunta. Convertir con una tasa real y decir cuál se usó
    sí la responde.

    Cada comprobante se convierte con **la tasa que se le guardó al
    sincronizarlo**, que es la que regía cerca de la fecha de la compra. Los
    que no tengan ninguna -los que ya estaban guardados antes de que se
    empezara a sellarlos- caen a `tipo_de_cambio`, el de hoy. Quien muestre
    estos totales tiene que poder decir cuáles son cuáles; para eso cada
    comprobante conserva `tipo_cambio_fecha`.
    """
    convertidos = []
    for item in items:
        comprobante = item.comprobante
        if (
            comprobante.monto is None
            or comprobante.moneda is None
            or comprobante.moneda == moneda_destino
        ):
            convertidos.append(item)
            continue
        venta = item.tipo_cambio_venta or tipo_de_cambio.venta
        convertidos.append(
            replace(
                item,
                comprobante=replace(
                    comprobante,
                    monto=convertir(comprobante.monto, comprobante.moneda, moneda_destino, venta),
                    moneda=moneda_destino,
                ),
                monto_original=comprobante.monto,
                moneda_original=comprobante.moneda,
                # Si se usó la de hoy por no haber guardada, queda dicho.
                tipo_cambio_venta=venta,
                tipo_cambio_fecha=item.tipo_cambio_fecha or tipo_de_cambio.fecha,
            )
        )
    return convertidos


@dataclass(frozen=True)
class BancoDetectado:
    """Un remitente que parece un banco, agrupado de los resultados de buscar "banco".

    Es un candidato, no una confirmación: que "banco" aparezca en el asunto
    o el cuerpo de un correo no garantiza que el remitente sea financiero de
    verdad -podría ser un boletín que lo menciona de pasada. `es_bac` marca
    el único caso que además de detectarse ya se lee de verdad
    (`comprobante_bac.py`); el resto son candidatos sin parser todavía.
    """

    dominio: str
    remitente_ejemplo: str
    cantidad_mensajes: int
    mensaje_mas_reciente: datetime | None
    es_bac: bool
    cuenta_correo_id: int
    proveedor: ProveedorCorreo
    direccion: str


_PATRON_CORREO = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")


def _dominio_de(remitente: str) -> str:
    """Saca el dominio de un remitente, sea `correo@dominio.cr` o `Nombre <correo@dominio.cr>`.

    Gmail devuelve el encabezado `From` tal cual vino en el correo -puede
    traer el nombre para mostrar delante-, mientras que Outlook ya entrega
    la dirección sola. Buscar el patrón de correo en vez de asumir una
    forma fija cubre los dos casos con el mismo código.
    """
    coincidencia = _PATRON_CORREO.search(remitente)
    return coincidencia.group(1).lower() if coincidencia else remitente.lower()


def _fila_desde_parseado(
    cuenta_correo_id: int,
    mensaje_id: str,
    parseado: ComprobanteParseado,
    tipo_de_cambio: TipoDeCambio | None = None,
) -> Comprobante:
    return Comprobante(
        cuenta_correo_id=cuenta_correo_id,
        mensaje_id=mensaje_id,
        tipo_cambio_venta=tipo_de_cambio.venta if tipo_de_cambio else None,
        tipo_cambio_fecha=tipo_de_cambio.fecha if tipo_de_cambio else None,
        banco=parseado.banco,
        comercio=parseado.comercio,
        ciudad=parseado.ciudad,
        pais=parseado.pais,
        fecha=parseado.fecha,
        marca_tarjeta=parseado.marca_tarjeta,
        ultimos_cuatro=parseado.ultimos_cuatro,
        autorizacion=parseado.autorizacion,
        referencia=parseado.referencia,
        tipo_transaccion=parseado.tipo_transaccion,
        moneda=parseado.moneda,
        monto=parseado.monto,
        confianza=parseado.confianza,
    )


def _parseado_desde_fila(fila: Comprobante) -> ComprobanteParseado:
    return ComprobanteParseado(
        banco=fila.banco,
        comercio=fila.comercio,
        ciudad=fila.ciudad,
        pais=fila.pais,
        fecha=fila.fecha,
        marca_tarjeta=fila.marca_tarjeta,
        ultimos_cuatro=fila.ultimos_cuatro,
        autorizacion=fila.autorizacion,
        referencia=fila.referencia,
        tipo_transaccion=fila.tipo_transaccion,
        moneda=fila.moneda,
        monto=fila.monto,
        confianza=fila.confianza,
    )


class CuentaCorreoService:
    """Aplica las reglas del dominio sobre los buzones vinculados de un titular.

    No sabe hablar HTTP con Microsoft ni con Google: eso lo hacen los
    `ProveedorDeCorreo` que recibe inyectados, uno por cada `ProveedorCorreo`
    que el sistema soporta. Este servicio solo decide qué hacer con lo que el
    proveedor devuelve -cifrar los tokens, crear o actualizar la cuenta,
    confirmar la transacción- y nunca con cuál proveedor específico habla.
    """

    def __init__(
        self,
        cuenta_correo_repository: CuentaCorreoRepository,
        usuario_repository: UsuarioRepository,
        proveedores: dict[ProveedorCorreo, ProveedorDeCorreo],
        comprobante_repository: ComprobanteRepository,
        tipo_cambio_service: TipoCambioService | None = None,
    ) -> None:
        self.cuentas = cuenta_correo_repository
        self.usuarios = usuario_repository
        self.proveedores = proveedores
        self.comprobantes = comprobante_repository
        # Opcional a propósito: sin él la sincronización funciona igual, solo
        # que los comprobantes quedan sin tipo de cambio guardado. Leer correo
        # no puede depender de que un servicio de moneda esté disponible.
        self.tipo_cambio = tipo_cambio_service

    def url_de_autorizacion(self, usuario_id: int, proveedor: ProveedorCorreo, estado: str) -> str:
        """Arma la URL a la que se manda al titular para que autorice el acceso."""
        self._asegurar_usuario_activo(usuario_id)
        return self._proveedor(proveedor).url_de_autorizacion(estado)

    def vincular(self, comando: VincularCuentaComando) -> CuentaCorreo:
        """Cambia el código de autorización por tokens y crea o actualiza la cuenta.

        Vincular un buzón que ya estaba vinculado no duplica la fila: renueva
        sus tokens y la vuelve a marcar activa. Es lo que pasa, por ejemplo,
        cuando el titular reautoriza tras revocar el acceso desde su cuenta de
        Microsoft o Google.
        """
        self._asegurar_usuario_activo(comando.usuario_id)
        proveedor = self._proveedor(comando.proveedor)

        tokens = proveedor.intercambiar_codigo(comando.codigo)
        direccion = proveedor.obtener_direccion(tokens.token_acceso)

        cuenta = self.cuentas.buscar_por_direccion(comando.usuario_id, comando.proveedor, direccion)
        if cuenta is None:
            cuenta = CuentaCorreo(
                usuario_id=comando.usuario_id,
                proveedor=comando.proveedor,
                direccion=direccion,
            )

        cuenta.token_acceso_cifrado = cifrar(tokens.token_acceso)
        if tokens.token_refresco is not None:
            cuenta.token_refresco_cifrado = cifrar(tokens.token_refresco)
        cuenta.expira_en = tokens.expira_en
        cuenta.estado = EstadoCuentaCorreo.ACTIVA

        self.cuentas.agregar(cuenta)
        self.cuentas.sesion.commit()
        return cuenta

    def listar(self, usuario_id: int) -> list[CuentaCorreo]:
        """Lista los buzones vinculados de un titular."""
        self._asegurar_usuario_activo(usuario_id)
        return self.cuentas.listar_de_usuario(usuario_id)

    def probar_conexion(
        self, usuario_id: int, cuenta_id: int, limite: int = 5
    ) -> list[MensajeResumido]:
        """Trae los últimos mensajes del buzón para confirmar que el token sirve.

        No descarga el cuerpo de ningún mensaje -solo remitente, asunto y
        fecha- porque esto es una prueba de conexión, no la ingesta real. La
        ingesta que sí lee y descarta el contenido es un proceso aparte.

        Por ahora solo trae correos de BAC (`DOMINIO_REMITENTE_BAC`): es el
        único banco cuyo formato ya sabe leer `comprobante_bac.py`, y mostrar
        mensajes de otros remitentes solo agregaría ruido sin que el sistema
        pueda hacer nada con ellos todavía. Cuando se sume el parser de otro
        banco, este filtro tiene que dejar de ser un valor fijo.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        token_acceso = self._token_acceso_vigente(cuenta)
        try:
            mensajes = self._proveedor(cuenta.proveedor).listar_mensajes_recientes(
                token_acceso, limite, remitente_contiene=DOMINIO_REMITENTE_BAC
            )
        except Exception:
            cuenta.estado = EstadoCuentaCorreo.ERROR
            self.cuentas.sesion.commit()
            raise
        cuenta.ultima_sincronizacion = datetime.now(UTC)
        self.cuentas.sesion.commit()
        return mensajes

    def leer_comprobante(
        self, usuario_id: int, cuenta_id: int, mensaje_id: str
    ) -> ComprobanteParseado:
        """Trae el cuerpo de un mensaje y lo pasa por el parser de BAC.

        Es el primer eslabón real de la ingesta: confirma que se puede llegar
        desde "un id de mensaje que devolvió `probar_conexion`" hasta "los
        campos de una compra", sin todavía persistir nada. Guardar el
        resultado como una `Compra` de verdad es el siguiente paso, cuando
        existan esas entidades -por eso esto no marca la cuenta en `ERROR`
        si un mensaje puntual falla: eso lo reservamos para cuando falla la
        conexión completa, en `probar_conexion`.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        token_acceso = self._token_acceso_vigente(cuenta)
        cuerpo = self._proveedor(cuenta.proveedor).obtener_cuerpo_de_mensaje(
            token_acceso, mensaje_id
        )
        return parsear_comprobante_bac(cuerpo)

    def resumen_financiero(
        self, usuario_id: int, cuenta_id: int, limite: int = 200
    ) -> ResumenFinanciero:
        """Suma por mes los comprobantes ya sincronizados de la bandeja.

        Antes esto releía y reparseaba la bandeja completa del proveedor en
        cada llamada -con una bandeja de varios años, varios segundos cada
        vez. Ahora primero sincroniza (`_sincronizar_comprobantes`, que solo
        pide al proveedor lo que todavía no está guardado) y lee el resto de
        la caché local: la primera vez sigue tardando lo mismo que antes,
        pero una bandeja ya al día responde casi al instante.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        self._sincronizar_comprobantes(cuenta, limite)

        comprobantes = [
            _parseado_desde_fila(fila) for fila in self.comprobantes.listar_de_cuenta(cuenta_id)
        ]
        return ResumenFinanciero(comprobantes=comprobantes, por_mes=agrupar_por_mes(comprobantes))

    def comprobantes_de_usuario(
        self, usuario_id: int, limite: int = 200
    ) -> list[ComprobanteConFuente]:
        """Sincroniza y combina los comprobantes de TODAS las cuentas activas del titular.

        Antes cada pantalla mostraba una sola cuenta -la primera que
        encontrara activa. Con más de un buzón vinculado eso significaba que,
        según cuál hubiera quedado activa más recientemente, el resto del
        historial simplemente desaparecía de la vista aunque la cuenta
        siguiera vinculada y con datos reales. Esto junta el historial de
        todas las cuentas activas, etiquetando cada comprobante con de cuál
        salió.

        Una cuenta rota (token vencido sin refresco, o un error del
        proveedor al listar mensajes) se salta en vez de tirar abajo el
        resto: un buzón que falla no debería esconder los otros que sí
        funcionan.
        """
        self._asegurar_usuario_activo(usuario_id)
        cuentas_activas = [
            c
            for c in self.cuentas.listar_de_usuario(usuario_id)
            if c.estado == EstadoCuentaCorreo.ACTIVA
        ]

        con_fuente: list[ComprobanteConFuente] = []
        for cuenta in cuentas_activas:
            try:
                self._sincronizar_comprobantes(cuenta, limite)
            except (ReglaDeNegocioViolada, ErrorDeProveedorExterno):
                continue
            for fila in self.comprobantes.listar_de_cuenta(cuenta.id):
                con_fuente.append(
                    ComprobanteConFuente(
                        comprobante=_parseado_desde_fila(fila),
                        cuenta_correo_id=cuenta.id,
                        proveedor=cuenta.proveedor,
                        direccion=cuenta.direccion,
                        tipo_cambio_venta=fila.tipo_cambio_venta,
                        tipo_cambio_fecha=fila.tipo_cambio_fecha,
                    )
                )
        return con_fuente

    def resumen_financiero_de_usuario(
        self, usuario_id: int, limite: int = 200
    ) -> ResumenFinanciero:
        """El mismo resumen por mes que `resumen_financiero`, pero de todas las
        cuentas activas del titular en vez de una sola. Ver `comprobantes_de_usuario`.
        """
        comprobantes = [c.comprobante for c in self.comprobantes_de_usuario(usuario_id, limite)]
        return ResumenFinanciero(comprobantes=comprobantes, por_mes=agrupar_por_mes(comprobantes))

    def detectar_bancos(self, usuario_id: int, limite: int = 30) -> list[BancoDetectado]:
        """Busca "banco" en cada buzón activo del titular y agrupa los remitentes por dominio.

        A diferencia de `comprobantes_de_usuario`, esto no sincroniza ni
        guarda nada -es una búsqueda de punta a punta, sin caché, porque no
        hay ningún `Comprobante` que persistir para un remitente que
        todavía no tiene parser. Sirve para que la pantalla de Bancos deje
        de mostrar una lista inventada y muestre en su lugar qué otros
        bancos parecen estar escribiéndole al titular, aunque Gastonomo
        todavía no sepa leerlos.
        """
        self._asegurar_usuario_activo(usuario_id)
        cuentas_activas = [
            c
            for c in self.cuentas.listar_de_usuario(usuario_id)
            if c.estado == EstadoCuentaCorreo.ACTIVA
        ]

        agrupado: dict[tuple[int, str], list[MensajeResumido]] = {}
        cuenta_por_grupo: dict[tuple[int, str], CuentaCorreo] = {}
        for cuenta in cuentas_activas:
            try:
                token = self._token_acceso_vigente(cuenta)
                mensajes = self._proveedor(cuenta.proveedor).buscar_por_texto(
                    token, "banco", limite
                )
            except (ReglaDeNegocioViolada, ErrorDeProveedorExterno):
                continue
            for mensaje in mensajes:
                clave = (cuenta.id, _dominio_de(mensaje.remitente))
                agrupado.setdefault(clave, []).append(mensaje)
                cuenta_por_grupo[clave] = cuenta

        detectados = []
        for (cuenta_id, dominio), mensajes in agrupado.items():
            cuenta = cuenta_por_grupo[(cuenta_id, dominio)]
            recibidos = [m.recibido_en for m in mensajes if m.recibido_en is not None]
            detectados.append(
                BancoDetectado(
                    dominio=dominio,
                    remitente_ejemplo=mensajes[0].remitente,
                    cantidad_mensajes=len(mensajes),
                    mensaje_mas_reciente=max(recibidos) if recibidos else None,
                    es_bac=DOMINIO_REMITENTE_BAC in dominio,
                    cuenta_correo_id=cuenta.id,
                    proveedor=cuenta.proveedor,
                    direccion=cuenta.direccion,
                )
            )
        # BAC primero -ya se lee de verdad-, después por cuántos mensajes se
        # encontraron: un dominio con un solo mensaje suelto es más probable
        # que sea ruido ("banco de preguntas", una promoción que lo nombra de
        # pasada) que uno con varios.
        detectados.sort(key=lambda b: (not b.es_bac, -b.cantidad_mensajes))
        return detectados

    def sincronizar(
        self, usuario_id: int, cuenta_id: int, limite: int = 200
    ) -> ResultadoDeSincronizacion:
        """Trae explícitamente el correo nuevo de un buzón y lo agrega a la caché local.

        `resumen_financiero` ya sincroniza sola en cada llamada; este método
        existe para cuando alguien quiere forzar el pull sin pedir además todo
        el resumen, o para confirmar cuánto trajo de nuevo.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        nuevos = self._sincronizar_comprobantes(cuenta, limite)
        totales = len(self.comprobantes.listar_de_cuenta(cuenta_id))
        assert cuenta.ultima_sincronizacion is not None  # _sincronizar_comprobantes la puso
        return ResultadoDeSincronizacion(
            comprobantes_nuevos=nuevos,
            comprobantes_totales=totales,
            sincronizado_en=cuenta.ultima_sincronizacion,
        )

    def _sincronizar_comprobantes(self, cuenta: CuentaCorreo, limite: int) -> int:
        """Trae y guarda los mensajes de BAC que la caché local todavía no tiene.

        `mensaje_id` es la clave de deduplicación: un mensaje ya guardado
        nunca vuelve a pedírsele el cuerpo al proveedor. Eso es lo que hace
        que sincronizar una bandeja ya al día sea prácticamente instantáneo
        -la única petición real es la de listar metadatos, no una por mensaje.

        Un mensaje puntual que no se puede leer (borrado entretanto, error
        transitorio del proveedor) se descarta y no tira abajo el resto de
        la sincronización.
        """
        token_acceso = self._token_acceso_vigente(cuenta)
        proveedor = self._proveedor(cuenta.proveedor)
        mensajes = proveedor.listar_mensajes_recientes(
            token_acceso, limite, remitente_contiene=DOMINIO_REMITENTE_BAC
        )

        ya_guardados = self.comprobantes.mensajes_ya_sincronizados(
            cuenta.id, [mensaje.identificador for mensaje in mensajes]
        )
        nuevos = [m for m in mensajes if m.identificador not in ya_guardados]

        # Una sola consulta para todo el lote, y solo si hay algo que guardar:
        # el tipo de cambio es el mismo para todos los que se guardan ahora.
        tipo_de_cambio = self._tipo_de_cambio_de_hoy() if nuevos else None

        agregados = 0
        for mensaje in nuevos:
            try:
                cuerpo = proveedor.obtener_cuerpo_de_mensaje(token_acceso, mensaje.identificador)
            except ErrorDeProveedorExterno:
                continue
            parseado = parsear_comprobante_bac(cuerpo)
            self.comprobantes.agregar(
                _fila_desde_parseado(cuenta.id, mensaje.identificador, parseado, tipo_de_cambio)
            )
            agregados += 1

        cuenta.ultima_sincronizacion = datetime.now(UTC)
        self.cuentas.sesion.commit()
        return agregados

    def _tipo_de_cambio_de_hoy(self) -> TipoDeCambio | None:
        """El tipo de cambio para sellar los comprobantes que se van a guardar.

        Que no haya -porque no se inyectó el servicio, o porque hoy no responde
        ni el Banco Central ni Hacienda- no puede impedir guardar el
        comprobante: el gasto es el dato importante, la tasa es un extra que
        mejora la conversión posterior. Sin ella, esos comprobantes se
        convierten con la tasa del día en que se consulten, como antes.
        """
        if self.tipo_cambio is None:
            return None
        try:
            return self.tipo_cambio.obtener()
        except Exception:
            # Se atrapa todo a propósito, y solo acá. En el resto del sistema
            # tragarse una excepción sin mirar el tipo esconde errores; en este
            # punto concreto es lo correcto, porque el valor es opcional por
            # diseño y la alternativa es perder el gasto -que sí es el dato
            # importante- por un problema de un servicio de moneda.
            #
            # `ErrorDeProveedorExterno` solo no alcanza: un `httpx.ReadTimeout`
            # de Hacienda se coló por acá y tumbó la sincronización con un 500.
            # Eso ya se arregló en el origen (`TipoCambioService._pedir`), pero
            # esta garantía no debería depender de que el otro servicio se
            # porte bien.
            return None

    def desvincular(self, usuario_id: int, cuenta_id: int) -> None:
        """Desvincula un buzón sin borrar la cuenta del titular.

        Se limpian los tokens -ya no sirven de nada guardados, y son el dato
        más sensible de la fila- pero la fila se conserva en estado
        `DESVINCULADA` para que el historial de qué buzones tuvo alguna vez
        siga siendo consultable.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        cuenta.token_acceso_cifrado = None
        cuenta.token_refresco_cifrado = None
        cuenta.estado = EstadoCuentaCorreo.DESVINCULADA
        self.cuentas.sesion.commit()

    def _token_acceso_vigente(self, cuenta: CuentaCorreo) -> str:
        if cuenta.estado == EstadoCuentaCorreo.DESVINCULADA:
            raise ReglaDeNegocioViolada(f"La cuenta {cuenta.id} ya fue desvinculada.")
        if cuenta.token_acceso_cifrado is None:
            raise ReglaDeNegocioViolada(f"La cuenta {cuenta.id} no tiene un token guardado.")

        ahora = datetime.now(UTC)
        vencido = cuenta.expira_en is not None and cuenta.expira_en <= ahora
        if not vencido:
            return descifrar(cuenta.token_acceso_cifrado)

        if cuenta.token_refresco_cifrado is None:
            cuenta.estado = EstadoCuentaCorreo.TOKEN_EXPIRADO
            self.cuentas.sesion.commit()
            raise ReglaDeNegocioViolada(
                f"El token de la cuenta {cuenta.id} vencio y no hay token de refresco; "
                "hay que volver a vincularla."
            )

        tokens = self._proveedor(cuenta.proveedor).refrescar(
            descifrar(cuenta.token_refresco_cifrado)
        )
        cuenta.token_acceso_cifrado = cifrar(tokens.token_acceso)
        if tokens.token_refresco is not None:
            cuenta.token_refresco_cifrado = cifrar(tokens.token_refresco)
        cuenta.expira_en = tokens.expira_en
        cuenta.estado = EstadoCuentaCorreo.ACTIVA
        self.cuentas.sesion.commit()
        return tokens.token_acceso

    def _obtener_cuenta_del_titular(self, usuario_id: int, cuenta_id: int) -> CuentaCorreo:
        self._asegurar_usuario_activo(usuario_id)
        cuenta = self.cuentas.obtener_de_usuario(cuenta_id, usuario_id)
        if cuenta is None:
            raise RecursoNoEncontrado(f"La cuenta de correo {cuenta_id} no existe en esta cuenta.")
        return cuenta

    def _proveedor(self, proveedor: ProveedorCorreo) -> ProveedorDeCorreo:
        return self.proveedores[proveedor]

    def _asegurar_usuario_activo(self, usuario_id: int) -> None:
        usuario = self.usuarios.obtener_por_id(usuario_id)
        if usuario is None:
            raise RecursoNoEncontrado(f"El usuario {usuario_id} no existe.")
        if not usuario.activo:
            raise ReglaDeNegocioViolada(f"El usuario {usuario_id} esta desactivado.")
