import { CheckSquare, Square } from "@phosphor-icons/react";
import { useState } from "react";
import { MuestraBadge } from "../components/MuestraBadge";

const BLOQUES: Record<string, string> = {
  resumen: "Resumen ejecutivo",
  categorias: "Desglose por categoría",
  comercios: "Top comercios",
  presupuestos: "Cumplimiento de presupuesto",
  movimientos: "Detalle de movimientos",
};

const CATEGORIAS_MUESTRA = [
  { nombre: "Alimentación", color: "#b5abfc", pct: "31%", monto: "₡234,400" },
  { nombre: "Supermercado", color: "#968ae0", pct: "26%", monto: "₡198,900" },
  { nombre: "Gasolina", color: "#796cbf", pct: "19%", monto: "₡142,000" },
  { nombre: "Servicios", color: "#5d5294", pct: "13%", monto: "₡96,500" },
  { nombre: "Transporte", color: "#423a6a", pct: "9%", monto: "₡71,300" },
];

export function Reportes() {
  const [bloques, setBloques] = useState<Record<string, boolean>>({
    resumen: true,
    categorias: true,
    comercios: true,
    presupuestos: true,
    movimientos: false,
  });
  const [formato, setFormato] = useState("PDF");
  const [generado, setGenerado] = useState(false);

  return (
    <div className="stack">
      <MuestraBadge>
        Datos de ejemplo — la exportación a PDF/CSV/Excel todavía no está implementada; esta
        pantalla muestra cómo se armaría un reporte, no genera un archivo real todavía.
      </MuestraBadge>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 17, alignItems: "start" }}>
        <section className="card stack">
          <div className="section-title">Armar reporte</div>
          <div className="stack" style={{ gap: 7 }}>
            {Object.entries(BLOQUES).map(([clave, etiqueta]) => {
              const activo = bloques[clave];
              const Icono = activo ? CheckSquare : Square;
              return (
                <button
                  key={clave}
                  onClick={() => {
                    setBloques((b) => ({ ...b, [clave]: !b[clave] }));
                    setGenerado(false);
                  }}
                  className="btn"
                  style={{
                    justifyContent: "flex-start",
                    borderColor: activo ? "var(--color-accent-500)" : "var(--color-border)",
                    color: activo ? "var(--color-accent-100)" : "var(--color-text-muted)",
                  }}
                >
                  <Icono size={14} weight={activo ? "fill" : "regular"} />
                  {etiqueta}
                </button>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 7 }}>
            {["PDF", "CSV", "Excel"].map((f) => (
              <button
                key={f}
                onClick={() => {
                  setFormato(f);
                  setGenerado(false);
                }}
                className="btn btn-sm"
                style={{ flex: 1, justifyContent: "center", borderColor: formato === f ? "var(--color-accent-500)" : "var(--color-border)" }}
              >
                {f}
              </button>
            ))}
          </div>
          <button className="btn btn-primary" onClick={() => setGenerado(true)}>
            {generado ? `Listo · ${formato} generado` : `Generar ${formato}`}
          </button>
        </section>

        <section
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            background: "var(--color-surface-2)",
            padding: 28,
            minHeight: 440,
          }}
        >
          <div
            style={{
              maxWidth: 560,
              margin: "0 auto",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: 28,
              display: "flex",
              flexDirection: "column",
              gap: 17,
            }}
          >
            <div>
              <div className="kicker">Reporte de gastos</div>
              <div style={{ fontSize: 20, fontWeight: 500, marginTop: 6 }}>Agosto 2026</div>
              <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginTop: 6 }}>1 banco · datos de ejemplo</div>
            </div>
            <div style={{ height: 1, background: "linear-gradient(90deg, transparent, #3f424d 20%, #3f424d 80%, transparent)" }} />
            <div className="grid grid-3">
              <div>
                <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>Gasto total</div>
                <div style={{ fontSize: 17, fontWeight: 500, marginTop: 3 }}>₡743,100</div>
              </div>
              <div>
                <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>Categorías</div>
                <div style={{ fontSize: 17, fontWeight: 500, marginTop: 3 }}>5</div>
              </div>
              <div>
                <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>Sobre presupuesto</div>
                <div style={{ fontSize: 17, fontWeight: 500, marginTop: 3 }}>1</div>
              </div>
            </div>
            {bloques.categorias && (
              <div className="stack" style={{ gap: 8 }}>
                {CATEGORIAS_MUESTRA.map((c) => (
                  <div key={c.nombre} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color }} />
                    <span style={{ flex: 1, color: "var(--color-text-bright-muted)" }}>{c.nombre}</span>
                    <span style={{ color: "var(--color-text-dim)" }}>{c.pct}</span>
                    <span style={{ fontVariantNumeric: "tabular-nums", width: 80, textAlign: "right" }}>{c.monto}</span>
                  </div>
                ))}
              </div>
            )}
            <div style={{ fontSize: 10.5, color: "var(--color-text-dimmer)", lineHeight: 1.6 }}>
              Vista previa de ejemplo. El reporte real se armaría desde los comprobantes leídos de
              Gmail y Outlook.
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
