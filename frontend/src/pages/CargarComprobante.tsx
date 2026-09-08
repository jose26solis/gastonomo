import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { formatearMonto } from "../lib/formato";
import type { Categoria, MetodoPago } from "../types";

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
 * Cargar a mano un comprobante de un banco sin lector exacto.
 *
 * Solo BAC tiene un lector automático validado contra una notificación real
 * (ver `comprobante_bac.py` en el backend) -para cualquier otro banco, el
 * titular pega el texto de la notificación (el mismo correo o SMS que le
 * llegó) y un lector genérico intenta sacar lo que pueda. Nunca se guarda
 * solo: siempre hay que confirmar (o corregir) los campos antes de que se
 * convierta en un gasto real, en dos pasos -"Analizar" primero, "Confirmar"
 * después- porque un lector sin validar contra ese banco puede fallar más
 * de lo que un titular esperaría de la ingesta automática.
 */
export function CargarComprobante({
  usuarioId,
  onIrACompras,
}: {
  usuarioId: number;
  onIrACompras: () => void;
}) {
  const [metodosPago, setMetodosPago] = useState<MetodoPago[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [banco, setBanco] = useState("");
  const [texto, setTexto] = useState("");
  const [analizando, setAnalizando] = useState(false);
  const [analizado, setAnalizado] = useState(false);
  const [confianzaBaja, setConfianzaBaja] = useState(false);

  const [comercio, setComercio] = useState("");
  const [fecha, setFecha] = useState("");
  const [moneda, setMoneda] = useState("CRC");
  const [monto, setMonto] = useState("");
  const [ultimosCuatro, setUltimosCuatro] = useState("");
  const [metodoPagoId, setMetodoPagoId] = useState("");
  const [categoriaId, setCategoriaId] = useState("");

  const [creando, setCreando] = useState(false);
  const [creada, setCreada] = useState<{ comercio: string; monto: string; moneda: string } | null>(
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

  const hojas = categorias.filter((c) => c.es_hoja && c.activa);

  async function analizar() {
    if (!banco.trim() || !texto.trim()) return;
    setError(null);
    setCreada(null);
    setAnalizando(true);
    try {
      const resultado = await api.analizarComprobanteManual(banco.trim(), texto);
      setComercio(resultado.comercio ?? "");
      setFecha(resultado.fecha ? resultado.fecha.slice(0, 10) : "");
      setMoneda(resultado.moneda ?? "CRC");
      setMonto(resultado.monto ?? "");
      setUltimosCuatro(resultado.ultimos_cuatro ?? "");
      setMetodoPagoId("");
      setCategoriaId("");
      setConfianzaBaja(resultado.confianza < 0.75);
      setAnalizado(true);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setAnalizando(false);
    }
  }

  async function confirmar() {
    if (!comercio.trim() || !fecha || !monto) return;
    setError(null);
    setCreando(true);
    try {
      const compra = await api.crearComprobanteManual({
        usuarioId,
        banco: banco.trim(),
        comercio: comercio.trim(),
        fecha,
        moneda,
        monto,
        ultimosCuatro: ultimosCuatro || undefined,
        metodoPagoId: metodoPagoId ? Number(metodoPagoId) : undefined,
        categoriaId: categoriaId ? Number(categoriaId) : undefined,
      });
      setCreada({ comercio: compra.comercio_nombre, monto: compra.total, moneda: compra.moneda });
      setBanco("");
      setTexto("");
      setAnalizado(false);
      setComercio("");
      setFecha("");
      setMoneda("CRC");
      setMonto("");
      setUltimosCuatro("");
      setMetodoPagoId("");
      setCategoriaId("");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCreando(false);
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="section-title">Cargar comprobante de otro banco</div>
        <div className="section-subtitle">
          Solo BAC tiene un lector automático validado contra una notificación real. Para
          cualquier otro banco, pegá el texto de la notificación de compra -el mismo correo o
          SMS que te llegó- y un lector general intenta sacar lo que pueda; vos confirmás o
          corregís antes de que se convierta en un gasto real.
        </div>

        {error && (
          <p className="mensaje-error" style={{ marginTop: 11 }}>
            {error}
          </p>
        )}

        {creada && (
          <div
            className="stack"
            style={{
              marginTop: 11,
              gap: 8,
              flexDirection: "row",
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <p className="mensaje-exito" style={{ margin: 0 }}>
              Se creó la compra de {creada.comercio} por{" "}
              {formatearMonto(Number(creada.monto), creada.moneda)}.
            </p>
            <button className="btn btn-sm" onClick={onIrACompras}>
              Ver en Compras
            </button>
          </div>
        )}

        <div className="stack" style={{ gap: 11, marginTop: 17 }}>
          <label className="stack" style={{ gap: 5 }}>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Banco</span>
            <input
              value={banco}
              onChange={(e) => setBanco(e.target.value)}
              placeholder="ej. Banco Popular"
              disabled={analizado}
              style={ESTILO_INPUT}
            />
          </label>
          <label className="stack" style={{ gap: 5 }}>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
              Texto de la notificación
            </span>
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Pegá acá el correo o SMS completo de la compra"
              rows={6}
              disabled={analizado}
              style={{ ...ESTILO_INPUT, fontFamily: "inherit", resize: "vertical" }}
            />
          </label>

          {!analizado ? (
            <button
              className="btn btn-primary"
              onClick={analizar}
              disabled={!banco.trim() || !texto.trim() || analizando}
              style={{ alignSelf: "flex-start" }}
            >
              {analizando ? "Analizando…" : "Analizar"}
            </button>
          ) : (
            <button
              className="btn btn-sm"
              type="button"
              onClick={() => setAnalizado(false)}
              style={{ alignSelf: "flex-start" }}
            >
              ← Editar el texto pegado
            </button>
          )}
        </div>
      </div>

      {analizado && (
        <div className="card">
          <div className="section-title">Confirmá los datos</div>
          <div className="section-subtitle">
            {confianzaBaja
              ? "El lector encontró poco en el texto -revisá todos los campos con cuidado antes de guardar."
              : "Esto es lo que el lector encontró en el texto. Corregí lo que haga falta antes de guardar."}
          </div>

          <div className="stack" style={{ gap: 11, marginTop: 17 }}>
            <label className="stack" style={{ gap: 5 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Comercio</span>
              <input
                value={comercio}
                onChange={(e) => setComercio(e.target.value)}
                placeholder="ej. Automercado Escazú"
                style={ESTILO_INPUT}
              />
            </label>

            <div className="grid grid-2" style={{ gap: 11 }}>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Fecha</span>
                <input
                  type="date"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                  style={ESTILO_INPUT}
                />
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

            <div className="grid grid-2" style={{ gap: 11 }}>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>Monto</span>
                <input
                  value={monto}
                  onChange={(e) => setMonto(e.target.value)}
                  placeholder="0.00"
                  inputMode="decimal"
                  style={ESTILO_INPUT}
                />
              </label>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Últimos 4 dígitos (opcional)
                </span>
                <input
                  value={ultimosCuatro}
                  onChange={(e) => setUltimosCuatro(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  placeholder="1234"
                  inputMode="numeric"
                  style={ESTILO_INPUT}
                />
              </label>
            </div>

            <div className="grid grid-2" style={{ gap: 11 }}>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Método de pago (opcional)
                </span>
                <select
                  value={metodoPagoId}
                  onChange={(e) => setMetodoPagoId(e.target.value)}
                  style={ESTILO_INPUT}
                >
                  <option value="">
                    {ultimosCuatro ? "Emparejar por últimos 4 dígitos" : "Sin definir"}
                  </option>
                  {metodosPago.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.alias}
                    </option>
                  ))}
                </select>
              </label>
              <label className="stack" style={{ gap: 5 }}>
                <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                  Categoría (opcional)
                </span>
                <select
                  value={categoriaId}
                  onChange={(e) => setCategoriaId(e.target.value)}
                  style={ESTILO_INPUT}
                >
                  <option value="">Categorizar sola (reglas y sugerencias)</option>
                  {hojas.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <button
              className="btn btn-primary"
              onClick={confirmar}
              disabled={!comercio.trim() || !fecha || !monto || creando}
              style={{ alignSelf: "flex-start" }}
            >
              {creando ? "Guardando…" : "Confirmar y crear la compra"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
