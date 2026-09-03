import { CreditCard, Plus, Trash } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { MetodoPago, TipoMetodoPago } from "../types";

const ETIQUETA_TIPO: Record<TipoMetodoPago, string> = {
  EFECTIVO: "Efectivo",
  DEBITO: "Débito",
  CREDITO: "Crédito",
  SINPE_MOVIL: "SINPE Móvil",
};

const ESTILO_INPUT = {
  padding: "7px 10px",
  background: "var(--color-surface-2)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  color: "var(--color-text)",
  fontSize: 12,
};

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}

/**
 * CRUD de métodos de pago. Sin esto `ConciliacionService` nunca tiene con
 * qué emparejar los últimos 4 dígitos que trae un comprobante -toda compra
 * quedaría marcada "requiere revisión" por falta de un método de pago
 * registrado, aunque el comercio y la categoría sí se hayan resuelto bien.
 */
export function MetodosPago({ usuarioId }: { usuarioId: number }) {
  const [metodos, setMetodos] = useState<MetodoPago[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creando, setCreando] = useState(false);
  const [desactivando, setDesactivando] = useState<number | null>(null);

  const [alias, setAlias] = useState("");
  const [tipo, setTipo] = useState<TipoMetodoPago>("CREDITO");
  const [moneda, setMoneda] = useState("CRC");
  const [ultimosCuatro, setUltimosCuatro] = useState("");
  const [entidad, setEntidad] = useState("");
  const [diaCorte, setDiaCorte] = useState("");

  const llevaUltimosCuatro = tipo === "DEBITO" || tipo === "CREDITO";
  const llevaDiaCorte = tipo === "CREDITO";

  useEffect(() => {
    api
      .listarMetodosPago(usuarioId)
      .then(setMetodos)
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [usuarioId]);

  async function crear() {
    if (!alias.trim() || !metodos) return;
    setCreando(true);
    setError(null);
    try {
      const nuevo = await api.crearMetodoPago({
        usuarioId,
        alias: alias.trim(),
        tipo,
        moneda,
        ultimosCuatro: llevaUltimosCuatro && ultimosCuatro ? ultimosCuatro : undefined,
        entidad: entidad.trim() || undefined,
        diaCorte: llevaDiaCorte && diaCorte ? Number(diaCorte) : undefined,
      });
      setMetodos([...metodos, nuevo]);
      setAlias("");
      setUltimosCuatro("");
      setEntidad("");
      setDiaCorte("");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCreando(false);
    }
  }

  async function desactivar(metodo: MetodoPago) {
    setDesactivando(metodo.id);
    try {
      const actualizado = await api.desactivarMetodoPago(usuarioId, metodo.id);
      setMetodos((actual) => actual?.map((m) => (m.id === metodo.id ? actualizado : m)) ?? null);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setDesactivando(null);
    }
  }

  const activos = metodos?.filter((m) => m.activo) ?? [];
  const inactivos = metodos?.filter((m) => !m.activo) ?? [];

  return (
    <div className="stack">
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="section-title">Tus métodos de pago</div>
          <div className="section-subtitle">
            Con estos, la conciliación automática empareja cada comprobante por sus últimos 4
            dígitos -sin un método registrado, la compra queda marcada para revisar.
          </div>

          {error && <p className="mensaje-error">{error}</p>}

          <div className="stack" style={{ gap: 8, marginTop: 17 }}>
            {metodos === null && <p className="vacio">Cargando…</p>}
            {metodos !== null && activos.length === 0 && (
              <p className="vacio">Todavía no registraste ningún método de pago.</p>
            )}
            {activos.map((m) => (
              <div
                key={m.id}
                className="card"
                style={{ display: "flex", alignItems: "center", gap: 11, padding: 11 }}
              >
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 8,
                    background: "var(--color-surface-2)",
                    display: "grid",
                    placeItems: "center",
                    color: "var(--color-accent-200)",
                    flexShrink: 0,
                  }}
                >
                  <CreditCard size={15} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5 }}>{m.alias}</div>
                  <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                    {ETIQUETA_TIPO[m.tipo]} · {m.moneda}
                    {m.ultimos_cuatro ? ` · ••${m.ultimos_cuatro}` : ""}
                    {m.entidad ? ` · ${m.entidad}` : ""}
                    {m.dia_corte ? ` · corte día ${m.dia_corte}` : ""}
                  </div>
                </div>
                <button
                  className="btn btn-sm"
                  onClick={() => desactivar(m)}
                  disabled={desactivando === m.id}
                  aria-label={`Desactivar ${m.alias}`}
                  title="Desactivar"
                >
                  <Trash size={13} />
                </button>
              </div>
            ))}
          </div>

          {inactivos.length > 0 && (
            <div style={{ borderTop: "1px solid var(--color-border)", marginTop: 17, paddingTop: 14 }}>
              <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginBottom: 8 }}>
                Desactivados ({inactivos.length})
              </div>
              <div className="stack" style={{ gap: 6 }}>
                {inactivos.map((m) => (
                  <div key={m.id} style={{ fontSize: 11, color: "var(--color-text-dimmer)" }}>
                    {m.alias} · {ETIQUETA_TIPO[m.tipo]}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="card">
          <div className="section-title">Registrar uno nuevo</div>
          <div className="section-subtitle">Alias, tipo y con qué moneda opera</div>

          <div className="stack" style={{ gap: 11, marginTop: 17 }}>
            <label className="stack" style={{ gap: 5 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Alias</span>
              <input
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                placeholder="ej. Visa BAC"
                style={ESTILO_INPUT}
              />
            </label>

            <div className="grid grid-2" style={{ gap: 11 }}>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Tipo</span>
                <select
                  value={tipo}
                  onChange={(e) => setTipo(e.target.value as TipoMetodoPago)}
                  style={ESTILO_INPUT}
                >
                  {(Object.keys(ETIQUETA_TIPO) as TipoMetodoPago[]).map((t) => (
                    <option key={t} value={t}>
                      {ETIQUETA_TIPO[t]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Moneda</span>
                <select value={moneda} onChange={(e) => setMoneda(e.target.value)} style={ESTILO_INPUT}>
                  <option value="CRC">Colones (CRC)</option>
                  <option value="USD">Dólares (USD)</option>
                  <option value="EUR">Euros (EUR)</option>
                </select>
              </label>
            </div>

            {llevaUltimosCuatro && (
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Últimos 4 dígitos
                </span>
                <input
                  value={ultimosCuatro}
                  onChange={(e) => setUltimosCuatro(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  placeholder="1234"
                  inputMode="numeric"
                  style={ESTILO_INPUT}
                />
              </label>
            )}

            <label className="stack" style={{ gap: 5 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Entidad (opcional)</span>
              <input
                value={entidad}
                onChange={(e) => setEntidad(e.target.value)}
                placeholder="ej. BAC"
                style={ESTILO_INPUT}
              />
            </label>

            {llevaDiaCorte && (
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Día de corte (opcional)
                </span>
                <input
                  value={diaCorte}
                  onChange={(e) => setDiaCorte(e.target.value.replace(/\D/g, "").slice(0, 2))}
                  placeholder="15"
                  inputMode="numeric"
                  style={ESTILO_INPUT}
                />
              </label>
            )}

            <button
              className="btn btn-primary"
              onClick={crear}
              disabled={!alias.trim() || creando}
              style={{ alignSelf: "flex-start" }}
            >
              <Plus size={13} /> Registrar
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
