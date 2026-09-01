import { EnvelopeSimple, FileCsv, FilePdf, FileXls } from "@phosphor-icons/react";
import { useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { useCuentaActiva } from "../lib/useCuentaActiva";

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

type Formato = "csv" | "xlsx" | "pdf";

const FORMATOS: { id: Formato; etiqueta: string; descripcion: string; icono: React.ElementType }[] = [
  { id: "csv", etiqueta: "CSV", descripcion: "Detalle de movimientos, uno por fila", icono: FileCsv },
  { id: "xlsx", etiqueta: "Excel", descripcion: "Lo mismo, en una hoja de cálculo", icono: FileXls },
  { id: "pdf", etiqueta: "PDF", descripcion: "Reporte de una página del mes más reciente", icono: FilePdf },
];

export function Reportes({ usuarioId, onIrAConectar }: { usuarioId: number; onIrAConectar: () => void }) {
  const { cargando, cuentaActiva, error: errorCuenta } = useCuentaActiva(usuarioId);
  const [descargando, setDescargando] = useState<Formato | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function descargar(formato: Formato) {
    if (!cuentaActiva) return;
    setDescargando(formato);
    setError(null);
    try {
      if (formato === "csv") await api.descargarMovimientosCsv(usuarioId, cuentaActiva.id);
      if (formato === "xlsx") await api.descargarMovimientosExcel(usuarioId, cuentaActiva.id);
      if (formato === "pdf") await api.descargarResumenPdf(usuarioId, cuentaActiva.id);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setDescargando(null);
    }
  }

  if (errorCuenta) {
    return <p className="mensaje-error">{errorCuenta}</p>;
  }
  if (cargando) {
    return <p className="vacio">Cargando…</p>;
  }
  if (!cuentaActiva) {
    return (
      <div className="card stack" style={{ maxWidth: 480 }}>
        <div className="section-title">Todavía no hay ningún buzón vinculado</div>
        <p className="section-subtitle" style={{ margin: 0 }}>
          Vinculá Outlook o Gmail para exportar tus comprobantes reales.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  return (
    <div className="stack" style={{ maxWidth: 720 }}>
      {error && <p className="mensaje-error">{error}</p>}

      <p className="section-subtitle" style={{ margin: 0 }}>
        Cada descarga relee tu bandeja real de {cuentaActiva.direccion} en el momento -puede tardar
        varios segundos con muchos comprobantes.
      </p>

      <div className="grid grid-3">
        {FORMATOS.map((f) => {
          const Icono = f.icono;
          const activo = descargando === f.id;
          return (
            <div key={f.id} className="card stack" style={{ alignItems: "flex-start" }}>
              <Icono size={22} color="var(--color-accent-200)" />
              <div className="section-title">{f.etiqueta}</div>
              <p className="section-subtitle" style={{ margin: 0 }}>{f.descripcion}</p>
              <button
                className="btn btn-primary"
                style={{ marginTop: 6 }}
                onClick={() => descargar(f.id)}
                disabled={descargando !== null}
              >
                {activo ? "Generando…" : `Descargar ${f.etiqueta}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
