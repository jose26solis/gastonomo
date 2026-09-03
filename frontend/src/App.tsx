import { AppShell } from "./components/AppShell";
import { useSesion } from "./lib/useSesion";
import { CallbackVinculacion } from "./pages/CallbackVinculacion";
import { Login } from "./pages/Login";

/**
 * Enrutamiento manual por `pathname`.
 *
 * Solo hay tres rutas de verdad -el resto de la navegación es estado de
 * React dentro de `AppShell`, no URLs- y ninguna necesita parámetros ni
 * historial propio: agregar `react-router` para esto sería una dependencia
 * entera para reemplazar tres líneas de `if`.
 */
export function App() {
  const { pathname } = window.location;
  const { usuario, cargando, registrar, iniciarSesion, cerrarSesion } = useSesion();

  if (pathname === "/vincular/outlook/callback") {
    return <CallbackVinculacion proveedor="OUTLOOK" />;
  }
  if (pathname === "/vincular/gmail/callback") {
    return <CallbackVinculacion proveedor="GMAIL" />;
  }

  if (cargando) {
    return null;
  }
  if (!usuario) {
    return <Login onRegistrar={registrar} onIniciarSesion={iniciarSesion} />;
  }
  return <AppShell usuario={usuario} onCerrarSesion={cerrarSesion} />;
}
