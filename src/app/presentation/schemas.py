"""DTOs de entrada y salida de la API.

Viven en presentacion, no en negocio: describen el contrato HTTP y pueden
cambiar sin que el dominio se entere.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.data.models.enums import EstadoCuentaCorreo, ProveedorCorreo


class SaludResponse(BaseModel):
    """Respuesta del endpoint de salud."""

    estado: str
    aplicacion: str
    version: str


class CrearCategoriaRequest(BaseModel):
    """Cuerpo de POST /api/categorias.

    Solo valida la forma del dato (tipos, largos, formato). Si la categoria se
    puede crear o no es una pregunta del negocio, y se responde en el servicio.
    """

    usuario_id: int = Field(gt=0, description="Titular dueno de la categoria")
    nombre: str = Field(min_length=1, max_length=60, examples=["Alimentacion"])
    color_hex: str = Field(max_length=7, examples=["#2563EB"])
    descripcion: str | None = Field(default=None, max_length=255)
    categoria_padre_id: int | None = Field(
        default=None, gt=0, description="Categoria que la totaliza, si es subcategoria"
    )


class CategoriaResponse(BaseModel):
    """Categoria tal como la ve el cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    nombre: str
    descripcion: str | None
    color_hex: str
    categoria_padre_id: int | None
    es_hoja: bool
    activa: bool


class ErrorResponse(BaseModel):
    """Forma unica de los errores de negocio traducidos a HTTP."""

    detalle: str


class IniciarVinculacionResponse(BaseModel):
    """URL a la que el frontend debe redirigir al titular para autorizar el acceso."""

    url_autorizacion: str


class CuentaCorreoResponse(BaseModel):
    """Una cuenta de correo vinculada, sin ningun dato de token."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    proveedor: ProveedorCorreo
    direccion: str
    estado: EstadoCuentaCorreo
    ultima_sincronizacion: datetime | None


class MensajeResumidoResponse(BaseModel):
    """Metadatos de un mensaje reciente, usados solo para probar la conexion."""

    identificador: str
    remitente: str
    asunto: str
    recibido_en: datetime | None


class ComprobanteParseadoResponse(BaseModel):
    """Lo que el parser de BAC logró leer del cuerpo de un mensaje.

    Todavía no es una `Compra`: es la lectura cruda, previa a resolver el
    comercio, emparejar el método de pago y persistir nada.
    """

    model_config = ConfigDict(from_attributes=True)

    banco: str
    comercio: str | None
    ciudad: str | None
    pais: str | None
    fecha: datetime | None
    marca_tarjeta: str | None
    ultimos_cuatro: str | None
    autorizacion: str | None
    referencia: str | None
    tipo_transaccion: str | None
    moneda: str | None
    monto: Decimal | None
    confianza: float
    es_compra: bool
    es_confiable: bool


class ResumenMensualResponse(BaseModel):
    """Total de compras de un mes, en una moneda."""

    model_config = ConfigDict(from_attributes=True)

    anio: int
    mes: int
    moneda: str
    total: Decimal
    cantidad_transacciones: int


class ResumenFinancieroResponse(BaseModel):
    """Los comprobantes de BAC leídos de la bandeja, y su suma por mes."""

    model_config = ConfigDict(from_attributes=True)

    comprobantes: list[ComprobanteParseadoResponse]
    por_mes: list[ResumenMensualResponse]
