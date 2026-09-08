import { useState } from "react";
import { ErrorDeApiError } from "../api";

const estiloInput: React.CSSProperties = {
  padding: "9px 11px",
  background: "var(--color-surface-2)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  color: "var(--color-text)",
  fontSize: 13,
  width: "100%",
};

/**
 * Página a la que apunta el enlace de "Olvidé mi contraseña" (`OlvideContrasena.tsx`).
 *
 * El `token` viaja como query param -no en la ruta- porque es justamente lo
 * que este formulario le manda de vuelta al backend para demostrar que quien
 * lo está usando tiene acceso a esa bandeja de entrada. Al confirmar, la
 * sesión queda iniciada de una vez -mismo criterio que registrarse- así que
 * de acá se puede ir derecho a la app, no hace falta loguearse aparte.
 */
export function RestablecerContrasena({
  onRestablecerContrasena,
}: {
  onRestablecerContrasena: (token: string, contrasenaNueva: string) => Promise<void>;
}) {
  const [token] = useState(() => new URLSearchParams(window.location.search).get("token"));
  const [contrasena, setContrasena] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [exito, setExito] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    if (contrasena !== confirmacion) {
      setError("Las dos contraseñas no coinciden.");
      return;
    }
    if (!token) return;

    setEnviando(true);
    try {
      await onRestablecerContrasena(token, contrasena);
      setExito(true);
    } catch (e) {
      setError(
        e instanceof ErrorDeApiError
          ? e.message
          : "No se pudo restablecer la contraseña.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="pagina-callback">
      <h1>Restablecer contraseña</h1>

      {!token && (
        <p className="mensaje-error">
          Este enlace no trae el token de recuperación. Pedí uno nuevo desde "¿Olvidaste tu
          contraseña?" en la pantalla de inicio de sesión.
        </p>
      )}

      {token && exito && (
        <p className="mensaje-exito">
          Listo, tu contraseña quedó actualizada y ya iniciaste sesión.
        </p>
      )}

      {token && !exito && (
        <form
          onSubmit={enviar}
          className="stack"
          style={{ gap: 11, textAlign: "left", maxWidth: 320, margin: "0 auto" }}
        >
          <label className="stack" style={{ gap: 5 }}>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
              Contraseña nueva
            </span>
            <input
              type="password"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              placeholder="Al menos 8 caracteres"
              minLength={8}
              required
              style={estiloInput}
            />
          </label>

          <label className="stack" style={{ gap: 5 }}>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
              Confirmar contraseña nueva
            </span>
            <input
              type="password"
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
              placeholder="Repetila igual"
              minLength={8}
              required
              style={estiloInput}
            />
          </label>

          {error && <p className="mensaje-error">{error}</p>}

          <button
            className="btn btn-primary"
            type="submit"
            disabled={enviando}
            style={{ justifyContent: "center", width: "100%" }}
          >
            {enviando ? "Un momento…" : "Restablecer contraseña"}
          </button>
        </form>
      )}

      <a href="/" className="enlace-volver">
        Ir a Gastonomo
      </a>
    </main>
  );
}
