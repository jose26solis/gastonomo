"""Endpoints de vinculación de buzones de correo (Outlook, Gmail).

El router no habla con Microsoft ni con Google: arma el comando, llama al
servicio y traduce el resultado. Toda la conversación HTTP con los proveedores
vive en `business/services/correo/`.

## Cómo viaja el `usuario_id` a través del proveedor

Vincular un correo son tres saltos: el navegador va de esta API al proveedor,
el titular autoriza ahí, y el proveedor devuelve al navegador a esta misma API
con un código. En ese viaje redondo el sistema no controla nada de lo que pasa
en el medio, así que no puede usar una sesión de servidor para recordar quién iba
vinculando: cuando el proveedor completa la vuelta, tiene que decírselo él mismo.

Por eso el parámetro `state` que exige el estándar OAuth2 no es un valor suelto:
es el `usuario_id` cifrado con la misma clave con la que se cifran los tokens.
El proveedor lo devuelve intacto -no lo lee, no lo modifica- y el callback lo
descifra para saber a quién pertenece la cuenta que se está creando. No hace
falta guardar ese estado en ningún lado ni limpiarlo después.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Query

from app.business.errors import DatosInvalidos
from app.business.seguridad.cifrado import TokenIlegible, cifrar, descifrar
from app.business.services.cuenta_correo_service import (
    ComprobanteConFuente,
    VincularCuentaComando,
    convertidos_a,
)
from app.business.services.resumen_service import agrupar_por_mes, filtrar_del_periodo
from app.data.models.enums import Moneda, ProveedorCorreo
from app.presentation.dependencies import (
    ServicioDeComercios,
    ServicioDeCuentasCorreo,
    ServicioDePresupuestos,
    ServicioDeTipoCambio,
    VerificarTitular,
)
from app.presentation.schemas import (
    BancoDetectadoResponse,
    ComercioClasificadoResponse,
    ComprobanteConFuenteResponse,
    ComprobanteParseadoResponse,
    CuentaCorreoResponse,
    EstadoDePresupuestoResponse,
    IniciarVinculacionResponse,
    MensajeResumidoResponse,
    ResultadoDeSincronizacionResponse,
    ResumenFinancieroConFuenteResponse,
    ResumenFinancieroResponse,
    ResumenMensualResponse,
    TipoDeCambioResponse,
    TransferenciaSinpeResponse,
)

router = APIRouter(prefix="/api/cuentas-correo", tags=["cuentas-correo"])


_TTL_ESTADO_SEGUNDOS = 600  # 10 minutos: de sobra para completar el handshake, poco para reusar

# El `state` de OAuth2 y el token de sesión (`auth_service.py`) se cifran con
# la misma clave simétrica y tienen la misma forma superficial -un JSON con
# `usuario_id`. Sin este campo, un `state` interceptado durante el
# handshake -viaja por la URL, visible en el historial del navegador y en
# los logs del proveedor- serviría como token de sesión válido por sus 10
# minutos de vida, y viceversa. Ver la nota equivalente en `auth_service.py`.
_PROPOSITO_ESTADO = "vincular-correo"


def _codificar_estado(usuario_id: int) -> str:
    return cifrar(json.dumps({"usuario_id": usuario_id, "proposito": _PROPOSITO_ESTADO}))


def _decodificar_estado(estado: str) -> int:
    try:
        datos = json.loads(descifrar(estado, ttl_segundos=_TTL_ESTADO_SEGUNDOS))
        if datos.get("proposito") != _PROPOSITO_ESTADO:
            raise ValueError("no es un token de vinculación")
        return int(datos["usuario_id"])
    except (TokenIlegible, ValueError, KeyError, TypeError) as error:
        raise DatosInvalidos("El parametro state no es valido o expiro.") from error


@router.get(
    "/outlook/iniciar",
    response_model=IniciarVinculacionResponse,
    summary="Iniciar la vinculación de un buzón de Outlook",
)
def iniciar_outlook(
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> IniciarVinculacionResponse:
    """Devuelve la URL de Microsoft a la que el frontend debe redirigir al titular."""
    url = servicio.url_de_autorizacion(
        usuario_id, ProveedorCorreo.OUTLOOK, _codificar_estado(usuario_id)
    )
    return IniciarVinculacionResponse(url_autorizacion=url)


@router.get(
    "/outlook/callback",
    response_model=CuentaCorreoResponse,
    summary="Recibir el código de autorización de Microsoft",
)
def callback_outlook(
    servicio: ServicioDeCuentasCorreo, code: str, state: str
) -> CuentaCorreoResponse:
    """Cambia el código de Microsoft por tokens y guarda la cuenta vinculada."""
    usuario_id = _decodificar_estado(state)
    comando = VincularCuentaComando(
        usuario_id=usuario_id, proveedor=ProveedorCorreo.OUTLOOK, codigo=code
    )
    return CuentaCorreoResponse.model_validate(servicio.vincular(comando))


@router.get(
    "/gmail/iniciar",
    response_model=IniciarVinculacionResponse,
    summary="Iniciar la vinculación de un buzón de Gmail",
)
def iniciar_gmail(
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> IniciarVinculacionResponse:
    """Devuelve la URL de Google a la que el frontend debe redirigir al titular."""
    url = servicio.url_de_autorizacion(
        usuario_id, ProveedorCorreo.GMAIL, _codificar_estado(usuario_id)
    )
    return IniciarVinculacionResponse(url_autorizacion=url)


@router.get(
    "/gmail/callback",
    response_model=CuentaCorreoResponse,
    summary="Recibir el código de autorización de Google",
)
def callback_gmail(
    servicio: ServicioDeCuentasCorreo, code: str, state: str
) -> CuentaCorreoResponse:
    """Cambia el código de Google por tokens y guarda la cuenta vinculada."""
    usuario_id = _decodificar_estado(state)
    comando = VincularCuentaComando(
        usuario_id=usuario_id, proveedor=ProveedorCorreo.GMAIL, codigo=code
    )
    return CuentaCorreoResponse.model_validate(servicio.vincular(comando))


@router.get("", response_model=list[CuentaCorreoResponse], summary="Listar los buzones vinculados")
def listar_cuentas(
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> list[CuentaCorreoResponse]:
    """Lista los buzones vinculados del titular indicado."""
    return [CuentaCorreoResponse.model_validate(c) for c in servicio.listar(usuario_id)]


def _response_desde_con_fuente(item: ComprobanteConFuente) -> ComprobanteConFuenteResponse:
    base = ComprobanteParseadoResponse.model_validate(item.comprobante)
    return ComprobanteConFuenteResponse(
        **base.model_dump(),
        cuenta_correo_id=item.cuenta_correo_id,
        proveedor=item.proveedor,
        direccion_cuenta=item.direccion,
        monto_original=item.monto_original,
        moneda_original=item.moneda_original,
        tipo_cambio_fecha=item.tipo_cambio_fecha,
    )


@router.get(
    "/resumen-financiero",
    response_model=ResumenFinancieroConFuenteResponse,
    summary="Combinar el resumen financiero de todas las cuentas activas del titular",
)
def resumen_financiero_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_tipo_cambio: ServicioDeTipoCambio,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
    moneda: Annotated[
        Moneda | None,
        Query(
            description="Convertir todo a esta moneda. Sin este parámetro, cada movimiento "
            "conserva la suya y las monedas no se suman entre sí."
        ),
    ] = None,
) -> ResumenFinancieroConFuenteResponse:
    """Igual que `/{cuenta_id}/resumen-financiero`, pero sumando el historial de
    TODAS las cuentas de correo activas del titular en vez de una sola -así un
    titular con Outlook y Gmail vinculados a la vez ve su gasto real completo
    en un solo lugar, con cada movimiento marcado según de qué bandeja salió.

    Con `moneda`, todo se convierte a esa moneda antes de sumar, para poder
    dar un balance único. La tasa usada viaja en `conversion`: un total
    convertido sin decir con qué tasa se armó no es un dato verificable. Sin
    `moneda`, el comportamiento es el de siempre -una fila de `por_mes` por
    cada moneda, sin mezclarlas.
    """
    con_fuente = servicio.comprobantes_de_usuario(usuario_id, limite)
    conversion = None
    if moneda is not None:
        conversion = servicio_tipo_cambio.obtener()
        con_fuente = convertidos_a(con_fuente, moneda.value, conversion)

    comprobantes = [c.comprobante for c in con_fuente]
    return ResumenFinancieroConFuenteResponse(
        comprobantes=[_response_desde_con_fuente(c) for c in con_fuente],
        por_mes=[ResumenMensualResponse.model_validate(r) for r in agrupar_por_mes(comprobantes)],
        conversion=TipoDeCambioResponse.model_validate(conversion) if conversion else None,
    )


@router.get(
    "/transferencias-sinpe",
    response_model=list[TransferenciaSinpeResponse],
    summary="Transferencias SINPE recibidas, combinando todas las cuentas activas del titular",
)
def transferencias_sinpe_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=100, gt=0, le=300),
) -> list[TransferenciaSinpeResponse]:
    """Busca "transferencia" en el asunto de cada buzón activo y parsea lo que sabe leer.

    Vacío sin tocar la red si el titular tiene apagado "Leer transferencias
    SINPE" en Ajustes -ver la nota en
    `CuentaCorreoService.transferencias_sinpe_de_usuario`. BAC y Banco
    Nacional tienen lector exacto (`confirmado=True`); cualquier otro banco
    pasa por un lector genérico y llega marcado `confirmado=False` -la
    pantalla lo muestra igual, pero para revisar.
    """
    con_fuente = servicio.transferencias_sinpe_de_usuario(usuario_id, limite)
    return [
        TransferenciaSinpeResponse(
            banco=t.transferencia.banco,
            destinatario=t.transferencia.destinatario,
            cuenta_destino=t.transferencia.cuenta_destino,
            fecha=t.transferencia.fecha,
            moneda=t.transferencia.moneda,
            monto=t.transferencia.monto,
            concepto=t.transferencia.concepto,
            referencia=t.transferencia.referencia,
            comprobante=t.transferencia.comprobante,
            confianza=t.transferencia.confianza,
            es_confiable=t.transferencia.es_confiable,
            confirmado=t.transferencia.confirmado,
            cuenta_correo_id=t.cuenta_correo_id,
            proveedor=t.proveedor,
            direccion_cuenta=t.direccion,
        )
        for t in con_fuente
    ]


@router.get(
    "/bancos",
    response_model=list[BancoDetectadoResponse],
    summary="Remitentes que parecen bancos, detectados en todas las cuentas activas del titular",
)
def bancos_detectados(
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=30, gt=0, le=100),
) -> list[BancoDetectadoResponse]:
    """Busca "banco" en cada buzón activo y agrupa los remitentes por dominio.

    No sincroniza ni guarda nada -a diferencia de `/resumen-financiero`, acá
    no hay ningún `Comprobante` que persistir para un remitente sin parser.
    Cada resultado es un candidato, no una confirmación (ver la nota en
    `BancoDetectado`, business/services/cuenta_correo_service.py).
    """
    detectados = servicio.detectar_bancos(usuario_id, limite)
    return [BancoDetectadoResponse.model_validate(b) for b in detectados]


@router.get(
    "/comercios",
    response_model=list[ComercioClasificadoResponse],
    summary="Comercios clasificados, combinando todas las cuentas activas del titular",
)
def comercios_clasificados_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> list[ComercioClasificadoResponse]:
    """Igual que `/{cuenta_id}/comercios`, pero sobre el historial combinado
    de todas las cuentas activas del titular.
    """
    resumen = servicio.resumen_financiero_de_usuario(usuario_id, limite)
    clasificados = servicio_comercios.clasificar_comprobantes(usuario_id, resumen.comprobantes)
    return [ComercioClasificadoResponse.model_validate(c) for c in clasificados]


@router.get(
    "/presupuestos",
    response_model=list[EstadoDePresupuestoResponse],
    summary="Estado de los presupuestos, combinando todas las cuentas activas del titular",
)
def presupuestos_del_periodo_de_usuario(
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    servicio_presupuestos: ServicioDePresupuestos,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    anio: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    limite: int = Query(default=200, gt=0, le=500),
) -> list[EstadoDePresupuestoResponse]:
    """Igual que `/{cuenta_id}/presupuestos`, pero comparando el consumo real
    de todas las cuentas activas del titular contra el límite de cada categoría.
    """
    resumen = servicio.resumen_financiero_de_usuario(usuario_id, limite)
    comprobantes_del_periodo = filtrar_del_periodo(resumen.comprobantes, anio, mes)
    clasificados = servicio_comercios.clasificar_comprobantes(usuario_id, comprobantes_del_periodo)
    estados = servicio_presupuestos.calcular_estados(usuario_id, anio, mes, clasificados)
    return [EstadoDePresupuestoResponse.model_validate(e) for e in estados]


@router.get(
    "/{cuenta_id}/probar",
    response_model=list[MensajeResumidoResponse],
    summary="Probar la conexión trayendo los últimos mensajes",
)
def probar_conexion(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=5, gt=0, le=25),
) -> list[MensajeResumidoResponse]:
    """Trae los últimos mensajes del buzón para confirmar que el token funciona.

    No lee el cuerpo de ningún mensaje, solo remitente, asunto y fecha.
    """
    mensajes = servicio.probar_conexion(usuario_id, cuenta_id, limite)
    return [MensajeResumidoResponse(**vars(m)) for m in mensajes]


@router.get(
    "/{cuenta_id}/comprobante",
    response_model=ComprobanteParseadoResponse,
    summary="Leer y parsear el comprobante de un mensaje",
)
def leer_comprobante(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    mensaje_id: str = Query(min_length=1, description="Id de mensaje que devolvió /probar"),
) -> ComprobanteParseadoResponse:
    """Trae el cuerpo de un mensaje y lo pasa por el parser de BAC.

    `mensaje_id` viaja como query param -no como parte de la ruta- porque los
    identificadores de mensaje de Graph pueden traer `/` y otros caracteres
    que romperían un segmento de URL.
    """
    comprobante = servicio.leer_comprobante(usuario_id, cuenta_id, mensaje_id)
    return ComprobanteParseadoResponse.model_validate(comprobante)


@router.get(
    "/{cuenta_id}/resumen-financiero",
    response_model=ResumenFinancieroResponse,
    summary="Leer los comprobantes de BAC y sumarlos por mes",
)
def resumen_financiero(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> ResumenFinancieroResponse:
    """Suma por mes los comprobantes de BAC ya sincronizados de la bandeja.

    Antes de leerlos, sincroniza -pide al proveedor solo los mensajes que
    todavía no están guardados localmente. La primera vez, con una bandeja de
    varios años, puede tardar varios segundos; de ahí en adelante, con la
    bandeja ya al día, es prácticamente instantáneo.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    return ResumenFinancieroResponse.model_validate(resumen)


@router.post(
    "/{cuenta_id}/sincronizar",
    response_model=ResultadoDeSincronizacionResponse,
    summary="Traer explícitamente el correo nuevo de un buzón",
)
def sincronizar(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> ResultadoDeSincronizacionResponse:
    """Fuerza el pull de correo nuevo, sin pedir además todo el resumen.

    Todo lo demás (`resumen-financiero`, `comercios`, `presupuestos`, los
    reportes) ya sincroniza solo antes de leer, así que usar este endpoint
    aparte es opcional -sirve para confirmar cuánto trajo de nuevo, o para
    un botón de "sincronizar" explícito en el frontend.
    """
    resultado = servicio.sincronizar(usuario_id, cuenta_id, limite)
    return ResultadoDeSincronizacionResponse.model_validate(resultado)


@router.get(
    "/{cuenta_id}/comercios",
    response_model=list[ComercioClasificadoResponse],
    summary="Resolver y clasificar los comercios de los comprobantes de BAC",
)
def comercios_clasificados(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    limite: int = Query(default=200, gt=0, le=500),
) -> list[ComercioClasificadoResponse]:
    """Lee los comprobantes de BAC, resuelve cada comercio en el catálogo
    compartido y adjunta la categoría que este titular ya le haya asignado,
    si la hay. Un comercio nuevo queda sin categoría hasta que alguien la
    asigne con `POST /api/comercios/{id}/categoria`.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    clasificados = servicio_comercios.clasificar_comprobantes(usuario_id, resumen.comprobantes)
    return [ComercioClasificadoResponse.model_validate(c) for c in clasificados]


@router.get(
    "/{cuenta_id}/presupuestos",
    response_model=list[EstadoDePresupuestoResponse],
    summary="Estado de los presupuestos del período, contra el gasto real",
)
def presupuestos_del_periodo(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    servicio_presupuestos: ServicioDePresupuestos,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
    anio: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    limite: int = Query(default=200, gt=0, le=500),
) -> list[EstadoDePresupuestoResponse]:
    """Lee los comprobantes de BAC, los clasifica por comercio y compara el
    consumo real de cada categoría contra su presupuesto del período.

    Un presupuesto sin ningún comercio clasificado en su categoría sale con
    `monto_consumido = 0`, no con un error: es simplemente que todavía no
    hubo gasto reconocido ahí, o que lo que hubo no está clasificado.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    comprobantes_del_periodo = filtrar_del_periodo(resumen.comprobantes, anio, mes)
    clasificados = servicio_comercios.clasificar_comprobantes(usuario_id, comprobantes_del_periodo)
    estados = servicio_presupuestos.calcular_estados(usuario_id, anio, mes, clasificados)
    return [EstadoDePresupuestoResponse.model_validate(e) for e in estados]


@router.delete("/{cuenta_id}", status_code=204, summary="Desvincular un buzón")
def desvincular_cuenta(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    _: VerificarTitular,
    usuario_id: int = Query(gt=0, le=2_147_483_647),
) -> None:
    """Desvincula el buzón y borra sus tokens. La fila se conserva como historial."""
    servicio.desvincular(usuario_id, cuenta_id)
