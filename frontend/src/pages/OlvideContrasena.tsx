import { useState } from "react";
import { api, ErrorDeApiError } from "../api";

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
 * "¿Olvidaste tu contraseña?" -pide el correo y pide el enlace de recuperación.
 *
 * Siempre termina en el mismo mensaje de éxito, exista o no una cuenta con ese
 * correo: es el mismo criterio que ya aplica `AuthService.iniciar_sesion` -no
 * hay que poder confirmar desde acá si un correo puntual tiene cuenta o no.
 * Por eso este formulario no distingue entre "listo, revisá tu correo" y
 * "ese correo no existe": para quien lo usa de verdad, los dos casos se ven
 * exactamente igual.
 */
export function OlvideContrasena() {
  const [correo, setCorreo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await api.solicitarRecuperacionContrasena(correo);
      setEnviado(true);
    } catch (e) {
      setError(e instanceof ErrorDeApiError ? e.message : "Ocurrió un error inesperado.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
      }}
    >
      <div className="card stack" style={{ width: "100%", maxWidth: 360, gap: 17 }}>
        <div>
          <div className="section-title" style={{ fontSize: 15 }}>
            Gastonomo
          </div>
          <div className="section-subtitle" style={{ marginTop: 4 }}>
            Recuperar contraseña
          </div>
        </div>

        {enviado ? (
          <p className="mensaje-exito">
            Si existe una cuenta con ese correo, te enviamos un enlace para restablecer la
            contraseña. Revisá tu bandeja de entrada -y la de spam, por si acaso.
          </p>
        ) : (
          <form onSubmit={enviar} className="stack" style={{ gap: 11 }}>
            <label className="stack" style={{ gap: 5 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Correo</span>
              <input
                type="email"
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
                placeholder="ana@ejemplo.cr"
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
              {enviando ? "Un momento…" : "Mandar enlace de recuperación"}
            </button>
          </form>
        )}

        <a
          href="/"
          style={{ fontSize: 11.5, color: "var(--color-accent-200)", textAlign: "left" }}
        >
          Volver a iniciar sesión
        </a>
      </div>
    </div>
  );
}
