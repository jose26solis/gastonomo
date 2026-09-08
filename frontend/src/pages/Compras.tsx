import { Clock, ListDashes, ReceiptX, WarningCircle } from "@phosphor-icons/react";
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

  async function desglosar(
    compra: Compra,
    lineas: Array<{
      descripcion: string;
      cantidad: string;
      precioUnitario: string;
      categoriaId?: number;
    }>,
  ) {
    const actualizada = await api.desglosarCompra(usuarioId, compra.id, lineas);
    setCompras((actual) => {
      if (!actual) return actual;
      if (filtro === "pendientes" && !actualizada.requiere_revision) {
        return actual.filter((c) => c.id !== compra.id);
      }
      return actual.map((c) => (c.id === compra.id ? actualizada : c));
    });
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
            onDesglosar={desglosar}
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
  onDesglosar,
  onVerBitacora,
}: {
  compra: Compra;
  metodosPago: MetodoPago[];
  categorias: Categoria[];
  onResolver: (compra: Compra, metodoPagoId?: number, categoriaId?: number) => void;
  onDesglosar: (
    compra: Compra,
    lineas: Array<{
      descripcion: string;
      cantidad: string;
      precioUnitario: string;
      categoriaId?: number;
    }>,
  ) => Promise<void>;
  onVerBitacora: () => void;
}) {
  const [metodoElegido, setMetodoElegido] = useState("");
  const [categoriaElegida, setCategoriaElegida] = useState("");
  const [desglosando, setDesglosando] = useState(false);
  const faltaMetodo = compra.metodo_pago_id === null;
  // Con más de un renglón, "elegir una categoría" ya no tiene un único
  // destino claro -eso es trabajo de "Desglosar" (corrige renglón por
  // renglón), no de este corrector rápido pensado para un único renglón.
  const faltaCategoria = compra.categoria_id === null && compra.lineas.length <= 1;

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
          onClick={() => setDesglosando((actual) => !actual)}
          title="Partir esta compra en varios renglones, cada uno con su propia categoría"
          aria-label={`Desglosar ${compra.comercio_nombre}`}
          style={{ padding: 5 }}
        >
          <ListDashes size={12} />
        </button>
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

      {desglosando && (
        <PanelDesglose
          compra={compra}
          categorias={categorias}
          onGuardar={async (lineas) => {
            await onDesglosar(compra, lineas);
            setDesglosando(false);
          }}
          onCancelar={() => setDesglosando(false)}
        />
      )}
    </div>
  );
}

interface FilaDesglose {
  descripcion: string;
  monto: string;
  categoriaId: string;
}

function lineasIniciales(compra: Compra): FilaDesglose[] {
  // Con un único renglón (el caso de siempre, recién ingerido por correo),
  // arranca con ese renglón más uno vacío -invita a partirlo en vez de
  // mostrar un formulario en blanco. Con varios (ya desglosada antes), edita
  // los que ya hay.
  if (compra.lineas.length <= 1) {
    const unica = compra.lineas[0];
    return [
      {
        descripcion: unica?.descripcion ?? compra.comercio_nombre,
        monto: unica?.subtotal ?? compra.total,
        categoriaId: unica?.categoria_id ? String(unica.categoria_id) : "",
      },
      { descripcion: "", monto: "", categoriaId: "" },
    ];
  }
  return compra.lineas.map((linea) => ({
    descripcion: linea.descripcion,
    monto: linea.subtotal,
    categoriaId: linea.categoria_id ? String(linea.categoria_id) : "",
  }));
}

/**
 * "Partir un cargo" en varios renglones, cada uno con su propia categoría.
 *
 * La suma de los renglones tiene que calzar exacto con el total de la
 * compra -desglosar reparte cuánto costó, nunca lo cambia (ver
 * `ConciliacionService.desglosar_compra` en el backend, que es quien de
 * verdad valida esto). Acá solo se avisa mientras se edita, para que no
 * haga falta mandar la petición para descubrir que no calza.
 */
function PanelDesglose({
  compra,
  categorias,
  onGuardar,
  onCancelar,
}: {
  compra: Compra;
  categorias: Categoria[];
  onGuardar: (
    lineas: Array<{
      descripcion: string;
      cantidad: string;
      precioUnitario: string;
      categoriaId?: number;
    }>,
  ) => Promise<void>;
  onCancelar: () => void;
}) {
  const [filas, setFilas] = useState<FilaDesglose[]>(() => lineasIniciales(compra));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filasCompletas = filas.filter((f) => f.descripcion.trim() !== "" && f.monto !== "");
  const suma = filasCompletas.reduce((acumulado, f) => acumulado + (Number(f.monto) || 0), 0);
  const total = Number(compra.total);
  // Comparación con tolerancia de un centavo: sumar strings decimales en
  // punto flotante puede arrastrar un error minúsculo que un usuario real
  // nunca metería a mano -el backend igual valida exacto con Decimal.
  const sumaCalza = filasCompletas.length > 0 && Math.abs(suma - total) < 0.005;

  function actualizarFila(indice: number, cambios: Partial<FilaDesglose>) {
    setFilas((actual) => actual.map((f, i) => (i === indice ? { ...f, ...cambios } : f)));
  }

  async function guardar() {
    setError(null);
    setGuardando(true);
    try {
      await onGuardar(
        filasCompletas.map((f) => ({
          descripcion: f.descripcion.trim(),
          cantidad: "1",
          precioUnitario: f.monto,
          categoriaId: f.categoriaId ? Number(f.categoriaId) : undefined,
        })),
      );
    } catch (e) {
      setError(e instanceof ErrorDeApiError ? e.message : "Ocurrió un error inesperado.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div
      className="stack"
      style={{ gap: 8, borderTop: "1px solid var(--color-surface-2)", paddingTop: 11 }}
    >
      {filas.map((fila, indice) => (
        <div
          key={indice}
          style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}
        >
          <input
            value={fila.descripcion}
            onChange={(e) => actualizarFila(indice, { descripcion: e.target.value })}
            placeholder="Descripción"
            style={{ ...ESTILO_SELECT, flex: 2, minWidth: 120 }}
          />
          <input
            value={fila.monto}
            onChange={(e) => actualizarFila(indice, { monto: e.target.value })}
            placeholder="Monto"
            inputMode="decimal"
            style={{ ...ESTILO_SELECT, flex: 1, minWidth: 90 }}
          />
          <select
            value={fila.categoriaId}
            onChange={(e) => actualizarFila(indice, { categoriaId: e.target.value })}
            style={ESTILO_SELECT}
          >
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
          <button
            className="btn btn-sm"
            onClick={() => setFilas((actual) => actual.filter((_, i) => i !== indice))}
            disabled={filas.length <= 1}
            aria-label="Quitar este renglón"
            style={{ padding: 5 }}
          >
            ×
          </button>
        </div>
      ))}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <button
          className="btn btn-sm"
          type="button"
          onClick={() =>
            setFilas((actual) => [...actual, { descripcion: "", monto: "", categoriaId: "" }])
          }
        >
          + Agregar renglón
        </button>
        <span
          style={{
            fontSize: 11,
            color: sumaCalza ? "var(--color-text-dim)" : "#e8a33d",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          Suma: {formatearMonto(suma, compra.moneda)} / {formatearMonto(total, compra.moneda)}
        </span>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn btn-sm btn-primary"
          disabled={!sumaCalza || guardando}
          onClick={guardar}
        >
          {guardando ? "Guardando…" : "Guardar desglose"}
        </button>
        <button className="btn btn-sm" type="button" onClick={onCancelar} disabled={guardando}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
