import { CheckCircle, EnvelopeSimple, MicrosoftOutlookLogo, XCircle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { CuentaCorreo, MensajeResumido, Proveedor } from "../types";

const NOMBRE_PROVEEDOR: Record<Proveedor, string> = { OUTLOOK: "Outlook", GMAIL: "Gmail" };

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

export function ConectarCorreo({ usuarioId }: { usuarioId: number }) {
  const [cuentas, setCuentas] = useState<CuentaCorreo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [vinculando, setVinculando] = useState<Proveedor | null>(null);
  const [mensajesPorCuenta, setMensajesPorCuenta] = useState<
    Record<number, MensajeResumido[] | "cargando" | "error">
  >({});

  useEffect(() => {
    cargarCuentas();
  }, [usuarioId]); // eslint-disable-line react-hooks/exhaustive-deps

  function cargarCuentas() {
    setCargando(true);
    setError(null);
    api
      .listarCuentas(usuarioId)
      .then(setCuentas)
      .catch((e: unknown) => setError(mensajeDeError(e)))
      .finally(() => setCargando(false));
  }

  async function vincular(proveedor: Proveedor) {
    setVinculando(proveedor);
    try {
      const { url_autorizacion } = await api.iniciarVinculacion(usuarioId, proveedor);
      window.location.href = url_autorizacion;
    } catch (e) {
      setError(mensajeDeError(e));
      setVinculando(null);
    }
  }

  async function probarConexion(cuenta: CuentaCorreo) {
    setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: "cargando" }));
    try {
      const mensajes = await api.probarConexion(usuarioId, cuenta.id);
      setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: mensajes }));
    } catch {
      setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: "error" }));
    }
  }

  async function desvincular(cuenta: CuentaCorreo) {
    if (!window.confirm(`¿Desvincular ${cuenta.direccion}?`)) return;
    try {
      await api.desvincular(usuarioId, cuenta.id);
      cargarCuentas();
    } catch (e) {
      setError(mensajeDeError(e));
    }
  }

  const cuentaPorProveedor = (p: Proveedor) => cuentas.find((c) => c.proveedor === p);

  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      {error && <p className="mensaje-error">{error}</p>}

      <div className="grid grid-2">
        {(["OUTLOOK", "GMAIL"] as const).map((proveedor) => {
          const cuenta = cuentaPorProveedor(proveedor);
          const Icono = proveedor === "OUTLOOK" ? MicrosoftOutlookLogo : EnvelopeSimple;
          const conectada = cuenta?.estado === "ACTIVA";
          return (
            <div key={proveedor} className="card stack">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Icono size={18} color="var(--color-accent-200)" />
                <div className="section-title" style={{ flex: 1 }}>
                  {NOMBRE_PROVEEDOR[proveedor]}
                </div>
                <span style={{ fontSize: 10.5, color: conectada ? "var(--color-accent-200)" : "var(--color-text-dim)" }}>
                  {cuenta ? cuenta.estado : "Sin conectar"}
                </span>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--color-text-muted)", lineHeight: 1.6 }}>
                {proveedor === "OUTLOOK"
                  ? "Lee solo las notificaciones de BAC Credomatic, para extraer y sumar tus compras."
                  : "Mismo alcance que Outlook, una vez que se registre la app en Google Cloud."}
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                {cuenta ? cuenta.direccion : "Ninguna cuenta vinculada"}
              </div>
              {cuenta ? (
                <div style={{ display: "flex", gap: 7 }}>
                  <button className="btn btn-sm" onClick={() => probarConexion(cuenta)} disabled={cuenta.estado === "DESVINCULADA"}>
                    Probar conexión
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => desvincular(cuenta)}>
                    Desvincular
                  </button>
                </div>
              ) : (
                <button
                  className="btn btn-primary"
                  style={{ alignSelf: "flex-start" }}
                  onClick={() => vincular(proveedor)}
                  disabled={vinculando !== null}
                >
                  {vinculando === proveedor ? "Redirigiendo…" : `Conectar ${NOMBRE_PROVEEDOR[proveedor]}`}
                </button>
              )}

              {cuenta && mensajesPorCuenta[cuenta.id] === "cargando" && <p className="vacio">Consultando…</p>}
              {cuenta && mensajesPorCuenta[cuenta.id] === "error" && (
                <p className="mensaje-error">No se pudo leer la bandeja.</p>
              )}
              {cuenta && Array.isArray(mensajesPorCuenta[cuenta.id]) && (
                <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                  {(mensajesPorCuenta[cuenta.id] as MensajeResumido[]).map((m) => (
                    <div key={m.identificador} style={{ fontSize: 11, display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.asunto}</span>
                    </div>
                  ))}
                  {(mensajesPorCuenta[cuenta.id] as MensajeResumido[]).length === 0 && (
                    <p className="vacio">Sin correos de BAC en esta bandeja.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <section className="card">
        <div className="section-title">Qué lee Gastonomo</div>
        <div className="stack" style={{ gap: 3, marginTop: 11 }}>
          {[
            { ok: true, texto: "Notificaciones de transacción de BAC Credomatic" },
            { ok: true, texto: "Solo el remitente y el cuerpo del mensaje, nunca adjuntos" },
            { ok: false, texto: "Correos personales y conversaciones" },
            { ok: false, texto: "Contactos, calendario y archivos" },
          ].map((s) => {
            const Icono = s.ok ? CheckCircle : XCircle;
            return (
              <div
                key={s.texto}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 0",
                  borderTop: "1px solid var(--color-surface-2)",
                  fontSize: 12,
                  color: "var(--color-text-bright-muted)",
                }}
              >
                <Icono size={14} color={s.ok ? "var(--color-accent-200)" : "var(--color-text-dim)"} />
                <span style={{ flex: 1 }}>{s.texto}</span>
                <span style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                  {s.ok ? "Permitido" : "Sin acceso"}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {cargando && <p className="vacio">Cargando cuentas…</p>}
    </div>
  );
}
