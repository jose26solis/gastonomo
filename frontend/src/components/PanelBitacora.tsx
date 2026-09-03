import { CheckCircle, Clock, WarningCircle, X } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearFechaHora } from "../lib/formato";
import type { EventoBitacora } from "../types";

const ETIQUETA_TIPO: Record<string, string> = {
  INGESTA_RECIBIDA: "Correo recibido",
  PARSEO_COMPROBANTE: "Comprobante leído",
  EMPAREJAMIENTO_METODO_PAGO: "Método de pago emparejado",
  RESOLUCION_COMERCIO: "Comercio resuelto",
  CATEGORIZACION_AUTOMATICA: "Categorizado automáticamente",
  CORRECCION_MANUAL: "Corrección manual",
  DESGLOSE_MANUAL: "Desglose manual",
  CONVERSION_MONEDA: "Conversión de moneda",
  IMPACTO_PRESUPUESTO: "Impactó un presupuesto",
  ALERTA_PRESUPUESTO: "Alerta de presupuesto",
  CAMBIO_ESTADO: "Cambio de estado",
  REVISION_REQUERIDA: "Requiere revisión",
  ANULACION: "Compra anulada",
};

const ETIQUETA_ACTOR: Record<string, string> = {
  TITULAR: "El titular",
  SERVICIO: "La ingesta automática",
  SISTEMA: "El sistema",
};

function mensajeDeError(error: unknown): string {
  if (error instanceof ErrorDeApiError && error.status === 404) {
    return "Esta compra todavía no tiene bitácora registrada.";
  }
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

function formatearDatos(datos: Record<string, unknown>): [string, string][] {
  return Object.entries(datos)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([clave, valor]) => [
      clave.replaceAll("_", " "),
      typeof valor === "object" ? JSON.stringify(valor) : String(valor),
    ]);
}

/**
 * Panel deslizable con la línea de tiempo completa de una compra: de qué
 * correo nació, cómo se emparejó el método de pago, qué regla la
 * categorizó, si afectó un presupuesto. Es el diferenciador declarado del
 * dominio -bajar de cualquier total en pantalla hasta el evento que lo
 * explica- ver ADR-002 y `docs/propuesta-dominio.md`.
 */
export function PanelBitacora({
  usuarioId,
  compraId,
  titulo,
  onCerrar,
}: {
  usuarioId: number;
  compraId: number;
  /** Lo que ya se ve en la fila del movimiento -comercio y fecha- para no
   * repetir un fetch solo para encabezar el panel. */
  titulo: string;
  onCerrar: () => void;
}) {
  const [eventos, setEventos] = useState<EventoBitacora[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar la bitácora de la
    // compra anterior mientras el fetch de la nueva está en curso.
    // oxlint-disable-next-line react/set-state-in-effect
    setEventos(null);
    setError(null);
    api
      .bitacoraDeCompra(usuarioId, compraId)
      .then((e) => {
        if (!cancelado) setEventos(e);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, compraId]);

  return (
    <>
      <div className="panel-backdrop" onClick={onCerrar} aria-hidden="true" />
      <aside className="panel-drawer" role="dialog" aria-label="Bitácora de la compra">
        <div style={{ display: "flex", alignItems: "flex-start", gap: 11, padding: 17, borderBottom: "1px solid var(--color-border)" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="section-title">Trazabilidad completa</div>
            <div className="section-subtitle" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {titulo}
            </div>
          </div>
          <button
            className="btn btn-sm"
            onClick={onCerrar}
            aria-label="Cerrar"
            style={{ padding: 6 }}
          >
            <X size={13} />
          </button>
        </div>

        <div className="stack" style={{ padding: 17, gap: 0 }}>
          {error && <p className="mensaje-error">{error}</p>}
          {!error && eventos === null && <p className="vacio">Leyendo la bitácora…</p>}
          {!error && eventos !== null && eventos.length === 0 && (
            <p className="vacio">Sin eventos registrados para esta compra.</p>
          )}
          {!error &&
            eventos !== null &&
            eventos.map((evento, i) => {
              const esUltimo = i === eventos.length - 1;
              const esAlerta = evento.tipo === "REVISION_REQUERIDA" || evento.tipo === "ALERTA_PRESUPUESTO";
              const Icono = esAlerta ? WarningCircle : CheckCircle;
              const datos = formatearDatos(evento.datos);
              return (
                <div key={evento.secuencia} style={{ display: "flex", gap: 11 }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <span
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        display: "grid",
                        placeItems: "center",
                        flexShrink: 0,
                        background: "var(--color-surface-2)",
                        color: esAlerta ? "#e8a33d" : "var(--color-accent-200)",
                      }}
                    >
                      <Icono size={13} weight="fill" />
                    </span>
                    {!esUltimo && <span style={{ flex: 1, width: 1, background: "var(--color-border)", minHeight: 18 }} />}
                  </div>
                  <div style={{ paddingBottom: esUltimo ? 0 : 17, flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 7, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 12.5 }}>{ETIQUETA_TIPO[evento.tipo] ?? evento.tipo}</span>
                      <span style={{ fontSize: 10, color: "var(--color-text-dim)", display: "flex", alignItems: "center", gap: 3 }}>
                        <Clock size={10} /> {formatearFechaHora(evento.ocurrido_en)}
                      </span>
                    </div>
                    <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>
                      {ETIQUETA_ACTOR[evento.actor.tipo] ?? evento.actor.tipo}
                      {evento.actor.nombre ? ` · ${evento.actor.nombre}` : ""}
                    </div>
                    {datos.length > 0 && (
                      <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 2 }}>
                        {datos.map(([clave, valor]) => (
                          <div key={clave} style={{ fontSize: 10.5, color: "var(--color-text-muted)" }}>
                            <span style={{ color: "var(--color-text-dim)" }}>{clave}:</span> {valor}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </aside>
    </>
  );
}
