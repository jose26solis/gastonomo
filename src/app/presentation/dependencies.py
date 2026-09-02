"""Armado de las dependencias de cada peticion.

Es el unico lugar de la capa de presentacion que conoce a los repositorios, y
solo para inyectarlos: los routers reciben el servicio ya construido y nunca
tocan la base directamente.
"""

from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from app.business.services.categoria_service import CategoriaService
from app.business.services.comercio_service import ComercioService
from app.business.services.correo.gmail import GmailProveedor
from app.business.services.correo.outlook import OutlookProveedor
from app.business.services.correo.proveedor import ProveedorDeCorreo
from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.business.services.presupuesto_service import PresupuestoService
from app.business.services.tipo_cambio_service import TipoCambioService
from app.config.cliente_http import obtener_cliente_http
from app.config.database import obtener_sesion
from app.config.settings import obtener_configuracion
from app.data.models.enums import ProveedorCorreo
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.comercio_categoria_repository import ComercioCategoriaRepository
from app.data.repositories.comercio_repository import ComercioRepository
from app.data.repositories.comprobante_repository import ComprobanteRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.presupuesto_repository import PresupuestoRepository
from app.data.repositories.usuario_repository import UsuarioRepository

SesionDependencia = Annotated[Session, Depends(obtener_sesion)]
ClienteHttpDependencia = Annotated[httpx.Client, Depends(obtener_cliente_http)]


def obtener_servicio_de_categorias(sesion: SesionDependencia) -> CategoriaService:
    """Arma el servicio de categorias con sus repositorios sobre la sesion actual."""
    return CategoriaService(CategoriaRepository(sesion), UsuarioRepository(sesion))


ServicioDeCategorias = Annotated[CategoriaService, Depends(obtener_servicio_de_categorias)]


def obtener_proveedores_de_correo(
    cliente: ClienteHttpDependencia,
) -> dict[ProveedorCorreo, ProveedorDeCorreo]:
    """Arma un proveedor por cada correo que el sistema sabe vincular."""
    configuracion = obtener_configuracion()
    return {
        ProveedorCorreo.OUTLOOK: OutlookProveedor(cliente, configuracion),
        ProveedorCorreo.GMAIL: GmailProveedor(cliente, configuracion),
    }


ProveedoresDeCorreoDependencia = Annotated[
    dict[ProveedorCorreo, ProveedorDeCorreo], Depends(obtener_proveedores_de_correo)
]


def obtener_servicio_de_cuentas_correo(
    sesion: SesionDependencia, proveedores: ProveedoresDeCorreoDependencia
) -> CuentaCorreoService:
    """Arma el servicio de cuentas de correo con sus repositorios y proveedores."""
    return CuentaCorreoService(
        CuentaCorreoRepository(sesion),
        UsuarioRepository(sesion),
        proveedores,
        ComprobanteRepository(sesion),
    )


ServicioDeCuentasCorreo = Annotated[
    CuentaCorreoService, Depends(obtener_servicio_de_cuentas_correo)
]


def obtener_servicio_de_comercios(sesion: SesionDependencia) -> ComercioService:
    """Arma el servicio de comercios con sus repositorios sobre la sesion actual."""
    return ComercioService(
        ComercioRepository(sesion),
        ComercioCategoriaRepository(sesion),
        CategoriaRepository(sesion),
    )


ServicioDeComercios = Annotated[ComercioService, Depends(obtener_servicio_de_comercios)]


def obtener_servicio_de_presupuestos(sesion: SesionDependencia) -> PresupuestoService:
    """Arma el servicio de presupuestos con sus repositorios sobre la sesion actual."""
    return PresupuestoService(
        PresupuestoRepository(sesion), CategoriaRepository(sesion), UsuarioRepository(sesion)
    )


ServicioDePresupuestos = Annotated[PresupuestoService, Depends(obtener_servicio_de_presupuestos)]


_servicio_de_tipo_cambio: TipoCambioService | None = None


def obtener_servicio_de_tipo_cambio(cliente: ClienteHttpDependencia) -> TipoCambioService:
    """Arma (una sola vez) el servicio de tipo de cambio, con su caché por fecha.

    A diferencia de los demás servicios, este no depende de la sesion de
    base de datos -no persiste nada por usuario- así que es el único que
    conviene reutilizar entre peticiones en vez de armar de cero cada vez:
    su caché en memoria solo sirve si sobrevive más de una petición.
    """
    global _servicio_de_tipo_cambio
    if _servicio_de_tipo_cambio is None:
        _servicio_de_tipo_cambio = TipoCambioService(cliente, obtener_configuracion())
    return _servicio_de_tipo_cambio


ServicioDeTipoCambio = Annotated[TipoCambioService, Depends(obtener_servicio_de_tipo_cambio)]
