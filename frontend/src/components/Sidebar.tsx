import {
  ArrowsLeftRight,
  Bank,
  ChartDonut,
  EnvelopeSimple,
  FileText,
  Gauge,
  SlidersHorizontal,
  Sparkle,
  SquaresFour,
} from "@phosphor-icons/react";

export type Pantalla =
  | "resumen"
  | "categorias"
  | "presupuestos"
  | "reportes"
  | "conectar"
  | "bancos"
  | "sinpe"
  | "ajustes";

const NAV: { id: Pantalla; label: string; icon: React.ElementType }[] = [
  { id: "resumen", label: "Resumen", icon: SquaresFour },
  { id: "categorias", label: "Categorías", icon: Sparkle },
  { id: "presupuestos", label: "Presupuestos", icon: Gauge },
  { id: "reportes", label: "Reportes", icon: FileText },
  { id: "conectar", label: "Conectar correo", icon: EnvelopeSimple },
  { id: "bancos", label: "Bancos", icon: Bank },
  { id: "sinpe", label: "SINPE", icon: ArrowsLeftRight },
  { id: "ajustes", label: "Ajustes", icon: SlidersHorizontal },
];

export function Sidebar({
  pantalla,
  onNavegar,
  lineaEstado,
  sincronizando,
  abierto,
  onCerrar,
}: {
  pantalla: Pantalla;
  onNavegar: (p: Pantalla) => void;
  lineaEstado: string;
  sincronizando: boolean;
  /** En pantallas angostas el sidebar es un cajón deslizable, no una columna
   * fija -no hay espacio para 224px fijos en un teléfono. `abierto` controla
   * si está desplegado; en pantallas anchas este valor no importa, el CSS lo
   * ignora (ver `.sidebar` en index.css). */
  abierto: boolean;
  onCerrar: () => void;
}) {
  function navegarYCerrar(p: Pantalla) {
    onNavegar(p);
    onCerrar();
  }

  return (
    <>
      {/* Solo se ve (y solo existe como capa clicable) en pantallas angostas
          con el cajón abierto -es lo que permite cerrarlo tocando afuera. */}
      <div
        className={`sidebar-backdrop${abierto ? " visible" : ""}`}
        onClick={onCerrar}
        aria-hidden="true"
      />
      <aside className={`sidebar${abierto ? " abierto" : ""}`}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 8px" }}>
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: 8,
            border: "1px solid var(--color-accent-400)",
            display: "grid",
            placeItems: "center",
            color: "var(--color-accent-200)",
          }}
        >
          <ChartDonut size={15} weight="fill" />
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, letterSpacing: "-0.01em" }}>Gastonomo</div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {NAV.map((item) => {
          const activo = pantalla === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => navegarYCerrar(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                textAlign: "left",
                padding: "8px 8px",
                borderRadius: 8,
                border: "none",
                cursor: "pointer",
                fontSize: 12.5,
                background: activo ? "var(--color-accent-700)" : "transparent",
                color: activo ? "var(--color-accent-100)" : "var(--color-text-muted)",
              }}
            >
              <Icon size={15} weight={activo ? "fill" : "regular"} style={{ opacity: 0.9 }} />
              <span style={{ flex: 1 }}>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 11 }}>
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            padding: 11,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              color: "var(--color-text-muted)",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--color-accent-300)",
                animation: sincronizando ? "pulse 2s infinite" : "none",
                opacity: sincronizando ? 1 : 0.5,
              }}
            />
            {sincronizando ? "Sincronización activa" : "Sin sincronizar"}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-dim)", lineHeight: 1.5 }}>
            {lineaEstado}
          </div>
        </div>
      </div>
      </aside>
    </>
  );
}
