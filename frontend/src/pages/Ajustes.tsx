import { CheckCircle, GoogleLogo, XCircle } from "@phosphor-icons/react";
import { useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { marcarFlujoGoogle } from "../lib/flujoGoogle";
import { MuestraBadge } from "../components/MuestraBadge";
import type { Usuario } from "../types";

const AJUSTES_DEF = [
  { clave: "autoCat", titulo: "Clasificar con IA al recibir", cuerpo: "Cada comprobante nuevo se categorizaría al llegar, sin esperar una sincronización manual." },
  { clave: "alertas", titulo: "Alertas de presupuesto", cuerpo: "Aviso cuando una categoría cruza el umbral configurado." },
  { clave: "sinpe", titulo: "Leer transferencias SINPE", cuerpo: "Incluir transferencias móviles aunque no traigan el formato de compra que ya se reconoce." },
  { clave: "ocultar", titulo: "Ocultar montos al compartir pantalla", cuerpo: "Reemplaza las cifras por puntos mientras la ventana no está enfocada." },
] as const;

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

const estiloInput: React.CSSProperties = {
  padding: "7px 10px",
  background: "var(--color-surface-2)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  color: "var(--color-text)",
  fontSize: 12,
  width: "100%",
};

export function Ajustes({
  usuario,
  onActualizarUsuario,
}: {
  usuario: Usuario;
  onActualizarUsuario: (usuario: Usuario) => void;
}) {
  const [valores, setValores] = useState<Record<string, boolean>>({
    autoCat: false,
    alertas: true,
    sinpe: false,
    ocultar: false,
  });

  return (
    <div className="stack" style={{ maxWidth: 640 }}>
      <CuentaCard usuario={usuario} onActualizarUsuario={onActualizarUsuario} />

      <MuestraBadge>
        Datos de ejemplo — estos interruptores no están conectados a ninguna preferencia guardada
        todavía; solo cambian en esta pantalla mientras la tenés abierta.
      </MuestraBadge>

      {AJUSTES_DEF.map((a) => {
        const activo = valores[a.clave];
        return (
          <div key={a.clave} className="card" style={{ display: "flex", alignItems: "center", gap: 17 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5 }}>{a.titulo}</div>
              <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginTop: 3, lineHeight: 1.5 }}>{a.cuerpo}</div>
            </div>
            <button
              onClick={() => setValores((v) => ({ ...v, [a.clave]: !v[a.clave] }))}
              style={{
                width: 38,
                height: 21,
                borderRadius: 20,
                border: `1px solid ${activo ? "var(--color-accent-400)" : "var(--color-border-strong)"}`,
                background: activo ? "var(--color-accent-600)" : "var(--color-surface-2)",
                cursor: "pointer",
                padding: "0 2px",
                display: "flex",
                alignItems: "center",
                justifyContent: activo ? "flex-end" : "flex-start",
              }}
            >
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: activo ? "var(--color-accent-100)" : "var(--color-text-dim)",
                  display: "block",
                }}
              />
            </button>
          </div>
        );
      })}
    </div>
  );
}

function CuentaCard({
  usuario,
  onActualizarUsuario,
}: {
  usuario: Usuario;
  onActualizarUsuario: (usuario: Usuario) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [vinculandoGoogle, setVinculandoGoogle] = useState(false);
  const [desvinculando, setDesvinculando] = useState(false);

  // Google es el único método de acceso: desvincularlo dejaría la cuenta sin
  // ninguno, y el backend lo rechaza -mejor explicarlo acá que dejar tocar
  // el botón y mostrar el error recién después.
  const puedeDesvincularGoogle = usuario.tiene_contrasena;

  async function vincularGoogle() {
    setError(null);
    setVinculandoGoogle(true);
    try {
      const { url_autorizacion } = await api.iniciarVinculacionGoogle();
      marcarFlujoGoogle("vincular");
      window.location.href = url_autorizacion;
    } catch (e) {
      setError(mensajeDeError(e));
      setVinculandoGoogle(false);
    }
  }

  async function desvincularGoogle() {
    if (!window.confirm("¿Desvincular Google como método de acceso?")) return;
    setError(null);
    setExito(null);
    setDesvinculando(true);
    try {
      onActualizarUsuario(await api.desvincularGoogle());
      setExito("Google quedó desvinculado.");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setDesvinculando(false);
    }
  }

  return (
    <section className="card stack">
      <div className="section-title">Mi cuenta</div>

      <div className="stack" style={{ gap: 3 }}>
        <div style={{ fontSize: 13 }}>{usuario.nombre_completo}</div>
        <div style={{ fontSize: 11.5, color: "var(--color-text-dim)" }}>{usuario.correo}</div>
      </div>

      {error && <p className="mensaje-error">{error}</p>}
      {exito && <p className="mensaje-exito">{exito}</p>}

      <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 14 }} className="stack">
        <div style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Métodos de acceso</div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <GoogleLogo size={15} color="var(--color-text-muted)" />
          <span style={{ flex: 1, fontSize: 12 }}>Google</span>
          {usuario.google_vinculado ? (
            <>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10.5, color: "var(--color-accent-200)" }}>
                <CheckCircle size={13} weight="fill" /> Vinculado
              </span>
              <button
                className="btn btn-sm"
                onClick={desvincularGoogle}
                disabled={!puedeDesvincularGoogle || desvinculando}
                title={
                  puedeDesvincularGoogle
                    ? undefined
                    : "Es tu único método de acceso: poné una contraseña antes de desvincularlo."
                }
              >
                Desvincular
              </button>
            </>
          ) : (
            <>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10.5, color: "var(--color-text-dim)" }}>
                <XCircle size={13} /> Sin vincular
              </span>
              <button className="btn btn-sm" onClick={vincularGoogle} disabled={vinculandoGoogle}>
                {vinculandoGoogle ? "Redirigiendo…" : "Vincular"}
              </button>
            </>
          )}
        </div>
        {usuario.google_vinculado && !puedeDesvincularGoogle && (
          <p style={{ fontSize: 10.5, color: "var(--color-text-dim)", margin: 0 }}>
            Es tu único método de acceso: poné una contraseña abajo antes de poder desvincularlo.
          </p>
        )}
      </div>

      <FormularioContrasena
        tieneContrasena={usuario.tiene_contrasena}
        onCambiada={(actualizado) => {
          onActualizarUsuario(actualizado);
          setExito("Contraseña actualizada.");
        }}
      />
    </section>
  );
}

function FormularioContrasena({
  tieneContrasena,
  onCambiada,
}: {
  tieneContrasena: boolean;
  onCambiada: (usuario: Usuario) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [contrasenaActual, setContrasenaActual] = useState("");
  const [contrasenaNueva, setContrasenaNueva] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    setGuardando(true);
    try {
      const actualizado = await api.cambiarContrasena(
        tieneContrasena ? contrasenaActual : null,
        contrasenaNueva,
      );
      onCambiada(actualizado);
      setContrasenaActual("");
      setContrasenaNueva("");
      setAbierto(false);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setGuardando(false);
    }
  }

  if (!abierto) {
    return (
      <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 14 }}>
        <button className="btn btn-sm" onClick={() => setAbierto(true)}>
          {tieneContrasena ? "Cambiar contraseña" : "Poner una contraseña"}
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={guardar}
      className="stack"
      style={{ gap: 8, borderTop: "1px solid var(--color-border)", paddingTop: 14 }}
    >
      <div style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
        {tieneContrasena ? "Cambiar contraseña" : "Poner una contraseña"}
      </div>
      {tieneContrasena && (
        <input
          type="password"
          value={contrasenaActual}
          onChange={(e) => setContrasenaActual(e.target.value)}
          placeholder="Contraseña actual"
          required
          style={estiloInput}
        />
      )}
      <input
        type="password"
        value={contrasenaNueva}
        onChange={(e) => setContrasenaNueva(e.target.value)}
        placeholder="Contraseña nueva, al menos 8 caracteres"
        minLength={8}
        required
        style={estiloInput}
      />
      {error && <p className="mensaje-error">{error}</p>}
      <div style={{ display: "flex", gap: 7 }}>
        <button className="btn btn-primary btn-sm" type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        <button
          className="btn btn-sm"
          type="button"
          onClick={() => {
            setAbierto(false);
            setError(null);
          }}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}
