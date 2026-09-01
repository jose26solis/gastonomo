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

export interface ErrorDeApi {
  detalle: string;
}
