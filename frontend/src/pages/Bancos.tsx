import { MuestraBadge } from "../components/MuestraBadge";

const BANCOS = [
  {
    abrev: "BAC",
    nombre: "BAC Credomatic",
    remitente: "notificaciones@baccredomatic.cr",
    vistoHace: "hoy",
    cuentas: [
      { nombre: "Tarjeta AMEX", mascara: "••8356", monto: "−₡186,400.00" },
      { nombre: "Cuenta corriente", mascara: "••1120", monto: "₡0.00" },
    ],
  },
  {
    abrev: "BNCR",
    nombre: "Banco Nacional de Costa Rica",
    remitente: "avisos@bncr.fi.cr",
    vistoHace: "sin conectar",
    cuentas: [{ nombre: "Cuenta de ahorro", mascara: "••9021", monto: "₡0.00" }],
  },
];

export function Bancos() {
  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      <MuestraBadge>
        Datos de ejemplo — solo BAC está conectado de verdad. El resto de bancos, y el saldo por
        cuenta, necesitan sus propios parsers y la entidad `MetodoPago` del dominio.
      </MuestraBadge>

      {BANCOS.map((b) => (
        <section key={b.abrev} className="card stack">
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
                fontSize: 11,
                fontWeight: 500,
              }}
            >
              {b.abrev}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{b.nombre}</div>
              <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>{b.remitente}</div>
            </div>
            <span style={{ fontSize: 10.5, color: "var(--color-text-muted)" }}>{b.vistoHace}</span>
          </div>
          <div className="grid grid-3">
            {b.cuentas.map((c) => (
              <div key={c.nombre} style={{ border: "1px solid var(--color-surface-2)", borderRadius: 8, padding: 11 }}>
                <div style={{ fontSize: 11.5, color: "var(--color-text-bright-muted)" }}>{c.nombre}</div>
                <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 3 }}>{c.mascara}</div>
                <div style={{ fontSize: 14, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>{c.monto}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
