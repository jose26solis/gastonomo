import { CallbackVinculacion } from "./pages/CallbackVinculacion";
import { CuentasCorreo } from "./pages/CuentasCorreo";

/**
 * Enrutamiento manual por `pathname`.
 *
 * Solo hay tres pantallas y ninguna necesita parámetros de ruta ni
 * navegación con historial propio: agregar `react-router` para esto sería
 * una dependencia entera para reemplazar tres líneas de `if`.
 */
export function App() {
  const { pathname } = window.location;

  if (pathname === "/vincular/outlook/callback") {
    return <CallbackVinculacion proveedor="OUTLOOK" />;
  }
  if (pathname === "/vincular/gmail/callback") {
    return <CallbackVinculacion proveedor="GMAIL" />;
  }
  return <CuentasCorreo />;
}
