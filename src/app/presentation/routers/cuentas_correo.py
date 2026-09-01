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

from fastapi import APIRouter, Query

from app.business.errors import DatosInvalidos
from app.business.seguridad.cifrado import TokenIlegible, cifrar, descifrar
from app.business.services.cuenta_correo_service import VincularCuentaComando
from app.data.models.enums import ProveedorCorreo
from app.presentation.dependencies import (
    ServicioDeComercios,
    ServicioDeCuentasCorreo,
    ServicioDePresupuestos,
)
from app.presentation.schemas import (
    ComercioClasificadoResponse,
    ComprobanteParseadoResponse,
    CuentaCorreoResponse,
    EstadoDePresupuestoResponse,
    IniciarVinculacionResponse,
    MensajeResumidoResponse,
    ResumenFinancieroResponse,
)

router = APIRouter(prefix="/api/cuentas-correo", tags=["cuentas-correo"])


def _codificar_estado(usuario_id: int) -> str:
    return cifrar(json.dumps({"usuario_id": usuario_id}))


def _decodificar_estado(estado: str) -> int:
    try:
        datos = json.loads(descifrar(estado))
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
    usuario_id: int = Query(gt=0),
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
    usuario_id: int = Query(gt=0),
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
    usuario_id: int = Query(gt=0),
) -> list[CuentaCorreoResponse]:
    """Lista los buzones vinculados del titular indicado."""
    return [CuentaCorreoResponse.model_validate(c) for c in servicio.listar(usuario_id)]


@router.get(
    "/{cuenta_id}/probar",
    response_model=list[MensajeResumidoResponse],
    summary="Probar la conexión trayendo los últimos mensajes",
)
def probar_conexion(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    usuario_id: int = Query(gt=0),
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
    usuario_id: int = Query(gt=0),
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
    usuario_id: int = Query(gt=0),
    limite: int = Query(default=200, gt=0, le=500),
) -> ResumenFinancieroResponse:
    """Trae y parsea los comprobantes de BAC de la bandeja, y los suma por mes.

    Puede tardar varios segundos con una bandeja de varios años: cada
    comprobante es una petición aparte al proveedor de correo, y todavía no
    hay ninguna tabla donde esto quede guardado entre una llamada y la
    siguiente.
    """
    resumen = servicio.resumen_financiero(usuario_id, cuenta_id, limite)
    return ResumenFinancieroResponse.model_validate(resumen)


@router.get(
    "/{cuenta_id}/comercios",
    response_model=list[ComercioClasificadoResponse],
    summary="Resolver y clasificar los comercios de los comprobantes de BAC",
)
def comercios_clasificados(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    servicio_comercios: ServicioDeComercios,
    usuario_id: int = Query(gt=0),
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
    usuario_id: int = Query(gt=0),
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
    clasificados = servicio_comercios.clasificar_comprobantes(usuario_id, resumen.comprobantes)
    estados = servicio_presupuestos.calcular_estados(usuario_id, anio, mes, clasificados)
    return [EstadoDePresupuestoResponse.model_validate(e) for e in estados]


@router.delete("/{cuenta_id}", status_code=204, summary="Desvincular un buzón")
def desvincular_cuenta(
    cuenta_id: int,
    servicio: ServicioDeCuentasCorreo,
    usuario_id: int = Query(gt=0),
) -> None:
    """Desvincula el buzón y borra sus tokens. La fila se conserva como historial."""
    servicio.desvincular(usuario_id, cuenta_id)
