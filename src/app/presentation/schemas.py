"""DTOs de entrada y salida de la API.

Viven en presentacion, no en negocio: describen el contrato HTTP y pueden
cambiar sin que el dominio se entere.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.data.models.enums import EstadoCuentaCorreo, EstadoPresupuesto, Moneda, ProveedorCorreo

# Tope real de una columna INTEGER de PostgreSQL. Un id "válido" (positivo)
# pero absurdamente grande pasa `gt=0` sin problema y solo revienta al
# convertirlo al tipo real de la columna -sqlalchemy.exc.DataError bajo
# PostgreSQL, un OverflowError crudo de Python bajo SQLite. Ponerle este
# techo acá, y no solo confiar en el manejador de errores de main.py, da un
# 422 con mensaje consistente sin importar qué motor esté detrás.
_ID_MAXIMO = 2_147_483_647


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

    usuario_id: int = Field(gt=0, le=_ID_MAXIMO, description="Titular dueno de la categoria")
    nombre: str = Field(min_length=1, max_length=60, examples=["Alimentacion"])
    color_hex: str = Field(max_length=7, examples=["#2563EB"])
    descripcion: str | None = Field(default=None, max_length=255)
    categoria_padre_id: int | None = Field(
        default=None,
        gt=0,
        le=_ID_MAXIMO,
        description="Categoria que la totaliza, si es subcategoria",
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


class ResultadoDeSincronizacionResponse(BaseModel):
    """Cuánto correo nuevo trajo una sincronización explícita."""

    model_config = ConfigDict(from_attributes=True)

    comprobantes_nuevos: int
    comprobantes_totales: int
    sincronizado_en: datetime


class TipoDeCambioResponse(BaseModel):
    """Tipo de cambio de referencia del colón contra el dólar, del Banco Central."""

    model_config = ConfigDict(from_attributes=True)

    fecha: date
    compra: Decimal
    venta: Decimal


class ComercioResponse(BaseModel):
    """Un comercio del catálogo compartido."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    nombre_normalizado: str
    identificacion_tributaria: str | None
    provincia: str | None


class ComercioClasificadoResponse(BaseModel):
    """Un comercio real, resuelto del catálogo, con su categoría sugerida (si la hay)."""

    model_config = ConfigDict(from_attributes=True)

    comercio_id: int
    nombre: str
    categoria_id: int | None
    categoria_nombre: str | None
    cantidad_transacciones: int
    total: Decimal
    moneda: str


class AsignarCategoriaComercioRequest(BaseModel):
    """Cuerpo de POST /api/comercios/{id}/categoria."""

    usuario_id: int = Field(gt=0, le=_ID_MAXIMO)
    categoria_id: int = Field(gt=0, le=_ID_MAXIMO)


class CrearPresupuestoRequest(BaseModel):
    """Cuerpo de POST /api/presupuestos.

    Crear el mismo (usuario, categoría, año, mes) dos veces no duplica: la
    segunda llamada corrige el límite de la que ya existía.
    """

    usuario_id: int = Field(gt=0, le=_ID_MAXIMO)
    categoria_id: int = Field(gt=0, le=_ID_MAXIMO)
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    moneda: Moneda
    # < 10**12: lo que de verdad soporta la columna Numeric(14,2). Sin este
    # tope, un valor con más dígitos pasa la validación y revienta en el
    # INSERT con un psycopg.errors.NumericValueOutOfRange sin capturar -un
    # 500 crudo en vez de un 422 con mensaje.
    monto_limite: Decimal = Field(gt=0, lt=Decimal(10**12))
    umbral_alerta: int = Field(default=80, ge=1, le=100)


class PresupuestoResponse(BaseModel):
    """Un presupuesto tal como quedó guardado -sin el consumo, que se calcula aparte."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    categoria_id: int
    anio: int
    mes: int
    moneda: Moneda
    monto_limite: Decimal
    umbral_alerta: int


class EstadoDePresupuestoResponse(BaseModel):
    """El límite de un presupuesto junto con su consumo real del período."""

    model_config = ConfigDict(from_attributes=True)

    presupuesto_id: int
    categoria_id: int
    categoria_nombre: str
    anio: int
    mes: int
    moneda: str
    monto_limite: Decimal
    monto_consumido: Decimal
    umbral_alerta: int
    porcentaje_usado: float
    estado: EstadoPresupuesto
