/**
 * Layout compartido por las páginas legales (Política de privacidad,
 * Términos de uso). Viven fuera del login a propósito -sin sesión, sin
 * `AppShell`- porque tienen que ser accesibles sin cuenta: es lo que exige
 * la verificación de apps de Google, y lo que necesitan Apple/Google para
 * revisar la ficha en sus tiendas.
 */
export function LegalLayout({
  titulo,
  actualizado,
  children,
}: {
  titulo: string;
  actualizado: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        padding: "48px 20px 80px",
      }}
    >
      <div style={{ maxWidth: 680, width: "100%" }}>
        <a
          href="/"
          style={{
            fontSize: 11.5,
            color: "var(--color-accent-200)",
            textDecoration: "none",
          }}
        >
          ← Volver a Gastonomo
        </a>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginTop: 17, marginBottom: 3 }}>{titulo}</h1>
        <p style={{ fontSize: 11.5, color: "var(--color-text-dim)", marginBottom: 28 }}>
          Última actualización: {actualizado}
        </p>
        <div
          className="stack"
          style={{ gap: 22, fontSize: 13, lineHeight: 1.7, color: "var(--color-text-bright-muted)" }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

export function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 8, color: "var(--color-text)" }}>
        {titulo}
      </h2>
      <div className="stack" style={{ gap: 10 }}>
        {children}
      </div>
    </section>
  );
}
