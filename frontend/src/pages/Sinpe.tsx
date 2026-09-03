import { ArrowsLeftRight, EnvelopeSimple } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearFechaCorta, formatearMonto } from "../lib/formato";
import { useCuentaActiva } from "../lib/useCuentaActiva";
import { MuestraBadge } from "../components/MuestraBadge";
import type { TransferenciaSinpe, Usuario } from "../types";

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

export function Sinpe({
  usuarioId,
  usuario,
  onActualizarUsuario,
  onIrAConectar,
}: {
  usuarioId: number;
  usuario: Usuario;
  onActualizarUsuario: (usuario: Usuario) => void;
  onIrAConectar: () => void;
}) {
  const { cargando: cargandoCuenta, hayCuentaActiva, error: errorCuenta } = useCuentaActiva(usuarioId);
  const [transferencias, setTransferencias] = useState<TransferenciaSinpe[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cambiandoPreferencia, setCambiandoPreferencia] = useState(false);

  useEffect(() => {
    if (!hayCuentaActiva || !usuario.leer_transferencias_sinpe) return;
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar datos obsoletos
    // mientras el fetch está en curso, igual que en Bancos.tsx/Presupuestos.tsx.
    // oxlint-disable-next-line react/set-state-in-effect
    setTransferencias(null);
    api
      .transferenciasSinpe(usuarioId)
      .then((t) => {
        if (!cancelado) setTransferencias(t);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, hayCuentaActiva, usuario.leer_transferencias_sinpe]);

  async function activar() {
    setError(null);
    setCambiandoPreferencia(true);
    try {
      onActualizarUsuario(await api.actualizarPreferenciaSinpe(true));
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCambiandoPreferencia(false);
    }
  }

  async function desactivar() {
    setError(null);
    setCambiandoPreferencia(true);
    try {
      onActualizarUsuario(await api.actualizarPreferenciaSinpe(false));
      setTransferencias(null);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCambiandoPreferencia(false);
    }
  }

  if (errorCuenta) {
    return <p className="mensaje-error">{errorCuenta}</p>;
  }
  if (cargandoCuenta) {
    return <p className="vacio">Cargando…</p>;
  }
  if (!hayCuentaActiva) {
    return (
      <div className="card stack" style={{ maxWidth: 480 }}>
        <div className="section-title">Todavía no hay ningún buzón vinculado</div>
        <p className="section-subtitle" style={{ margin: 0 }}>
          Vinculá Outlook o Gmail para leer tus transferencias SINPE.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  if (!usuario.leer_transferencias_sinpe) {
    return (
      <div className="stack" style={{ maxWidth: 900 }}>
        {error && <p className="mensaje-error">{error}</p>}
        <div className="card stack" style={{ maxWidth: 480 }}>
          <div className="section-title">Leer transferencias SINPE está apagado</div>
          <p className="section-subtitle" style={{ margin: 0 }}>
            Buscar "sinpe" en tu correo es una petición real por cada buzón vinculado -por eso
            este interruptor empieza apagado. Activalo acá o en Ajustes.
          </p>
          <button
            className="btn btn-primary"
            style={{ alignSelf: "flex-start" }}
            onClick={activar}
            disabled={cambiandoPreferencia}
          >
            {cambiandoPreferencia ? "Activando…" : "Activar"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      {error && <p className="mensaje-error">{error}</p>}

      <MuestraBadge>
        Transferencias SINPE recibidas, leídas de verdad de tu correo. Solo BAC y el Banco
        Nacional tienen lector hoy -otro banco que también te escriba avisos de SINPE todavía no
        aparece acá.
      </MuestraBadge>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-sm" onClick={desactivar} disabled={cambiandoPreferencia}>
          {cambiandoPreferencia ? "Desactivando…" : "Desactivar"}
        </button>
      </div>

      {transferencias === null && <p className="vacio">Buscando transferencias SINPE en tu correo…</p>}

      {transferencias !== null && transferencias.length === 0 && (
        <p className="vacio">No encontramos transferencias SINPE de BAC ni del Banco Nacional.</p>
      )}

      {transferencias?.map((t, i) => (
        <section key={`${t.cuenta_correo_id}-${t.referencia ?? i}`} className="card stack">
          <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                border: "1px solid var(--color-border-accent)",
                display: "grid",
                placeItems: "center",
                color: "var(--color-accent-200)",
              }}
            >
              <ArrowsLeftRight size={16} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{t.banco}</div>
              <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>
                {t.concepto ?? "Sin concepto"}
                {t.cuenta_destino ? ` · ${t.cuenta_destino}` : ""}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 14, fontVariantNumeric: "tabular-nums" }}>
                {t.monto ? formatearMonto(Number(t.monto), t.moneda ?? "CRC") : "—"}
              </div>
              {t.fecha && (
                <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>
                  {formatearFechaCorta(t.fecha)}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 18, fontSize: 10.5, color: "var(--color-text-dim)" }}>
            {t.referencia && <span>Ref. {t.referencia}</span>}
            {t.comprobante && <span>Comprobante {t.comprobante}</span>}
            {!t.es_confiable && <span style={{ color: "var(--color-accent-200)" }}>Revisar: datos incompletos</span>}
          </div>
        </section>
      ))}
    </div>
  );
}
