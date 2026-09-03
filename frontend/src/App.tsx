import { AppShell } from "./components/AppShell";
import { useSesion } from "./lib/useSesion";
import { CallbackVinculacion } from "./pages/CallbackVinculacion";
import { PoliticaDePrivacidad } from "./pages/legal/PoliticaDePrivacidad";
import { TerminosDeUso } from "./pages/legal/TerminosDeUso";
import { Login } from "./pages/Login";

/**
 * Enrutamiento manual por `pathname`.
 *
 * No todas las rutas necesitan sesión iniciada -al revés, /privacidad y
 * /terminos tienen que funcionar SIN login: es lo que exige la verificación
 * de apps de Google y lo que las tiendas revisan antes de publicar la ficha.
 * Por eso se resuelven antes de mirar si hay usuario. El resto de la
 * navegación es estado de React dentro de `AppShell`, no URLs -agregar
 * `react-router` para esto sería una dependencia entera para reemplazar un
 * puñado de líneas de `if`.
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
  if (pathname === "/privacidad") {
    return <PoliticaDePrivacidad />;
  }
  if (pathname === "/terminos") {
    return <TerminosDeUso />;
  }

  if (cargando) {
    return null;
  }
  if (!usuario) {
    return <Login onRegistrar={registrar} onIniciarSesion={iniciarSesion} />;
  }
  return <AppShell usuario={usuario} onCerrarSesion={cerrarSesion} />;
}
