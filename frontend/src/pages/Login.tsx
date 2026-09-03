import { useState } from "react";
import { ErrorDeApiError } from "../api";

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

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
 * Registro e inicio de sesión, en una sola pantalla que alterna entre los dos
 * modos -son el mismo formulario con un campo de más (`nombreCompleto`), no
 * dos flujos separados que valga la pena mantener aparte.
 */
export function Login({
  onRegistrar,
  onIniciarSesion,
}: {
  onRegistrar: (nombreCompleto: string, correo: string, contrasena: string) => Promise<void>;
  onIniciarSesion: (correo: string, contrasena: string) => Promise<void>;
}) {
  const [modo, setModo] = useState<"iniciar-sesion" | "registro">("iniciar-sesion");
  const [nombreCompleto, setNombreCompleto] = useState("");
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      if (modo === "registro") {
        await onRegistrar(nombreCompleto, correo, contrasena);
      } else {
        await onIniciarSesion(correo, contrasena);
      }
    } catch (e) {
      setError(mensajeDeError(e));
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
            {modo === "registro" ? "Creá tu cuenta" : "Iniciá sesión para ver tus gastos"}
          </div>
        </div>

        <form onSubmit={enviar} className="stack" style={{ gap: 11 }}>
          {modo === "registro" && (
            <label className="stack" style={{ gap: 5 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Nombre completo</span>
              <input
                value={nombreCompleto}
                onChange={(e) => setNombreCompleto(e.target.value)}
                placeholder="Ana Pérez"
                required
                style={estiloInput}
              />
            </label>
          )}

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

          <label className="stack" style={{ gap: 5 }}>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Contraseña</span>
            <input
              type="password"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              placeholder={modo === "registro" ? "Al menos 8 caracteres" : "••••••••"}
              minLength={modo === "registro" ? 8 : undefined}
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
            {enviando
              ? "Un momento…"
              : modo === "registro"
                ? "Crear cuenta"
                : "Iniciar sesión"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setModo(modo === "registro" ? "iniciar-sesion" : "registro");
            setError(null);
          }}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--color-accent-200)",
            cursor: "pointer",
            fontSize: 11.5,
            padding: 0,
            textAlign: "left",
          }}
        >
          {modo === "registro"
            ? "¿Ya tenés cuenta? Iniciá sesión"
            : "¿Todavía no tenés cuenta? Registrate"}
        </button>

        {modo === "registro" && (
          <p style={{ fontSize: 10.5, color: "var(--color-text-dim)", margin: 0, lineHeight: 1.6 }}>
            Al crear una cuenta aceptás los{" "}
            <a href="/terminos" style={{ color: "var(--color-text-dim)" }}>
              Términos de uso
            </a>{" "}
            y la{" "}
            <a href="/privacidad" style={{ color: "var(--color-text-dim)" }}>
              Política de privacidad
            </a>
            .
          </p>
        )}
      </div>
    </div>
  );
}
