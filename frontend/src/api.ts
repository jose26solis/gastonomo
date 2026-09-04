/**
 * Cliente HTTP hacia la API de Gastonomo.
 *
 * Un solo lugar que sabe la URL base y cómo traducir un error de negocio
 * (`{"detalle": "..."}`, la forma que arma `main.py` en el backend) a una
 * excepción de JavaScript. Los componentes nunca llaman a `fetch` directo.
 */

import type {
  BancoDetectado,
  CampoRegla,
  Categoria,
  ComercioClasificado,
  Compra,
  ComprobanteParseado,
  CuentaCorreo,
  ErrorDeApi,
  EstadoDePresupuesto,
  EventoBitacora,
  IniciarVinculacionResponse,
  MensajeResumido,
  MetodoPago,
  Presupuesto,
  Proveedor,
  ReglaCategorizacion,
  Sesion,
  ResumenFinancieroConFuente,
  TipoDeCambio,
  TipoMetodoPago,
  TransferenciaSinpe,
  UrlDeAutorizacion,
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

  /** Pide la URL de Google para "Iniciar sesión con Google" -público, nadie está identificado todavía. */
  iniciarLoginGoogle(): Promise<UrlDeAutorizacion> {
    return peticion("/api/auth/google/iniciar");
  },

  /** Completa el login: crea la cuenta si es la primera vez, o entra a la que ya existía. */
  completarLoginGoogle(codigo: string, estado: string): Promise<Sesion> {
    return peticion("/api/auth/google/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo, estado }),
    });
  },

  /** Pide la URL para vincular Google a la cuenta ya logueada -por eso sí necesita sesión. */
  iniciarVinculacionGoogle(): Promise<UrlDeAutorizacion> {
    return peticion("/api/auth/google/vincular/iniciar");
  },

  /** Completa la vinculación. Público a propósito: el `usuario_id` viaja cifrado dentro
   * de `estado`, no en un encabezado -es la misma cuenta que abrió `iniciarVinculacionGoogle`. */
  completarVinculacionGoogle(codigo: string, estado: string): Promise<Usuario> {
    return peticion("/api/auth/google/vincular/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo, estado }),
    });
  },

  desvincularGoogle(): Promise<Usuario> {
    return peticion("/api/auth/google/vincular", { method: "DELETE" });
  },

  /** `contrasenaActual` es null para ponerle una primera contraseña a una cuenta de solo Google. */
  cambiarContrasena(contrasenaActual: string | null, contrasenaNueva: string): Promise<Usuario> {
    return peticion("/api/auth/contrasena", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contrasena_actual: contrasenaActual,
        contrasena_nueva: contrasenaNueva,
      }),
    });
  },

  /** Prende o apaga "Leer transferencias SINPE" -el interruptor de Ajustes. */
  actualizarPreferenciaSinpe(activo: boolean): Promise<Usuario> {
    return peticion("/api/auth/preferencias/sinpe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activo }),
    });
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

  /**
   * Busca la palabra "banco" en todas las cuentas activas del titular y
   * agrupa lo que encuentra por dominio del remitente. Es una detección, no
   * una conexión real: solo BAC tiene parser hoy, el resto son candidatos.
   */
  detectarBancos(usuarioId: number, limite = 30): Promise<BancoDetectado[]> {
    const parametros = new URLSearchParams({ usuario_id: String(usuarioId), limite: String(limite) });
    return peticion(`/api/cuentas-correo/bancos?${parametros.toString()}`);
  },

  /**
   * Busca "sinpe" en el asunto de todas las cuentas activas y devuelve las
   * que sabe parsear (BAC y Banco Nacional). Vacío sin tocar la red si el
   * titular tiene apagado "Leer transferencias SINPE" en Ajustes.
   */
  transferenciasSinpe(usuarioId: number, limite = 100): Promise<TransferenciaSinpe[]> {
    const parametros = new URLSearchParams({ usuario_id: String(usuarioId), limite: String(limite) });
    return peticion(`/api/cuentas-correo/transferencias-sinpe?${parametros.toString()}`);
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

  // ---- Métodos de pago ----

  /** Sin esto la conciliación automática nunca tiene con qué emparejar los
   * últimos 4 dígitos que trae un comprobante -ver ConciliacionService. */
  crearMetodoPago(datos: {
    usuarioId: number;
    alias: string;
    tipo: TipoMetodoPago;
    moneda: string;
    ultimosCuatro?: string;
    entidad?: string;
    diaCorte?: number;
  }): Promise<MetodoPago> {
    return peticion("/api/metodos-pago", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario_id: datos.usuarioId,
        alias: datos.alias,
        tipo: datos.tipo,
        moneda: datos.moneda,
        ultimos_cuatro: datos.ultimosCuatro ?? null,
        entidad: datos.entidad ?? null,
        dia_corte: datos.diaCorte ?? null,
      }),
    });
  },

  listarMetodosPago(usuarioId: number): Promise<MetodoPago[]> {
    return peticion(`/api/metodos-pago?usuario_id=${usuarioId}`);
  },

  desactivarMetodoPago(usuarioId: number, metodoPagoId: number): Promise<MetodoPago> {
    return peticion(`/api/metodos-pago/${metodoPagoId}?usuario_id=${usuarioId}`, {
      method: "DELETE",
    });
  },

  // ---- Reglas de categorización ----

  /** Sin esto, `ReglaCategorizacion` era un modelo y un motor de evaluación
   * sin ningún dueño real -ver `regla_categorizacion_service.py`. */
  crearReglaCategorizacion(datos: {
    usuarioId: number;
    nombre: string;
    patron: string;
    categoriaDestinoId: number;
    campo?: CampoRegla;
    prioridad?: number;
  }): Promise<ReglaCategorizacion> {
    return peticion("/api/reglas-categorizacion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario_id: datos.usuarioId,
        nombre: datos.nombre,
        patron: datos.patron,
        categoria_destino_id: datos.categoriaDestinoId,
        campo: datos.campo ?? "COMERCIO_NORMALIZADO",
        prioridad: datos.prioridad ?? null,
      }),
    });
  },

  listarReglasCategorizacion(usuarioId: number): Promise<ReglaCategorizacion[]> {
    return peticion(`/api/reglas-categorizacion?usuario_id=${usuarioId}`);
  },

  desactivarReglaCategorizacion(usuarioId: number, reglaId: number): Promise<ReglaCategorizacion> {
    return peticion(`/api/reglas-categorizacion/${reglaId}?usuario_id=${usuarioId}`, {
      method: "DELETE",
    });
  },

  // ---- Compras reales ----

  /** Las compras ya conciliadas del titular, más recientes primero.
   * `requiereRevision: true` trae solo las que quedaron sin método de pago o
   * sin categoría -la lista que hace visible esa marca, antes invisible. */
  listarCompras(
    usuarioId: number,
    opciones?: { requiereRevision?: boolean; limite?: number },
  ): Promise<Compra[]> {
    const parametros = new URLSearchParams({ usuario_id: String(usuarioId) });
    if (opciones?.requiereRevision !== undefined) {
      parametros.set("requiere_revision", String(opciones.requiereRevision));
    }
    if (opciones?.limite) parametros.set("limite", String(opciones.limite));
    return peticion(`/api/compras?${parametros.toString()}`);
  },

  obtenerCompra(usuarioId: number, compraId: number): Promise<Compra> {
    return peticion(`/api/compras/${compraId}?usuario_id=${usuarioId}`);
  },

  /** Corrige a mano el método de pago y/o la categoría de una compra -pensada
   * para resolver una que quedó `requiere_revision`. Al menos uno de los dos
   * tiene que venir. */
  resolverRevisionCompra(
    usuarioId: number,
    compraId: number,
    datos: { metodoPagoId?: number; categoriaId?: number },
  ): Promise<Compra> {
    return peticion(`/api/compras/${compraId}/resolver?usuario_id=${usuarioId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        metodo_pago_id: datos.metodoPagoId ?? null,
        categoria_id: datos.categoriaId ?? null,
      }),
    });
  },

  // ---- Bitácora de compras ----

  /** La trazabilidad completa de una compra: de qué correo nació y cómo se
   * clasificó. 404 si la compra no existe, no es del titular, o no concilió
   * -ver la nota de `compra_id` en `ComprobanteConFuente`. */
  bitacoraDeCompra(usuarioId: number, compraId: number): Promise<EventoBitacora[]> {
    return peticion(`/api/compras/${compraId}/bitacora?usuario_id=${usuarioId}`);
  },

  // ---- Tipo de cambio ----

  /** 502 si el Banco Central no está configurado o no respondió -es normal que falle
   * mientras no haya una suscripción real; quien llama debe manejarlo como opcional. */
  tipoDeCambio(fecha?: string): Promise<TipoDeCambio> {
    const parametros = fecha ? `?fecha=${fecha}` : "";
    return peticion(`/api/tipo-cambio${parametros}`);
  },
};
