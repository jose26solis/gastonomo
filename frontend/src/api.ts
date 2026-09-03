/**
 * Cliente HTTP hacia la API de Gastonomo.
 *
 * Un solo lugar que sabe la URL base y cómo traducir un error de negocio
 * (`{"detalle": "..."}`, la forma que arma `main.py` en el backend) a una
 * excepción de JavaScript. Los componentes nunca llaman a `fetch` directo.
 */

import type {
  Categoria,
  ComercioClasificado,
  ComprobanteParseado,
  CuentaCorreo,
  ErrorDeApi,
  EstadoDePresupuesto,
  IniciarVinculacionResponse,
  MensajeResumido,
  Presupuesto,
  Proveedor,
  Sesion,
  ResumenFinancieroConFuente,
  TipoDeCambio,
  Usuario,
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

// El token de sesión vive acá, en memoria, no en cada llamada individual:
// así ningún componente tiene que acordarse de pasarlo. `useSesion` es el
// único que lo cambia -al iniciar sesión, registrarse, cerrar sesión o
// hidratar lo que había en localStorage al cargar la página.
let tokenDeSesion: string | null = null;

export function establecerTokenDeSesion(token: string | null): void {
  tokenDeSesion = token;
}

function encabezadosDeAutorizacion(): HeadersInit {
  return tokenDeSesion ? { Authorization: `Bearer ${tokenDeSesion}` } : {};
}

async function peticion<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${URL_BASE}${ruta}`, {
    ...init,
    headers: { ...encabezadosDeAutorizacion(), ...init?.headers },
  });
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

/** Descarga un archivo que el backend arma al vuelo (CSV/Excel/PDF), disparando el guardado del navegador. */
async function descargarArchivo(ruta: string, nombreSugerido: string): Promise<void> {
  const respuesta = await fetch(`${URL_BASE}${ruta}`, { headers: encabezadosDeAutorizacion() });
  if (!respuesta.ok) {
    const cuerpo = (await respuesta.json().catch(() => null)) as ErrorDeApi | null;
    throw new ErrorDeApiError(
      cuerpo?.detalle ?? `La API respondió ${respuesta.status}`,
      respuesta.status,
    );
  }
  const blob = await respuesta.blob();
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreSugerido;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}

const rutaProveedor: Record<Proveedor, string> = {
  OUTLOOK: "outlook",
  GMAIL: "gmail",
};

export const api = {
  // ---- Autenticación ----

  registrar(nombreCompleto: string, correo: string, contrasena: string): Promise<Sesion> {
    return peticion("/api/auth/registro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre_completo: nombreCompleto,
        correo,
        contrasena,
      }),
    });
  },

  iniciarSesion(correo: string, contrasena: string): Promise<Sesion> {
    return peticion("/api/auth/iniciar-sesion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ correo, contrasena }),
    });
  },

  /** Confirma que un token guardado sigue vigente y trae al titular dueño. */
  yo(): Promise<Usuario> {
    return peticion("/api/auth/yo");
  },

  // ---- Cuentas de correo ----

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

  leerComprobante(
    usuarioId: number,
    cuentaId: number,
    mensajeId: string,
  ): Promise<ComprobanteParseado> {
    const parametros = new URLSearchParams({
      usuario_id: String(usuarioId),
      mensaje_id: mensajeId,
    });
    return peticion(`/api/cuentas-correo/${cuentaId}/comprobante?${parametros.toString()}`);
  },

  /**
   * Lee y parsea los comprobantes de BAC de TODAS las cuentas activas del
   * titular (Outlook y Gmail a la vez, si tiene ambas vinculadas), y los suma
   * por mes. Cada comprobante trae marcada la cuenta de la que salió.
   *
   * Puede tardar varios segundos: cada comprobante nuevo es una petición real
   * al proveedor de correo. No hay un límite de tiempo especial en el fetch
   * -el componente que llama esto debe mostrar un estado de carga mientras espera.
   */
  resumenFinanciero(
    usuarioId: number,
    moneda?: string,
    limite = 200,
  ): Promise<ResumenFinancieroConFuente> {
    const parametros = new URLSearchParams({
      usuario_id: String(usuarioId),
      limite: String(limite),
    });
    // Sin `moneda`, cada movimiento conserva la suya y las monedas no se
    // suman entre sí -el comportamiento por defecto.
    if (moneda) parametros.set("moneda", moneda);
    return peticion(`/api/cuentas-correo/resumen-financiero?${parametros.toString()}`);
  },

  desvincular(usuarioId: number, cuentaId: number): Promise<void> {
    return peticion(`/api/cuentas-correo/${cuentaId}?usuario_id=${usuarioId}`, {
      method: "DELETE",
    });
  },

  // ---- Categorías ----

  listarCategorias(usuarioId: number): Promise<Categoria[]> {
    return peticion(`/api/categorias?usuario_id=${usuarioId}`);
  },

  crearCategoria(usuarioId: number, nombre: string, colorHex: string): Promise<Categoria> {
    return peticion("/api/categorias", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario_id: usuarioId, nombre, color_hex: colorHex }),
    });
  },

  // ---- Comercios ----

  /**
   * Lee las bandejas reales de todas las cuentas activas, resuelve cada
   * comercio en el catálogo y adjunta su categoría sugerida. Igual que
   * `resumenFinanciero`, puede tardar varios segundos: relee todo cada vez.
   */
  listarComercios(usuarioId: number, limite = 200): Promise<ComercioClasificado[]> {
    const parametros = new URLSearchParams({ usuario_id: String(usuarioId), limite: String(limite) });
    return peticion(`/api/cuentas-correo/comercios?${parametros.toString()}`);
  },

  asignarCategoriaComercio(
    usuarioId: number,
    comercioId: number,
    categoriaId: number,
  ): Promise<void> {
    return peticion(`/api/comercios/${comercioId}/categoria`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario_id: usuarioId, categoria_id: categoriaId }),
    });
  },

  // ---- Presupuestos ----

  crearOActualizarPresupuesto(datos: {
    usuarioId: number;
    categoriaId: number;
    anio: number;
    mes: number;
    moneda: string;
    montoLimite: string;
    umbralAlerta: number;
  }): Promise<Presupuesto> {
    return peticion("/api/presupuestos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario_id: datos.usuarioId,
        categoria_id: datos.categoriaId,
        anio: datos.anio,
        mes: datos.mes,
        moneda: datos.moneda,
        monto_limite: datos.montoLimite,
        umbral_alerta: datos.umbralAlerta,
      }),
    });
  },

  eliminarPresupuesto(usuarioId: number, presupuestoId: number): Promise<void> {
    return peticion(`/api/presupuestos/${presupuestoId}?usuario_id=${usuarioId}`, {
      method: "DELETE",
    });
  },

  /** El límite comparado contra el gasto real ya clasificado del período, de
   * todas las cuentas activas -no solo el límite crudo. */
  estadoDePresupuestos(
    usuarioId: number,
    anio: number,
    mes: number,
    limite = 200,
  ): Promise<EstadoDePresupuesto[]> {
    const parametros = new URLSearchParams({
      usuario_id: String(usuarioId),
      anio: String(anio),
      mes: String(mes),
      limite: String(limite),
    });
    return peticion(`/api/cuentas-correo/presupuestos?${parametros.toString()}`);
  },

  // ---- Reportes ----

  descargarMovimientosCsv(usuarioId: number): Promise<void> {
    return descargarArchivo(
      `/api/cuentas-correo/reportes/movimientos.csv?usuario_id=${usuarioId}`,
      "gastonomo-movimientos.csv",
    );
  },

  descargarMovimientosExcel(usuarioId: number): Promise<void> {
    return descargarArchivo(
      `/api/cuentas-correo/reportes/movimientos.xlsx?usuario_id=${usuarioId}`,
      "gastonomo-movimientos.xlsx",
    );
  },

  descargarResumenPdf(usuarioId: number): Promise<void> {
    return descargarArchivo(
      `/api/cuentas-correo/reportes/resumen.pdf?usuario_id=${usuarioId}`,
      "gastonomo-reporte.pdf",
    );
  },

  // ---- Tipo de cambio ----

  /** 502 si el Banco Central no está configurado o no respondió -es normal que falle
   * mientras no haya una suscripción real; quien llama debe manejarlo como opcional. */
  tipoDeCambio(fecha?: string): Promise<TipoDeCambio> {
    const parametros = fecha ? `?fecha=${fecha}` : "";
    return peticion(`/api/tipo-cambio${parametros}`);
  },
};
