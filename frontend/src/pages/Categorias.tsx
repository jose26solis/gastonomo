import { ForkKnife, GasPump, Lightning, ShoppingCart, Sparkle, Car as Taxi, TShirt } from "@phosphor-icons/react";
import { MuestraBadge } from "../components/MuestraBadge";

const CATEGORIAS = [
  { nombre: "Alimentación", icono: ForkKnife, monto: 234_400, movimientos: 22, color: "#b5abfc" },
  { nombre: "Supermercado", icono: ShoppingCart, monto: 198_900, movimientos: 9, color: "#968ae0" },
  { nombre: "Gasolina", icono: GasPump, monto: 142_000, movimientos: 6, color: "#796cbf" },
  { nombre: "Servicios", icono: Lightning, monto: 96_500, movimientos: 4, color: "#5d5294" },
  { nombre: "Transporte", icono: Taxi, monto: 71_300, movimientos: 11, color: "#423a6a" },
  { nombre: "Ropa", icono: TShirt, monto: 43_200, movimientos: 2, color: "#7972a9" },
];

const PENDIENTES = [
  {
    comercio: "PALI SANTA ANA",
    fecha: "17 ago",
    monto: "₡18,400",
    sugerencia: "Supermercado",
    confianza: 0.61,
    razon: "El correo llegó sin detalle de línea; se clasificó por el nombre del comercio.",
  },
  {
    comercio: "AUTOSTAR REPUESTOS",
    fecha: "15 ago",
    monto: "₡76,900",
    sugerencia: "Transporte",
    confianza: 0.54,
    razon: "Podría ser mantenimiento del vehículo o una compra puntual de repuestos.",
  },
];

const totalCategorias = CATEGORIAS.reduce((suma, c) => suma + c.monto, 0);
const maximo = CATEGORIAS[0].monto;

export function Categorias() {
  return (
    <div className="stack">
      <MuestraBadge>
        Datos de ejemplo — falta modelar la clasificación automática por categoría; hoy
        Gastonomo lee comprobantes de BAC pero todavía no les asigna una `Categoria` del dominio.
      </MuestraBadge>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="section-title">Categorías detectadas</div>
          <div className="section-subtitle">El modelo leería el comercio y el monto del comprobante</div>
          <div className="stack" style={{ gap: 14, marginTop: 17 }}>
            {CATEGORIAS.map((c) => {
              const Icono = c.icono;
              return (
                <div key={c.nombre} className="stack" style={{ gap: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                    <Icono size={14} color="var(--color-accent-400)" />
                    <span style={{ flex: 1, color: "var(--color-text-bright-muted)" }}>{c.nombre}</span>
                    <span style={{ color: "var(--color-text-dim)", fontSize: 10.5 }}>{c.movimientos} mov.</span>
                    <span style={{ fontVariantNumeric: "tabular-nums" }}>₡{c.monto.toLocaleString("en-US")}</span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ background: c.color, width: `${Math.round((c.monto / maximo) * 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 14, fontSize: 11, color: "var(--color-text-dim)" }}>
            Total del mes de muestra: ₡{totalCategorias.toLocaleString("en-US")}
          </div>
        </section>

        <section className="card" style={{ borderColor: "var(--color-border-accent)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Sparkle size={15} color="var(--color-accent-200)" />
            <div className="section-title">Por confirmar</div>
            <span style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--color-text-dim)" }}>
              {PENDIENTES.length} pendientes
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginTop: 6, lineHeight: 1.6 }}>
            Movimientos donde la clasificación quedaría por debajo del umbral de confianza.
          </div>
          <div className="stack" style={{ marginTop: 17 }}>
            {PENDIENTES.map((p) => (
              <div key={p.comercio} className="card stack" style={{ gap: 8 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span style={{ fontSize: 12.5 }}>{p.comercio}</span>
                  <span style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>{p.fecha}</span>
                  <span style={{ marginLeft: "auto", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{p.monto}</span>
                </div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.5 }}>{p.razon}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span className="tag">{p.sugerencia}</span>
                  <span style={{ fontSize: 10, color: "var(--color-text-dim)" }}>
                    {Math.round(p.confianza * 100)}% de confianza
                  </span>
                  <button className="btn btn-sm btn-primary" style={{ marginLeft: "auto" }} disabled>
                    Confirmar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
