import { Sparkle } from "@phosphor-icons/react";

/**
 * Marca visible en cualquier pantalla que todavía no tiene datos reales.
 *
 * El backend hoy solo sabe leer y sumar comprobantes de BAC (Resumen) y
 * vincular buzones (Conectar correo). El resto de esta maqueta -presupuestos,
 * bancos, categorías, reportes- no tiene ninguna entidad ni proceso real
 * detrás todavía, así que se muestra con datos de ejemplo y esta insignia,
 * en vez de simular que ya funciona.
 */
export function MuestraBadge({ children }: { children?: React.ReactNode }) {
  return (
    <div className="badge-muestra">
      <Sparkle size={14} weight="fill" />
      <span>
        {children ?? "Datos de ejemplo — esta pantalla todavía no tiene backend real conectado"}
      </span>
    </div>
  );
}
