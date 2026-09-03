import { Bank, EnvelopeSimple } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearFechaCorta } from "../lib/formato";
import { useCuentaActiva } from "../lib/useCuentaActiva";
import { MuestraBadge } from "../components/MuestraBadge";
import type { BancoDetectado, Proveedor } from "../types";

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

const NOMBRE_PROVEEDOR: Record<Proveedor, string> = {
  OUTLOOK: "Outlook",
  GMAIL: "Gmail",
};

/** Del dominio del remitente a algo más corto para el círculo de iniciales, ej. "baccredomatic.cr" -> "BAC". */
function abreviaturaDe(dominio: string): string {
  const raiz = dominio.split(".")[0] ?? dominio;
  return raiz.slice(0, 4).toUpperCase();
}

export function Bancos({ usuarioId, onIrAConectar }: { usuarioId: number; onIrAConectar: () => void }) {
  const { cargando: cargandoCuenta, hayCuentaActiva, error: errorCuenta } = useCuentaActiva(usuarioId);
  const [bancos, setBancos] = useState<BancoDetectado[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hayCuentaActiva) return;
    let cancelado = false;
    api
      .detectarBancos(usuarioId)
      .then((b) => {
        if (!cancelado) setBancos(b);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, hayCuentaActiva]);

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
          Vinculá Outlook o Gmail para que Gastonomo busque avisos de banco en tu correo.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      {error && <p className="mensaje-error">{error}</p>}

      <MuestraBadge>
        Búsqueda real de la palabra "banco" en tus buzones vinculados. Solo BAC tiene un parser que lee
        montos y comercios de verdad hoy -el resto son candidatos: bancos que sí te escriben, pero a los
        que Gastonomo todavía no sabe leerles el detalle de cada movimiento.
      </MuestraBadge>

      {bancos === null && <p className="vacio">Buscando avisos de banco en tu correo…</p>}

      {bancos !== null && bancos.length === 0 && (
        <p className="vacio">No encontramos correos con la palabra "banco" en tus buzones vinculados.</p>
      )}

      {bancos?.map((b) => (
        <section key={`${b.cuenta_correo_id}-${b.dominio}`} className="card stack">
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
                fontSize: 10,
                fontWeight: 500,
              }}
            >
              {b.es_bac ? <Bank size={16} /> : abreviaturaDe(b.dominio)}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{b.dominio}</div>
              <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>
                {b.remitente_ejemplo} · {NOMBRE_PROVEEDOR[b.proveedor]} ({b.direccion})
              </div>
            </div>
            <span
              style={{
                fontSize: 10.5,
                padding: "3px 8px",
                borderRadius: 999,
                color: b.es_bac ? "var(--color-accent-100)" : "var(--color-text-muted)",
                border: `1px solid ${b.es_bac ? "var(--color-accent-500)" : "var(--color-surface-2)"}`,
              }}
            >
              {b.es_bac ? "Conectado" : "Candidato, sin soporte todavía"}
            </span>
          </div>
          <div style={{ display: "flex", gap: 18, fontSize: 10.5, color: "var(--color-text-dim)" }}>
            <span>
              {b.cantidad_mensajes} {b.cantidad_mensajes === 1 ? "correo encontrado" : "correos encontrados"}
            </span>
            {b.mensaje_mas_reciente && <span>Más reciente: {formatearFechaCorta(b.mensaje_mas_reciente)}</span>}
          </div>
        </section>
      ))}
    </div>
  );
}
