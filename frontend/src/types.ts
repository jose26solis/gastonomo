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

export interface ErrorDeApi {
  detalle: string;
}
