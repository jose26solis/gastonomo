/**
 * Bandera compartida entre quien inicia el viaje a Google (Login.tsx para
 * "Iniciar sesión con Google", Ajustes.tsx para vincularlo a una cuenta ya
 * logueada) y `CallbackGoogle.tsx`, la única página a la que Google vuelve
 * en los dos casos -ver la nota en ese archivo sobre por qué comparten
 * `redirect_uri` y por qué hace falta esta bandera para distinguirlos.
 *
 * Un solo archivo para la clave y los valores: que alguien escriba
 * "vincular" en un lugar y "vinclar" en otro por error no debe ser posible.
 */
export const CLAVE_FLUJO_GOOGLE = "gastonomo.google_flujo";

export type FlujoGoogle = "login" | "vincular";

export function marcarFlujoGoogle(flujo: FlujoGoogle): void {
  window.sessionStorage.setItem(CLAVE_FLUJO_GOOGLE, flujo);
}
