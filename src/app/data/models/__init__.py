"""Entidades del dominio mapeadas a tablas.

SQLAlchemy resuelve las relaciones declaradas como cadena (`Mapped["Categoria"]`)
buscando esa clase entre las que ya se importaron alguna vez. Sin importar acá
cada módulo de modelo, cuál relación resuelve dependería del orden accidental
en que otro archivo los haya importado antes.
"""

from app.data.models.categoria import Categoria
from app.data.models.categoria_estandar import CategoriaEstandar
from app.data.models.comercio import Comercio
from app.data.models.comercio_categoria_sugerida import ComercioCategoriaSugerida
from app.data.models.compra import Compra
from app.data.models.comprobante import Comprobante
from app.data.models.cuenta_correo import CuentaCorreo
from app.data.models.linea_compra import LineaCompra
from app.data.models.metodo_pago import MetodoPago
from app.data.models.presupuesto import Presupuesto
from app.data.models.regla_categorizacion import ReglaCategorizacion
from app.data.models.tipo_cambio import TipoCambio
from app.data.models.transferencia_sinpe import TransferenciaSinpe
from app.data.models.usuario import Usuario

__all__ = [
    "Categoria",
    "CategoriaEstandar",
    "Comercio",
    "ComercioCategoriaSugerida",
    "Compra",
    "Comprobante",
    "CuentaCorreo",
    "LineaCompra",
    "MetodoPago",
    "Presupuesto",
    "ReglaCategorizacion",
    "TipoCambio",
    "TransferenciaSinpe",
    "Usuario",
]
