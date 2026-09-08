import { useEffect, useState } from "react";
import { api, establecerTokenDeSesion } from "../api";
import type { Usuario } from "../types";

const CLAVE_TOKEN = "gastonomo.token";

/**
 * Sesión del titular: quién está logueado, y registrarse/iniciar
 * sesión/cerrar sesión. Reemplaza al `usuario_id` que antes se escribía a
 * mano en el encabezado -ahora lo decide con quién se inició sesión, no un
 * número libre en un campo de texto.
 *
 * El token vive en `localStorage` -sobrevive a cerrar la pestaña, como
 * cualquier sesión de verdad- y se confirma contra `GET /api/auth/yo` al
 * cargar la página: uno vencido (30 días) o de un usuario desactivado no
 * debería dejar pasar a la app mostrando una pantalla que después falla en
 * cada pedido.
 */
export function useSesion() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const guardado = window.localStorage.getItem(CLAVE_TOKEN);
    if (!guardado) {
      // Sin token guardado no hay nada que confirmar contra el servidor.
      // oxlint-disable-next-line react/set-state-in-effect
      setCargando(false);
      return;
    }
    establecerTokenDeSesion(guardado);
    api
      .yo()
      .then(setUsuario)
      .catch(() => {
        establecerTokenDeSesion(null);
        window.localStorage.removeItem(CLAVE_TOKEN);
      })
      .finally(() => setCargando(false));
  }, []);

  function guardarSesion(sesion: { token: string; usuario: Usuario }) {
    establecerTokenDeSesion(sesion.token);
    window.localStorage.setItem(CLAVE_TOKEN, sesion.token);
    setUsuario(sesion.usuario);
  }

  async function registrar(nombreCompleto: string, correo: string, contrasena: string) {
    guardarSesion(await api.registrar(nombreCompleto, correo, contrasena));
  }

  async function iniciarSesion(correo: string, contrasena: string) {
    guardarSesion(await api.iniciarSesion(correo, contrasena));
  }

  /** Llamado desde la página de retorno de Google (`CallbackGoogle.tsx`) tras completar el login. */
  async function iniciarSesionConGoogle(codigo: string, estado: string) {
    guardarSesion(await api.completarLoginGoogle(codigo, estado));
  }

  /** Llamado desde `RestablecerContrasena.tsx` tras confirmar el enlace de
   * recuperación -deja al titular ya logueado, mismo criterio que registrarse. */
  async function restablecerContrasena(token: string, contrasenaNueva: string) {
    guardarSesion(await api.restablecerContrasena(token, contrasenaNueva));
  }

  /**
   * Refleja en la sesión un cambio de perfil que no vino con un token nuevo
   * -vincular o desvincular Google, cambiar la contraseña. El token sigue
   * siendo el mismo; lo único que cambió es qué dice `usuario`.
   */
  function actualizarUsuario(actualizado: Usuario) {
    setUsuario(actualizado);
  }

  /**
   * No hay nada que avisarle al servidor: el token no vive en ninguna tabla
   * (ver `auth_service.py`), así que "cerrar sesión" es, del todo, olvidarlo acá.
   */
  function cerrarSesion() {
    establecerTokenDeSesion(null);
    window.localStorage.removeItem(CLAVE_TOKEN);
    setUsuario(null);
  }

  return {
    usuario,
    cargando,
    registrar,
    iniciarSesion,
    iniciarSesionConGoogle,
    restablecerContrasena,
    actualizarUsuario,
    cerrarSesion,
  };
}
