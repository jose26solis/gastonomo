import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { CuentaCorreo, MensajeResumido, Proveedor } from "../types";

const etiquetaEstado: Record<CuentaCorreo["estado"], string> = {
  ACTIVA: "Activa",
  TOKEN_EXPIRADO: "Token vencido",
  DESVINCULADA: "Desvinculada",
  ERROR: "Con error",
};

/**
 * Vincula el `usuario_id` a `localStorage` en vez de a un login.
 *
 * El Laboratorio 1 sembró un usuario de demostración con id 1
 * (`sembrar_usuario_de_demostracion` en `config/database.py`); la
 * autenticación real es trabajo de un laboratorio posterior. Mientras tanto,
 * este campo deja probar el flujo con cualquier id sin tener que hardcodearlo.
 */
function useUsuarioId(): [number, (id: number) => void] {
  const [usuarioId, setUsuarioId] = useState<number>(() => {
    const guardado = window.localStorage.getItem("gastonomo.usuario_id");
    return guardado ? Number(guardado) : 1;
  });

  function cambiar(id: number) {
    setUsuarioId(id);
    window.localStorage.setItem("gastonomo.usuario_id", String(id));
  }

  return [usuarioId, cambiar];
}

export function CuentasCorreo() {
  const [usuarioId, cambiarUsuarioId] = useUsuarioId();
  const [cuentas, setCuentas] = useState<CuentaCorreo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [vinculando, setVinculando] = useState<Proveedor | null>(null);
  const [mensajesPorCuenta, setMensajesPorCuenta] = useState<
    Record<number, MensajeResumido[] | "cargando" | "error">
  >({});

  useEffect(() => {
    cargarCuentas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuarioId]);

  function cargarCuentas() {
    setCargando(true);
    setError(null);
    api
      .listarCuentas(usuarioId)
      .then(setCuentas)
      .catch((error: unknown) => setError(mensajeDeError(error)))
      .finally(() => setCargando(false));
  }

  async function vincular(proveedor: Proveedor) {
    setVinculando(proveedor);
    try {
      const { url_autorizacion } = await api.iniciarVinculacion(usuarioId, proveedor);
      window.location.href = url_autorizacion;
    } catch (error) {
      setError(mensajeDeError(error));
      setVinculando(null);
    }
  }

  async function probarConexion(cuenta: CuentaCorreo) {
    setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: "cargando" }));
    try {
      const mensajes = await api.probarConexion(usuarioId, cuenta.id);
      setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: mensajes }));
    } catch {
      setMensajesPorCuenta((actual) => ({ ...actual, [cuenta.id]: "error" }));
    }
  }

  async function desvincular(cuenta: CuentaCorreo) {
    if (!window.confirm(`¿Desvincular ${cuenta.direccion}?`)) return;
    try {
      await api.desvincular(usuarioId, cuenta.id);
      cargarCuentas();
    } catch (error) {
      setError(mensajeDeError(error));
    }
  }

  return (
    <main className="pagina-cuentas">
      <h1>Gastonomo</h1>
      <p className="subtitulo">Buzones de correo vinculados</p>

      <label className="campo-usuario">
        usuario_id
        <input
          type="number"
          min={1}
          value={usuarioId}
          onChange={(evento) => cambiarUsuarioId(Number(evento.target.value) || 1)}
        />
      </label>

      <div className="acciones-vincular">
        <button onClick={() => vincular("OUTLOOK")} disabled={vinculando !== null}>
          {vinculando === "OUTLOOK" ? "Redirigiendo…" : "Conectar Outlook"}
        </button>
        <button onClick={() => vincular("GMAIL")} disabled={vinculando !== null}>
          {vinculando === "GMAIL" ? "Redirigiendo…" : "Conectar Gmail"}
        </button>
      </div>

      {error && <p className="mensaje-error">{error}</p>}

      {cargando ? (
        <p>Cargando…</p>
      ) : cuentas.length === 0 ? (
        <p className="vacio">Todavía no hay buzones vinculados para este usuario.</p>
      ) : (
        <ul className="lista-cuentas">
          {cuentas.map((cuenta) => (
            <li key={cuenta.id} className="tarjeta-cuenta">
              <div className="encabezado-cuenta">
                <span className="proveedor">{cuenta.proveedor}</span>
                <span className={`estado estado--${cuenta.estado.toLowerCase()}`}>
                  {etiquetaEstado[cuenta.estado]}
                </span>
              </div>
              <p className="direccion">{cuenta.direccion}</p>
              <p className="ultima-sincronizacion">
                Última sincronización:{" "}
                {cuenta.ultima_sincronizacion
                  ? new Date(cuenta.ultima_sincronizacion).toLocaleString()
                  : "nunca"}
              </p>

              <div className="acciones-cuenta">
                <button
                  onClick={() => probarConexion(cuenta)}
                  disabled={cuenta.estado === "DESVINCULADA"}
                >
                  Probar conexión
                </button>
                <button className="boton-peligro" onClick={() => desvincular(cuenta)}>
                  Desvincular
                </button>
              </div>

              {mensajesPorCuenta[cuenta.id] === "cargando" && <p>Consultando…</p>}
              {mensajesPorCuenta[cuenta.id] === "error" && (
                <p className="mensaje-error">No se pudo leer la bandeja.</p>
              )}
              {Array.isArray(mensajesPorCuenta[cuenta.id]) && (
                <ul className="lista-mensajes">
                  {(mensajesPorCuenta[cuenta.id] as MensajeResumido[]).map((mensaje) => (
                    <li key={mensaje.identificador}>
                      <span className="asunto">{mensaje.asunto}</span>
                      <span className="remitente">{mensaje.remitente}</span>
                    </li>
                  ))}
                  {(mensajesPorCuenta[cuenta.id] as MensajeResumido[]).length === 0 && (
                    <li className="vacio">La bandeja no tiene mensajes.</li>
                  )}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function mensajeDeError(error: unknown): string {
  return error instanceof ErrorDeApiError ? error.message : "Ocurrió un error inesperado.";
}
