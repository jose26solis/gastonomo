import { Clock, ReceiptX, WarningCircle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { PanelBitacora } from "../components/PanelBitacora";
import { formatearFechaCorta, formatearMonto } from "../lib/formato";
import type { Categoria, Compra, MetodoPago } from "../types";

const ESTILO_SELECT = {
  padding: "6px 8px",
  background: "var(--color-surface-2)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  color: "var(--color-text)",
  fontSize: 11.5,
};

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

/**
 * La lista de `Compra` reales, de primera clase -antes de esta pantalla solo
 * se podían ver indirectamente, a través de los campos planos de
 * `Comprobante` o de los eventos sueltos de su bitácora. Acá también se
 * hace visible (y corregible) `requiere_revision`: una compra que la
 * ingesta no pudo emparejar del todo sola, y que hasta ahora no tenía
 * ningún indicio en pantalla ni forma de resolverse.
 */
export function Compras({ usuarioId }: { usuarioId: number }) {
  const [filtro, setFiltro] = useState<"pendientes" | "todas">("pendientes");
  const [compras, setCompras] = useState<Compra[] | null>(null);
  const [metodosPago, setMetodosPago] = useState<MetodoPago[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [bitacoraAbierta, setBitacoraAbierta] = useState<{ compraId: number; titulo: string } | null>(
    null,
  );

  useEffect(() => {
    api
      .listarMetodosPago(usuarioId)
      .then((m) => setMetodosPago(m.filter((x) => x.activo)))
      .catch((e: unknown) => setError(mensajeDeError(e)));
    api
      .listarCategorias(usuarioId)
      .then(setCategorias)
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [usuarioId]);

  useEffect(() => {
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar compras del otro
    // filtro mientras el fetch está en curso.
    // oxlint-disable-next-line react/set-state-in-effect
    setCompras(null);
    api
      .listarCompras(usuarioId, { requiereRevision: filtro === "pendientes" ? true : undefined })
      .then((c) => {
        if (!cancelado) setCompras(c);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, filtro]);

  async function resolver(compra: Compra, metodoPagoId?: number, categoriaId?: number) {
    try {
      const actualizada = await api.resolverRevisionCompra(usuarioId, compra.id, {
        metodoPagoId,
        categoriaId,
      });
      setCompras((actual) => {
        if (!actual) return actual;
        // En "Pendientes de revisión", una que se resolvió del todo sale de la lista.
        if (filtro === "pendientes" && !actualizada.requiere_revision) {
          return actual.filter((c) => c.id !== compra.id);
        }
        return actual.map((c) => (c.id === compra.id ? actualizada : c));
      });
    } catch (e) {
      setError(mensajeDeError(e));
    }
  }

  const hojas = categorias.filter((c) => c.es_hoja && c.activa);

  return (
    <div className="stack">
      <div className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontSize: 11.5, color: "var(--color-text-dim)" }}>Mostrar</span>
        <select
          value={filtro}
          onChange={(e) => setFiltro(e.target.value as "pendientes" | "todas")}
          style={ESTILO_SELECT}
        >
          <option value="pendientes">Pendientes de revisión</option>
          <option value="todas">Todas</option>
        </select>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      <div className="stack" style={{ gap: 8 }}>
        {compras === null && <p className="vacio">Cargando…</p>}
        {compras !== null && compras.length === 0 && filtro === "pendientes" && (
          <p className="vacio">Ninguna compra necesita revisión -todas quedaron con método de pago y categoría.</p>
        )}
        {compras !== null && compras.length === 0 && filtro === "todas" && (
          <p className="vacio">Todavía no hay ninguna compra real conciliada.</p>
        )}
        {compras?.map((compra) => (
          <FilaCompra
            key={compra.id}
            compra={compra}
            metodosPago={metodosPago}
            categorias={hojas}
            onResolver={resolver}
            onVerBitacora={() =>
              setBitacoraAbierta({
                compraId: compra.id,
                titulo: `${compra.comercio_nombre} · ${formatearMonto(-Number(compra.total), compra.moneda)}`,
              })
            }
          />
        ))}
      </div>

      {bitacoraAbierta && (
        <PanelBitacora
          usuarioId={usuarioId}
          compraId={bitacoraAbierta.compraId}
          titulo={bitacoraAbierta.titulo}
          onCerrar={() => setBitacoraAbierta(null)}
        />
      )}
    </div>
  );
}

function FilaCompra({
  compra,
  metodosPago,
  categorias,
  onResolver,
  onVerBitacora,
}: {
  compra: Compra;
  metodosPago: MetodoPago[];
  categorias: Categoria[];
  onResolver: (compra: Compra, metodoPagoId?: number, categoriaId?: number) => void;
  onVerBitacora: () => void;
}) {
  const [metodoElegido, setMetodoElegido] = useState("");
  const [categoriaElegida, setCategoriaElegida] = useState("");
  const faltaMetodo = compra.metodo_pago_id === null;
  const faltaCategoria = compra.categoria_id === null;

  return (
    <div className="card stack" style={{ gap: 11 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <span
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: "var(--color-surface-2)",
            display: "grid",
            placeItems: "center",
            color: compra.requiere_revision ? "#e8a33d" : "var(--color-accent-200)",
            flexShrink: 0,
          }}
        >
          {compra.requiere_revision ? <WarningCircle size={15} weight="fill" /> : <ReceiptX size={15} />}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12.5 }}>{compra.comercio_nombre}</div>
          <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
            {formatearFechaCorta(compra.fecha)}
            {" · "}
            {compra.metodo_pago_alias ?? "Sin método de pago"}
            {" · "}
            {compra.categoria_nombre ?? "Sin categoría"}
          </div>
        </div>
        <span style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
          {formatearMonto(-Number(compra.total), compra.moneda)}
        </span>
        <button
          className="btn btn-sm"
          onClick={onVerBitacora}
          title="Ver de dónde salió este movimiento"
          aria-label={`Ver bitácora de ${compra.comercio_nombre}`}
          style={{ padding: 5 }}
        >
          <Clock size={12} />
        </button>
      </div>

      {(faltaMetodo || faltaCategoria) && (
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            alignItems: "center",
            borderTop: "1px solid var(--color-surface-2)",
            paddingTop: 11,
          }}
        >
          {faltaMetodo && (
            <select
              value={metodoElegido}
              onChange={(e) => setMetodoElegido(e.target.value)}
              style={ESTILO_SELECT}
            >
              <option value="">Elegir método de pago…</option>
              {metodosPago.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.alias}
                </option>
              ))}
            </select>
          )}
          {faltaCategoria && (
            <select
              value={categoriaElegida}
              onChange={(e) => setCategoriaElegida(e.target.value)}
              style={ESTILO_SELECT}
            >
              <option value="">Elegir categoría…</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn btn-sm btn-primary"
            disabled={!metodoElegido && !categoriaElegida}
            onClick={() => {
              onResolver(
                compra,
                metodoElegido ? Number(metodoElegido) : undefined,
                categoriaElegida ? Number(categoriaElegida) : undefined,
              );
              setMetodoElegido("");
              setCategoriaElegida("");
            }}
          >
            Corregir
          </button>
        </div>
      )}
    </div>
  );
}
