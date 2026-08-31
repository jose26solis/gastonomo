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
from app.business.services.correo.gmail import GmailProveedor
from app.business.services.correo.outlook import OutlookProveedor
from app.business.services.correo.proveedor import ProveedorDeCorreo
from app.business.services.cuenta_correo_service import CuentaCorreoService
from app.config.cliente_http import obtener_cliente_http
from app.config.database import obtener_sesion
from app.config.settings import obtener_configuracion
from app.data.models.enums import ProveedorCorreo
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
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
        CuentaCorreoRepository(sesion), UsuarioRepository(sesion), proveedores
    )


ServicioDeCuentasCorreo = Annotated[
    CuentaCorreoService, Depends(obtener_servicio_de_cuentas_correo)
]
