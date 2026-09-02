"""Reglas de negocio de la vinculación de correo, con un proveedor falso."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.business.errors import RecursoNoEncontrado, ReglaDeNegocioViolada
from app.business.seguridad.cifrado import descifrar
from app.business.services.cuenta_correo_service import CuentaCorreoService, VincularCuentaComando
from app.data.models.enums import EstadoCuentaCorreo, Moneda, ProveedorCorreo
from app.data.models.usuario import Usuario
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository
from tests.apoyos_correo import ProveedorDeCorreoFalso


@pytest.fixture
def servicio(
    sesion: Session, proveedor_correo_falso: ProveedorDeCorreoFalso
) -> CuentaCorreoService:
    return CuentaCorreoService(
        CuentaCorreoRepository(sesion),
        UsuarioRepository(sesion),
        {ProveedorCorreo.OUTLOOK: proveedor_correo_falso},
        ComprobanteRepository(sesion),
    )


def _vincular(servicio: CuentaCorreoService, usuario: Usuario, codigo: str = "codigo-abc"):
    return servicio.vincular(
        VincularCuentaComando(
            usuario_id=usuario.id, proveedor=ProveedorCorreo.OUTLOOK, codigo=codigo
        )
    )


def test_vincula_una_cuenta_nueva_y_cifra_los_tokens(
    servicio: CuentaCorreoService, usuario: Usuario, proveedor_correo_falso: ProveedorDeCorreoFalso
) -> None:
    cuenta = _vincular(servicio, usuario, codigo="codigo-abc")

    assert cuenta.id is not None
    assert cuenta.direccion == "titular@ejemplo.cr"
    assert cuenta.estado == EstadoCuentaCorreo.ACTIVA
    assert proveedor_correo_falso.codigo_recibido == "codigo-abc"
    assert cuenta.token_acceso_cifrado != "acceso-1", "el token no puede quedar en claro"
    assert descifrar(cuenta.token_acceso_cifrado) == "acceso-1"
    assert descifrar(cuenta.token_refresco_cifrado) == "refresco-1"


def test_vincular_dos_veces_el_mismo_buzon_actualiza_en_vez_de_duplicar(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    primera = _vincular(servicio, usuario)
    segunda = _vincular(servicio, usuario)

    assert primera.id == segunda.id
    assert len(servicio.listar(usuario.id)) == 1


def test_no_deja_vincular_para_un_usuario_que_no_existe(servicio: CuentaCorreoService) -> None:
    with pytest.raises(RecursoNoEncontrado):
        servicio.vincular(
            VincularCuentaComando(usuario_id=9999, proveedor=ProveedorCorreo.OUTLOOK, codigo="x")
        )


def test_probar_conexion_devuelve_los_mensajes_del_proveedor(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    cuenta = _vincular(servicio, usuario)

    mensajes = servicio.probar_conexion(usuario.id, cuenta.id)

    assert len(mensajes) == 1
    assert mensajes[0].remitente == "NotificacionBAC@baccredomatic.cr"


def test_probar_conexion_actualiza_la_ultima_sincronizacion(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    cuenta = _vincular(servicio, usuario)
    assert cuenta.ultima_sincronizacion is None

    servicio.probar_conexion(usuario.id, cuenta.id)

    assert cuenta.ultima_sincronizacion is not None


def test_un_token_vencido_se_refresca_solo(
    servicio: CuentaCorreoService,
    usuario: Usuario,
    proveedor_correo_falso: ProveedorDeCorreoFalso,
    sesion: Session,
) -> None:
    cuenta = _vincular(servicio, usuario)
    cuenta.expira_en = datetime.now(UTC) - timedelta(minutes=1)
    sesion.commit()

    servicio.probar_conexion(usuario.id, cuenta.id)

    assert proveedor_correo_falso.token_refrescado_con == "refresco-1"
    assert descifrar(cuenta.token_acceso_cifrado) == "acceso-2"
    assert cuenta.estado == EstadoCuentaCorreo.ACTIVA


def test_un_token_vencido_sin_refresco_marca_la_cuenta_expirada(
    servicio: CuentaCorreoService, usuario: Usuario, sesion: Session
) -> None:
    cuenta = _vincular(servicio, usuario)
    cuenta.expira_en = datetime.now(UTC) - timedelta(minutes=1)
    cuenta.token_refresco_cifrado = None
    sesion.commit()

    with pytest.raises(ReglaDeNegocioViolada):
        servicio.probar_conexion(usuario.id, cuenta.id)

    assert cuenta.estado == EstadoCuentaCorreo.TOKEN_EXPIRADO


def test_leer_comprobante_trae_el_cuerpo_y_lo_parsea(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    """El mensaje "1" del doble de prueba es la muestra real de BAC anonimizada."""
    cuenta = _vincular(servicio, usuario)

    comprobante = servicio.leer_comprobante(usuario.id, cuenta.id, "1")

    assert comprobante.banco == "BAC Credomatic"
    assert comprobante.comercio == "WALMART SAN SEBASTIAN"
    assert comprobante.es_compra is True
    assert comprobante.es_confiable is True


def test_leer_comprobante_de_un_mensaje_que_no_es_de_bac(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    """El mensaje "2" es el señuelo de PriceSmart: sin los campos de BAC."""
    cuenta = _vincular(servicio, usuario)

    comprobante = servicio.leer_comprobante(usuario.id, cuenta.id, "2")

    assert comprobante.confianza == 0.0
    assert comprobante.es_confiable is False


def test_desvincular_borra_los_tokens_y_cambia_el_estado(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    cuenta = _vincular(servicio, usuario)

    servicio.desvincular(usuario.id, cuenta.id)

    assert cuenta.estado == EstadoCuentaCorreo.DESVINCULADA
    assert cuenta.token_acceso_cifrado is None
    assert cuenta.token_refresco_cifrado is None


def test_resumen_financiero_lee_y_suma_solo_lo_de_bac(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    """El doble de prueba trae un correo de BAC y uno de PriceSmart; solo el de BAC suma."""
    cuenta = _vincular(servicio, usuario)

    resumen = servicio.resumen_financiero(usuario.id, cuenta.id)

    assert len(resumen.comprobantes) == 1
    assert resumen.comprobantes[0].comercio == "WALMART SAN SEBASTIAN"
    assert len(resumen.por_mes) == 1
    assert resumen.por_mes[0].total == Decimal("7870.00")
    assert resumen.por_mes[0].cantidad_transacciones == 1


def test_resumen_financiero_no_vuelve_a_leer_un_comprobante_ya_sincronizado(
    servicio: CuentaCorreoService,
    usuario: Usuario,
    proveedor_correo_falso: ProveedorDeCorreoFalso,
) -> None:
    """El punto de la caché: la segunda llamada no debe volver a pedir el cuerpo."""
    cuenta = _vincular(servicio, usuario)

    servicio.resumen_financiero(usuario.id, cuenta.id)
    assert proveedor_correo_falso.cuerpos_leidos == ["1"]

    resumen = servicio.resumen_financiero(usuario.id, cuenta.id)

    assert proveedor_correo_falso.cuerpos_leidos == ["1"], (
        "el segundo resumen no debio volver a pedirle el cuerpo al proveedor"
    )
    assert len(resumen.comprobantes) == 1
    assert resumen.comprobantes[0].comercio == "WALMART SAN SEBASTIAN"


def test_sincronizar_devuelve_cuantos_comprobantes_trajo_de_nuevo(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    cuenta = _vincular(servicio, usuario)

    primera = servicio.sincronizar(usuario.id, cuenta.id)
    segunda = servicio.sincronizar(usuario.id, cuenta.id)

    assert primera.comprobantes_nuevos == 1
    assert primera.comprobantes_totales == 1
    assert segunda.comprobantes_nuevos == 0, "ya no hay nada nuevo que traer"
    assert segunda.comprobantes_totales == 1
    assert segunda.sincronizado_en >= primera.sincronizado_en


def test_probar_conexion_en_una_cuenta_desvinculada_falla(
    servicio: CuentaCorreoService, usuario: Usuario
) -> None:
    cuenta = _vincular(servicio, usuario)
    servicio.desvincular(usuario.id, cuenta.id)

    with pytest.raises(ReglaDeNegocioViolada):
        servicio.probar_conexion(usuario.id, cuenta.id)


def test_no_deja_ver_una_cuenta_de_otro_titular(
    servicio: CuentaCorreoService, usuario: Usuario, sesion: Session
) -> None:
    otro = Usuario(
        nombre_completo="Otra persona",
        correo="otra-persona@gastonomo.cr",
        contrasena_hash="hash",
        moneda_preferida=Moneda.CRC,
    )
    sesion.add(otro)
    sesion.commit()
    cuenta = _vincular(servicio, usuario)

    with pytest.raises(RecursoNoEncontrado):
        servicio.probar_conexion(otro.id, cuenta.id)
