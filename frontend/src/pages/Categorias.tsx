import { EnvelopeSimple, Plus, Sparkle } from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearMonto } from "../lib/formato";
import { useCuentaActiva } from "../lib/useCuentaActiva";
import type { Categoria, ComercioClasificado } from "../types";

const PALETA = ["#2563EB", "#16A34A", "#D97706", "#DC2626", "#7C3AED", "#0891B2", "#DB2777"];

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

export function Categorias({ usuarioId, onIrAConectar }: { usuarioId: number; onIrAConectar: () => void }) {
  const { cargando: cargandoCuenta, cuentaActiva, error: errorCuenta } = useCuentaActiva(usuarioId);
  const [categorias, setCategorias] = useState<Categoria[] | null>(null);
  const [comercios, setComercios] = useState<ComercioClasificado[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nuevaCategoria, setNuevaCategoria] = useState("");
  const [creandoCategoria, setCreandoCategoria] = useState(false);
  const [asignando, setAsignando] = useState<number | null>(null);

  useEffect(() => {
    api
      .listarCategorias(usuarioId)
      .then(setCategorias)
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [usuarioId]);

  useEffect(() => {
    if (!cuentaActiva) return;
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar comercios
    // obsoletos mientras el fetch para la nueva cuenta está en curso.
    // oxlint-disable-next-line react/set-state-in-effect
    setComercios(null);
    api
      .listarComercios(usuarioId, cuentaActiva.id)
      .then((c) => {
        if (!cancelado) setComercios(c);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, cuentaActiva]);

  async function crearCategoria() {
    const nombre = nuevaCategoria.trim();
    if (!nombre || !categorias) return;
    setCreandoCategoria(true);
    try {
      const color = PALETA[categorias.length % PALETA.length];
      const categoria = await api.crearCategoria(usuarioId, nombre, color);
      setCategorias([...categorias, categoria]);
      setNuevaCategoria("");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCreandoCategoria(false);
    }
  }

  async function confirmarCategoria(comercio: ComercioClasificado, categoriaId: number) {
    setAsignando(comercio.comercio_id);
    try {
      await api.asignarCategoriaComercio(usuarioId, comercio.comercio_id, categoriaId);
      const categoria = categorias?.find((c) => c.id === categoriaId);
      setComercios(
        (actual) =>
          actual?.map((c) =>
            c.comercio_id === comercio.comercio_id
              ? { ...c, categoria_id: categoriaId, categoria_nombre: categoria?.nombre ?? null }
              : c,
          ) ?? null,
      );
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setAsignando(null);
    }
  }

  const { porCategoria, pendientes } = useMemo(() => {
    if (!comercios) return { porCategoria: [], pendientes: [] };
    const acumulado = new Map<string, { nombre: string; total: number; movimientos: number }>();
    const pend: ComercioClasificado[] = [];
    for (const c of comercios) {
      if (c.categoria_id === null || c.categoria_nombre === null) {
        pend.push(c);
        continue;
      }
      const clave = `${c.categoria_id}-${c.moneda}`;
      const actual = acumulado.get(clave) ?? { nombre: c.categoria_nombre, total: 0, movimientos: 0 };
      actual.total += Number(c.total);
      actual.movimientos += c.cantidad_transacciones;
      acumulado.set(clave, actual);
    }
    const lista = [...acumulado.values()].sort((a, b) => b.total - a.total);
    return { porCategoria: lista, pendientes: pend.sort((a, b) => Number(b.total) - Number(a.total)) };
  }, [comercios]);

  const maximoCategoria = porCategoria[0]?.total ?? 1;

  if (errorCuenta || error) {
    return <p className="mensaje-error">{errorCuenta ?? error}</p>;
  }

  if (cargandoCuenta) {
    return <p className="vacio">Cargando…</p>;
  }

  if (!cuentaActiva) {
    return (
      <div className="card stack" style={{ maxWidth: 480 }}>
        <div className="section-title">Todavía no hay ningún buzón vinculado</div>
        <p className="section-subtitle" style={{ margin: 0 }}>
          Vinculá Outlook o Gmail para clasificar tus comercios reales por categoría.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="section-title">Categorías detectadas</div>
          <div className="section-subtitle">Suma real de los comercios ya clasificados</div>

          <div className="stack" style={{ gap: 14, marginTop: 17 }}>
            {comercios === null && <p className="vacio">Leyendo comercios de la bandeja real…</p>}
            {comercios !== null && porCategoria.length === 0 && (
              <p className="vacio">Todavía no clasificaste ningún comercio.</p>
            )}
            {porCategoria.map((c) => (
              <div key={c.nombre} className="stack" style={{ gap: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                  <span style={{ flex: 1, color: "var(--color-text-bright-muted)" }}>{c.nombre}</span>
                  <span style={{ color: "var(--color-text-dim)", fontSize: 10.5 }}>{c.movimientos} mov.</span>
                  <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatearMonto(c.total, "CRC")}</span>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ background: "var(--color-accent-400)", width: `${Math.round((c.total / maximoCategoria) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div style={{ borderTop: "1px solid var(--color-border)", marginTop: 17, paddingTop: 14 }}>
            <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginBottom: 8 }}>
              Nueva categoría
            </div>
            <div style={{ display: "flex", gap: 7 }}>
              <input
                value={nuevaCategoria}
                onChange={(e) => setNuevaCategoria(e.target.value)}
                placeholder="ej. Transporte"
                style={{
                  flex: 1,
                  padding: "7px 10px",
                  background: "var(--color-surface-2)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                  color: "var(--color-text)",
                  fontSize: 12,
                }}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={crearCategoria}
                disabled={!nuevaCategoria.trim() || creandoCategoria}
              >
                <Plus size={13} /> Crear
              </button>
            </div>
          </div>
        </section>

        <section className="card" style={{ borderColor: "var(--color-border-accent)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Sparkle size={15} color="var(--color-accent-200)" />
            <div className="section-title">Por confirmar</div>
            <span style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--color-text-dim)" }}>
              {pendientes.length} pendientes
            </span>
          </div>
          <div className="section-subtitle">Comercios reales sin categoría asignada todavía</div>

          <div className="stack" style={{ marginTop: 17 }}>
            {comercios === null && <p className="vacio">Leyendo comercios de la bandeja real…</p>}
            {comercios !== null && pendientes.length === 0 && (
              <p className="vacio">Todo clasificado. Los comercios nuevos van a aparecer acá.</p>
            )}
            {pendientes.map((c) => (
              <div key={c.comercio_id} className="card stack" style={{ gap: 8 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span style={{ fontSize: 12.5 }}>{c.nombre}</span>
                  <span style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                    {c.cantidad_transacciones} mov.
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
                    {formatearMonto(Number(c.total), c.moneda)}
                  </span>
                </div>
                <SelectorDeCategoria
                  categorias={categorias ?? []}
                  disabled={asignando === c.comercio_id}
                  onConfirmar={(categoriaId) => confirmarCategoria(c, categoriaId)}
                />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function SelectorDeCategoria({
  categorias,
  disabled,
  onConfirmar,
}: {
  categorias: Categoria[];
  disabled: boolean;
  onConfirmar: (categoriaId: number) => void;
}) {
  const hojas = categorias.filter((c) => c.es_hoja && c.activa);
  const [seleccion, setSeleccion] = useState<string>("");

  if (hojas.length === 0) {
    return <p className="vacio">Creá una categoría primero para poder clasificar.</p>;
  }

  return (
    <div style={{ display: "flex", gap: 7 }}>
      <select
        value={seleccion}
        onChange={(e) => setSeleccion(e.target.value)}
        style={{
          flex: 1,
          padding: "6px 8px",
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          color: "var(--color-text)",
          fontSize: 11.5,
        }}
      >
        <option value="">Elegir categoría…</option>
        {hojas.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nombre}
          </option>
        ))}
      </select>
      <button
        className="btn btn-sm btn-primary"
        disabled={!seleccion || disabled}
        onClick={() => onConfirmar(Number(seleccion))}
      >
        Confirmar
      </button>
    </div>
  );
}
