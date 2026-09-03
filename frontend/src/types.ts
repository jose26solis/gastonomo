/**
 * Tipos que reflejan los DTOs de `src/app/presentation/schemas.py`.
 *
 * Se mantienen a mano en vez de generarlos: el backend todavía no publica un
 * cliente OpenAPI, y son pocos campos. Si crecen, vale la pena generar esto
 * desde `/openapi.json` en vez de seguir copiándolo.
 */

export type Proveedor = "OUTLOOK" | "GMAIL";

export type EstadoCuentaCorreo =
  | "ACTIVA"
  | "TOKEN_EXPIRADO"
  | "DESVINCULADA"
  | "ERROR";

export interface CuentaCorreo {
  id: number;
  usuario_id: number;
  proveedor: Proveedor;
  direccion: string;
  estado: EstadoCuentaCorreo;
  ultima_sincronizacion: string | null;
}

export interface IniciarVinculacionResponse {
  url_autorizacion: string;
}

export interface MensajeResumido {
  identificador: string;
  remitente: string;
  asunto: string;
  recibido_en: string | null;
}

export interface ComprobanteParseado {
  banco: string;
  comercio: string | null;
  ciudad: string | null;
  pais: string | null;
  fecha: string | null;
  marca_tarjeta: string | null;
  ultimos_cuatro: string | null;
  autorizacion: string | null;
  referencia: string | null;
  tipo_transaccion: string | null;
  moneda: string | null;
  /** Viaja como string desde Pydantic (Decimal); parsear con Number() para sumar. */
  monto: string | null;
  confianza: number;
  es_compra: boolean;
  es_confiable: boolean;
}

export interface ResumenMensual {
  anio: number;
  mes: number;
  moneda: string;
  total: string;
  cantidad_transacciones: number;
}

export interface ResumenFinanciero {
  comprobantes: ComprobanteParseado[];
  por_mes: ResumenMensual[];
}

/** Un comprobante combinado de varias cuentas, marcado con de cuál salió. */
export interface ComprobanteConFuente extends ComprobanteParseado {
  cuenta_correo_id: number;
  proveedor: Proveedor;
  direccion_cuenta: string;
  /** Lo que cobró el banco, si este movimiento se convirtió a otra moneda. */
  monto_original: string | null;
  moneda_original: string | null;
  /** De qué día es la tasa con la que se convirtió este movimiento. */
  tipo_cambio_fecha: string | null;
  /** La Compra real que se concilió a partir de este movimiento -con esto se
   * puede pedir `api.bitacoraDeCompra`. `null` si la confianza del parseo no
   * alcanzó para conciliar. */
  compra_id: number | null;
}

export interface ResumenFinancieroConFuente {
  comprobantes: ComprobanteConFuente[];
  por_mes: ResumenMensual[];
  /** La tasa con la que se convirtió todo, si se pidió una moneda única. */
  conversion: TipoDeCambio | null;
}

export interface Categoria {
  id: number;
  usuario_id: number;
  nombre: string;
  descripcion: string | null;
  color_hex: string;
  categoria_padre_id: number | null;
  es_hoja: boolean;
  activa: boolean;
}

export interface ComercioClasificado {
  comercio_id: number;
  nombre: string;
  categoria_id: number | null;
  categoria_nombre: string | null;
  cantidad_transacciones: number;
  total: string;
  moneda: string;
}

export interface Presupuesto {
  id: number;
  usuario_id: number;
  categoria_id: number;
  anio: number;
  mes: number;
  moneda: string;
  monto_limite: string;
  umbral_alerta: number;
}

export type EstadoPresupuesto = "EN_RANGO" | "CERCA_DEL_LIMITE" | "EXCEDIDO";

export interface EstadoDePresupuesto {
  presupuesto_id: number;
  categoria_id: number;
  categoria_nombre: string;
  anio: number;
  mes: number;
  moneda: string;
  monto_limite: string;
  monto_consumido: string;
  umbral_alerta: number;
  porcentaje_usado: number;
  estado: EstadoPresupuesto;
}

export type TipoMetodoPago = "EFECTIVO" | "DEBITO" | "CREDITO" | "SINPE_MOVIL";

export interface MetodoPago {
  id: number;
  usuario_id: number;
  alias: string;
  tipo: TipoMetodoPago;
  moneda: string;
  /** Solo DEBITO/CREDITO llevan esto -ver el modelo del backend. */
  ultimos_cuatro: string | null;
  entidad: string | null;
  dia_corte: number | null;
  activo: boolean;
}

/**
 * Un paso de la trazabilidad de una compra, tal como vive en Mongo: de qué
 * correo nació, cómo se emparejó el método de pago, qué regla la categorizó.
 * Es el diferenciador declarado del dominio -ver ADR-002.
 */
export interface EventoBitacora {
  secuencia: number;
  tipo: string;
  ocurrido_en: string;
  actor: { tipo: string; usuario_id: number | null; nombre: string | null };
  datos: Record<string, unknown>;
}

export interface ErrorDeApi {
  detalle: string;
}

export interface Usuario {
  id: number;
  nombre_completo: string;
  correo: string;
  moneda_preferida: string;
  /** Si tiene contraseña propia -false en una cuenta que solo entró por Google. */
  tiene_contrasena: boolean;
  /** Si "Iniciar sesión con Google" está activo para esta cuenta. */
  google_vinculado: boolean;
  /** El interruptor "Leer transferencias SINPE" de Ajustes. Apagado por default. */
  leer_transferencias_sinpe: boolean;
}

export interface UrlDeAutorizacion {
  url_autorizacion: string;
}

export interface Sesion {
  token: string;
  usuario: Usuario;
}

export interface TipoDeCambio {
  fecha: string;
  compra: string;
  venta: string;
}

/**
 * Un remitente que parece un banco, encontrado buscando "banco" en un buzón
 * vinculado. Es un candidato, no una confirmación: solo BAC tiene un parser
 * real hoy -el resto son pistas de a qué otro banco vale la pena agregarle soporte.
 */
export interface BancoDetectado {
  dominio: string;
  remitente_ejemplo: string;
  cantidad_mensajes: number;
  mensaje_mas_reciente: string | null;
  es_bac: boolean;
  cuenta_correo_id: number;
  proveedor: Proveedor;
  direccion: string;
}

/**
 * Una transferencia SINPE recibida, ya leída y parseada. BAC y Banco Nacional
 * tienen lector exacto (`confirmado: true`); cualquier otro banco pasa por un
 * lector genérico de patrones sueltos y llega con `confirmado: false` -se
 * muestra igual, pero marcada para revisar.
 */
export interface TransferenciaSinpe {
  banco: string;
  destinatario: string | null;
  cuenta_destino: string | null;
  fecha: string | null;
  moneda: string | null;
  /** Viaja como string desde Pydantic (Decimal); parsear con Number() para sumar. */
  monto: string | null;
  concepto: string | null;
  referencia: string | null;
  comprobante: string | null;
  confianza: number;
  es_confiable: boolean;
  confirmado: boolean;
  cuenta_correo_id: number;
  proveedor: Proveedor;
  direccion_cuenta: string;
}
