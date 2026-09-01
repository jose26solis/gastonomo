import { useState } from "react";
import { MuestraBadge } from "../components/MuestraBadge";

const AJUSTES_DEF = [
  { clave: "autoCat", titulo: "Clasificar con IA al recibir", cuerpo: "Cada comprobante nuevo se categorizaría al llegar, sin esperar una sincronización manual." },
  { clave: "alertas", titulo: "Alertas de presupuesto", cuerpo: "Aviso cuando una categoría cruza el umbral configurado." },
  { clave: "sinpe", titulo: "Leer transferencias SINPE", cuerpo: "Incluir transferencias móviles aunque no traigan el formato de compra que ya se reconoce." },
  { clave: "ocultar", titulo: "Ocultar montos al compartir pantalla", cuerpo: "Reemplaza las cifras por puntos mientras la ventana no está enfocada." },
] as const;

export function Ajustes() {
  const [valores, setValores] = useState<Record<string, boolean>>({
    autoCat: false,
    alertas: true,
    sinpe: false,
    ocultar: false,
  });

  return (
    <div className="stack" style={{ maxWidth: 640 }}>
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
