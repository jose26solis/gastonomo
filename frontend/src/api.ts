/**
 * Cliente HTTP hacia la API de Gastonomo.
 *
 * Un solo lugar que sabe la URL base y cómo traducir un error de negocio
 * (`{"detalle": "..."}`, la forma que arma `main.py` en el backend) a una
 * excepción de JavaScript. Los componentes nunca llaman a `fetch` directo.
 */

import type {
  CuentaCorreo,
  ErrorDeApi,
  IniciarVinculacionResponse,
  MensajeResumido,
  Proveedor,
} from "./types";

const URL_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ErrorDeApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ErrorDeApiError";
    this.status = status;
  }
}

async function peticion<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${URL_BASE}${ruta}`, init);
  if (!respuesta.ok) {
    const cuerpo = (await respuesta.json().catch(() => null)) as ErrorDeApi | null;
    throw new ErrorDeApiError(
      cuerpo?.detalle ?? `La API respondió ${respuesta.status}`,
      respuesta.status,
    );
  }
  if (respuesta.status === 204) {
    return undefined as T;
  }
  return (await respuesta.json()) as T;
}

const rutaProveedor: Record<Proveedor, string> = {
  OUTLOOK: "outlook",
  GMAIL: "gmail",
};

export const api = {
  /** Pide la URL de autorización del proveedor para redirigir al titular. */
  iniciarVinculacion(usuarioId: number, proveedor: Proveedor): Promise<IniciarVinculacionResponse> {
    return peticion(
      `/api/cuentas-correo/${rutaProveedor[proveedor]}/iniciar?usuario_id=${usuarioId}`,
    );
  },

  /** Completa la vinculación con el código y el state que trajo el redirect. */
  completarVinculacion(
    proveedor: Proveedor,
    codigo: string,
    estado: string,
  ): Promise<CuentaCorreo> {
    const parametros = new URLSearchParams({ code: codigo, state: estado });
    return peticion(
      `/api/cuentas-correo/${rutaProveedor[proveedor]}/callback?${parametros.toString()}`,
    );
  },

  listarCuentas(usuarioId: number): Promise<CuentaCorreo[]> {
    return peticion(`/api/cuentas-correo?usuario_id=${usuarioId}`);
  },

  probarConexion(usuarioId: number, cuentaId: number): Promise<MensajeResumido[]> {
    return peticion(`/api/cuentas-correo/${cuentaId}/probar?usuario_id=${usuarioId}`);
  },

  desvincular(usuarioId: number, cuentaId: number): Promise<void> {
    return peticion(`/api/cuentas-correo/${cuentaId}?usuario_id=${usuarioId}`, {
      method: "DELETE",
    });
  },
};
