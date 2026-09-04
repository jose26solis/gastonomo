import { ListChecks, Plus, Trash } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { Categoria, ReglaCategorizacion } from "../types";

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
 * CRUD de reglas de categorización. Hasta que existió esta pantalla,
 * `ReglaCategorizacion` era un modelo y un motor de evaluación
 * (`ConciliacionService._categorizar`) sin ningún dueño real: ningún
 * titular podía crear una regla de verdad, así que el motor siempre caía
 * al mecanismo viejo (la categoría sugerida del comercio). Una regla se
 * evalúa antes que esa sugerencia, por prioridad ascendente -la primera
 * cuyo patrón aparece en el nombre del comercio gana.
 */
export function ReglasCategorizacion({ usuarioId }: { usuarioId: number }) {
  const [reglas, setReglas] = useState<ReglaCategorizacion[] | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creando, setCreando] = useState(false);
  const [desactivando, setDesactivando] = useState<number | null>(null);

  const [nombre, setNombre] = useState("");
  const [patron, setPatron] = useState("");
  const [categoriaDestinoId, setCategoriaDestinoId] = useState("");

  useEffect(() => {
    api
      .listarReglasCategorizacion(usuarioId)
      .then(setReglas)
      .catch((e: unknown) => setError(mensajeDeError(e)));
    api
      .listarCategorias(usuarioId)
      .then(setCategorias)
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [usuarioId]);

  const hojas = categorias.filter((c) => c.es_hoja && c.activa);

  async function crear() {
    if (!nombre.trim() || !patron.trim() || !categoriaDestinoId || !reglas) return;
    setCreando(true);
    setError(null);
    try {
      const nueva = await api.crearReglaCategorizacion({
        usuarioId,
        nombre: nombre.trim(),
        patron: patron.trim(),
        categoriaDestinoId: Number(categoriaDestinoId),
      });
      setReglas([...reglas, nueva].sort((a, b) => a.prioridad - b.prioridad));
      setNombre("");
      setPatron("");
      setCategoriaDestinoId("");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCreando(false);
    }
  }

  async function desactivar(regla: ReglaCategorizacion) {
    setDesactivando(regla.id);
    try {
      const actualizada = await api.desactivarReglaCategorizacion(usuarioId, regla.id);
      setReglas((actual) => actual?.map((r) => (r.id === regla.id ? actualizada : r)) ?? null);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setDesactivando(null);
    }
  }

  const activas = reglas?.filter((r) => r.activa) ?? [];
  const inactivas = reglas?.filter((r) => !r.activa) ?? [];

  return (
    <div className="stack">
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="section-title">Tus reglas</div>
          <div className="section-subtitle">
            Se evalúan en orden de prioridad -gana la primera cuyo patrón aparece en el nombre
            del comercio. Sin ninguna que coincida, se usa la categoría que ya le asignaste a ese
            comercio en Categorías.
          </div>

          {error && <p className="mensaje-error">{error}</p>}

          <div className="stack" style={{ gap: 8, marginTop: 17 }}>
            {reglas === null && <p className="vacio">Cargando…</p>}
            {reglas !== null && activas.length === 0 && (
              <p className="vacio">Todavía no creaste ninguna regla.</p>
            )}
            {activas.map((r) => (
              <div
                key={r.id}
                className="card"
                style={{ display: "flex", alignItems: "center", gap: 11, padding: 11 }}
              >
                <span
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: 8,
                    background: "var(--color-surface-2)",
                    display: "grid",
                    placeItems: "center",
                    color: "var(--color-accent-200)",
                    flexShrink: 0,
                    fontSize: 10.5,
                  }}
                  title="Prioridad"
                >
                  {r.prioridad}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5 }}>{r.nombre}</div>
                  <div style={{ fontSize: 10.5, color: "var(--color-text-dim)" }}>
                    "{r.patron}" → {r.categoria_destino_nombre}
                    {r.veces_aplicada > 0 &&
                      ` · aplicada ${r.veces_aplicada} ${r.veces_aplicada === 1 ? "vez" : "veces"}`}
                  </div>
                </div>
                <button
                  className="btn btn-sm"
                  onClick={() => desactivar(r)}
                  disabled={desactivando === r.id}
                  aria-label={`Desactivar ${r.nombre}`}
                  title="Desactivar"
                >
                  <Trash size={13} />
                </button>
              </div>
            ))}
          </div>

          {inactivas.length > 0 && (
            <div style={{ borderTop: "1px solid var(--color-border)", marginTop: 17, paddingTop: 14 }}>
              <div style={{ fontSize: 11, color: "var(--color-text-dim)", marginBottom: 8 }}>
                Desactivadas ({inactivas.length})
              </div>
              <div className="stack" style={{ gap: 6 }}>
                {inactivas.map((r) => (
                  <div key={r.id} style={{ fontSize: 11, color: "var(--color-text-dimmer)" }}>
                    {r.nombre} · "{r.patron}" → {r.categoria_destino_nombre}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="card">
          <div className="section-title">Crear una regla</div>
          <div className="section-subtitle">
            Ej. patrón "WALMART" → categoría Supermercado: cualquier comercio futuro que contenga
            "WALMART" se categoriza solo.
          </div>

          {hojas.length === 0 ? (
            <p className="vacio" style={{ marginTop: 17 }}>
              Creá una categoría primero en la pantalla de Categorías.
            </p>
          ) : (
            <div className="stack" style={{ gap: 11, marginTop: 17 }}>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Nombre</span>
                <input
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  placeholder="ej. Walmart es supermercado"
                  style={ESTILO_INPUT}
                />
              </label>

              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Patrón (aparece en el nombre del comercio)
                </span>
                <input
                  value={patron}
                  onChange={(e) => setPatron(e.target.value.toUpperCase())}
                  placeholder="ej. WALMART"
                  style={ESTILO_INPUT}
                />
              </label>

              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Categoría destino
                </span>
                <select
                  value={categoriaDestinoId}
                  onChange={(e) => setCategoriaDestinoId(e.target.value)}
                  style={ESTILO_INPUT}
                >
                  <option value="">Elegir categoría…</option>
                  {hojas.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </label>

              <button
                className="btn btn-primary"
                onClick={crear}
                disabled={!nombre.trim() || !patron.trim() || !categoriaDestinoId || creando}
                style={{ alignSelf: "flex-start" }}
              >
                <Plus size={13} /> Crear regla
              </button>
            </div>
          )}

          <div
            style={{
              display: "flex",
              gap: 7,
              marginTop: 17,
              padding: 11,
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              fontSize: 10.5,
              color: "var(--color-text-dim)",
              lineHeight: 1.6,
            }}
          >
            <ListChecks size={13} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              La prioridad la asigna el sistema (al final de la lista) para no desplazar una regla
              que ya tenías -si dos reglas coinciden con el mismo comercio, gana la de menor número.
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}
