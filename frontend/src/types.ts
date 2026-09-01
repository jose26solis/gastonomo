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

export interface ErrorDeApi {
  detalle: string;
}
