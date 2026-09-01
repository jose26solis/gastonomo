import { EnvelopeSimple, Trash } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearMes, formatearMonto } from "../lib/formato";
import { useCuentaActiva } from "../lib/useCuentaActiva";
import type { Categoria, EstadoDePresupuesto } from "../types";

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

const HOY = new Date();

export function Presupuestos({ usuarioId, onIrAConectar }: { usuarioId: number; onIrAConectar: () => void }) {
  const { cargando: cargandoCuenta, cuentaActiva, error: errorCuenta } = useCuentaActiva(usuarioId);
  const [anio, setAnio] = useState(HOY.getFullYear());
  const [mes, setMes] = useState(HOY.getMonth() + 1);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [estados, setEstados] = useState<EstadoDePresupuesto[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [categoriaNueva, setCategoriaNueva] = useState("");
  const [montoNuevo, setMontoNuevo] = useState("");
  const [umbralNuevo, setUmbralNuevo] = useState("80");
  const [guardando, setGuardando] = useState(false);
  const [recargaClave, setRecargaClave] = useState(0);

  useEffect(() => {
    api
      .listarCategorias(usuarioId)
      .then(setCategorias)
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [usuarioId]);

  useEffect(() => {
    if (!cuentaActiva) return;
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar estados
    // obsoletos mientras el fetch para el nuevo período está en curso.
    // oxlint-disable-next-line react/set-state-in-effect
    setEstados(null);
    api
      .estadoDePresupuestos(usuarioId, cuentaActiva.id, anio, mes)
      .then((e) => {
        if (!cancelado) setEstados(e);
      })
      .catch((e: unknown) => {
        if (!cancelado) setError(mensajeDeError(e));
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId, cuentaActiva, anio, mes, recargaClave]);

  async function guardarPresupuesto() {
    if (!categoriaNueva || !montoNuevo) return;
    setGuardando(true);
    try {
      await api.crearOActualizarPresupuesto({
        usuarioId,
        categoriaId: Number(categoriaNueva),
        anio,
        mes,
        moneda: "CRC",
        montoLimite: montoNuevo,
        umbralAlerta: Number(umbralNuevo) || 80,
      });
      setMontoNuevo("");
      setRecargaClave((k) => k + 1);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar(presupuestoId: number) {
    try {
      await api.eliminarPresupuesto(usuarioId, presupuestoId);
      setEstados((actual) => actual?.filter((e) => e.presupuesto_id !== presupuestoId) ?? null);
    } catch (e) {
      setError(mensajeDeError(e));
    }
  }

  const hojas = categorias.filter((c) => c.es_hoja && c.activa);

  if (errorCuenta) {
    return <p className="mensaje-error">{errorCuenta}</p>;
  }
  if (cargandoCuenta) {
    return <p className="vacio">Cargando…</p>;
  }
  if (!cuentaActiva) {
    return (
      <div className="card stack" style={{ maxWidth: 480 }}>
        <div className="section-title">Todavía no hay ningún buzón vinculado</div>
        <p className="section-subtitle" style={{ margin: 0 }}>
          Vinculá Outlook o Gmail para comparar tus presupuestos contra el gasto real.
        </p>
        <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={onIrAConectar}>
          <EnvelopeSimple size={14} /> Conectar correo
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      {error && <p className="mensaje-error">{error}</p>}

      <div className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontSize: 11.5, color: "var(--color-text-dim)" }}>Período</span>
        <select
          value={mes}
          onChange={(e) => setMes(Number(e.target.value))}
          style={{ padding: "6px 8px", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 8, color: "var(--color-text)", fontSize: 11.5 }}
        >
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              {formatearMes(2000, m).split(" ")[0]}
            </option>
          ))}
        </select>
        <input
          type="number"
          value={anio}
          onChange={(e) => setAnio(Number(e.target.value) || HOY.getFullYear())}
          style={{ width: 72, padding: "6px 8px", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 8, color: "var(--color-text)", fontSize: 11.5 }}
        />
      </div>

      <section className="card">
        <div className="section-title">Nuevo presupuesto</div>
        <div className="section-subtitle">Colones (CRC), para {formatearMes(anio, mes)}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap", alignItems: "center" }}>
          <select
            value={categoriaNueva}
            onChange={(e) => setCategoriaNueva(e.target.value)}
            style={{ padding: "7px 10px", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 8, color: "var(--color-text)", fontSize: 12, minWidth: 160 }}
          >
            <option value="">Categoría…</option>
            {hojas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
          <input
            value={montoNuevo}
            onChange={(e) => setMontoNuevo(e.target.value)}
            placeholder="Límite, ej. 100000"
            inputMode="decimal"
            style={{ width: 150, padding: "7px 10px", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 8, color: "var(--color-text)", fontSize: 12 }}
          />
          <input
            value={umbralNuevo}
            onChange={(e) => setUmbralNuevo(e.target.value)}
            placeholder="Umbral %"
            inputMode="numeric"
            style={{ width: 90, padding: "7px 10px", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 8, color: "var(--color-text)", fontSize: 12 }}
          />
          <button className="btn btn-primary" onClick={guardarPresupuesto} disabled={!categoriaNueva || !montoNuevo || guardando}>
            Guardar
          </button>
        </div>
        {hojas.length === 0 && (
          <p className="vacio" style={{ marginTop: 11 }}>
            Todavía no tenés categorías. Creá una en la pantalla de Categorías primero.
          </p>
        )}
      </section>

      <div className="grid grid-3">
        {estados === null && <p className="vacio">Leyendo comprobantes reales…</p>}
        {estados !== null && estados.length === 0 && (
          <p className="vacio">Sin presupuestos para {formatearMes(anio, mes)}.</p>
        )}
        {estados?.map((e) => {
          const excedido = e.estado === "EXCEDIDO";
          const cerca = e.estado === "CERCA_DEL_LIMITE";
          return (
            <div
              key={e.presupuesto_id}
              className="card stack"
              style={{ borderColor: excedido ? "var(--color-accent-500)" : "var(--color-border)" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <span style={{ fontSize: 12.5, flex: 1 }}>{e.categoria_nombre}</span>
                <span
                  style={{
                    fontSize: 10.5,
                    color: excedido ? "var(--color-accent-100)" : cerca ? "var(--color-accent-200)" : "var(--color-text-dim)",
                  }}
                >
                  {excedido ? "Excedido" : cerca ? "Cerca del límite" : "En rango"}
                </span>
                <button
                  onClick={() => eliminar(e.presupuesto_id)}
                  style={{ background: "transparent", border: "none", color: "var(--color-text-dim)", cursor: "pointer", display: "grid", placeItems: "center" }}
                  title="Eliminar presupuesto"
                >
                  <Trash size={13} />
                </button>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontSize: 20, fontWeight: 500 }}>{formatearMonto(Number(e.monto_consumido), e.moneda)}</span>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  de {formatearMonto(Number(e.monto_limite), e.moneda)}
                </span>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${Math.min(e.porcentaje_usado, 100).toFixed(0)}%`,
                    background: excedido ? "var(--color-accent-200)" : cerca ? "var(--color-accent-300)" : "var(--color-accent-500)",
                  }}
                />
              </div>
              <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                {e.porcentaje_usado.toFixed(0)}% usado
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
