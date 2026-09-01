import {
  Car as CarIcon,
  ForkKnife,
  GasPump,
  Lightning,
  Repeat,
  ShoppingCart,
  TrendUp,
  WarningCircle,
} from "@phosphor-icons/react";
import { MuestraBadge } from "../components/MuestraBadge";

const PRESUPUESTOS = [
  { nombre: "Alimentación", icono: ForkKnife, gastado: 234_400, limite: 220_000 },
  { nombre: "Supermercado", icono: ShoppingCart, gastado: 198_900, limite: 250_000 },
  { nombre: "Gasolina", icono: GasPump, gastado: 142_000, limite: 150_000 },
  { nombre: "Servicios", icono: Lightning, gastado: 96_500, limite: 130_000 },
  { nombre: "Transporte", icono: CarIcon, gastado: 71_300, limite: 100_000 },
].map((p) => {
  const pct = (p.gastado / p.limite) * 100;
  const excedido = pct > 100;
  const cerca = pct >= 80;
  return { ...p, pct, excedido, cerca };
});

const ALERTAS = [
  {
    icono: WarningCircle,
    color: "var(--color-accent-100)",
    titulo: "Alimentación superó el presupuesto",
    cuerpo: "₡234,400 de ₡220,000. Dos compras grandes esta semana explican la mayoría.",
    cuando: "hoy",
  },
  {
    icono: TrendUp,
    color: "var(--color-accent-200)",
    titulo: "Gasolina llegó al 95% del límite",
    cuerpo: "Una carga más de tamaño similar cruza el tope del mes.",
    cuando: "ayer",
  },
  {
    icono: Repeat,
    color: "var(--color-text-muted)",
    titulo: "Regla aprendida",
    cuerpo: "Los cargos de Servicentro se clasificarían como Gasolina sin confirmación.",
    cuando: "hace 3 días",
  },
];

export function Presupuestos() {
  return (
    <div className="stack">
      <MuestraBadge>
        Datos de ejemplo — falta la entidad `Presupuesto` del dominio y el proceso que compara el
        gasto acumulado contra un límite mensual.
      </MuestraBadge>

      <div className="grid grid-3">
        {PRESUPUESTOS.map((p) => {
          const Icono = p.icono;
          return (
            <div
              key={p.nombre}
              className="card stack"
              style={{ borderColor: p.excedido ? "var(--color-accent-500)" : "var(--color-border)" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <Icono size={14} color="var(--color-accent-400)" />
                <span style={{ fontSize: 12.5, flex: 1 }}>{p.nombre}</span>
                <span
                  style={{
                    fontSize: 10.5,
                    color: p.excedido ? "var(--color-accent-100)" : p.cerca ? "var(--color-accent-200)" : "var(--color-text-dim)",
                  }}
                >
                  {p.excedido ? "Excedido" : p.cerca ? "Cerca del límite" : "En rango"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontSize: 20, fontWeight: 500 }}>₡{p.gastado.toLocaleString("en-US")}</span>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>de ₡{p.limite.toLocaleString("en-US")}</span>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${Math.min(p.pct, 100).toFixed(0)}%`,
                    background: p.excedido ? "var(--color-accent-200)" : p.cerca ? "var(--color-accent-300)" : "var(--color-accent-500)",
                  }}
                />
              </div>
              <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                {p.excedido
                  ? `₡${(p.gastado - p.limite).toLocaleString("en-US")} sobre el límite`
                  : `₡${(p.limite - p.gastado).toLocaleString("en-US")} disponibles · ${Math.round(p.pct)}% usado`}
              </div>
            </div>
          );
        })}
      </div>

      <section className="card">
        <div className="section-title">Alertas</div>
        <div className="stack" style={{ gap: 3, marginTop: 11 }}>
          {ALERTAS.map((a) => {
            const Icono = a.icono;
            return (
              <div
                key={a.titulo}
                style={{ display: "flex", alignItems: "flex-start", gap: 11, padding: "11px 0", borderTop: "1px solid var(--color-surface-2)" }}
              >
                <Icono size={15} color={a.color} style={{ marginTop: 1 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5 }}>{a.titulo}</div>
                  <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginTop: 3, lineHeight: 1.5 }}>{a.cuerpo}</div>
                </div>
                <div style={{ fontSize: 10.5, color: "var(--color-text-dimmer)" }}>{a.cuando}</div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
