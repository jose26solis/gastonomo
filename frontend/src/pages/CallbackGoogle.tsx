import { useEffect, useRef, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import { CLAVE_FLUJO_GOOGLE } from "../lib/flujoGoogle";

type Resultado =
  | { estado: "cargando" }
  | { estado: "exito"; mensaje: string }
  | { estado: "error"; mensaje: string };

type ParametrosDeRetorno =
  | { ok: true; codigo: string; estado: string }
  | { ok: false; mensaje: string };

function leerParametrosDeRetorno(): ParametrosDeRetorno {
  const parametros = new URLSearchParams(window.location.search);

  const errorDeGoogle = parametros.get("error");
  if (errorDeGoogle) {
    return { ok: false, mensaje: "Google rechazó la autorización." };
  }

  const codigo = parametros.get("code");
  const estado = parametros.get("state");
  if (!codigo || !estado) {
    return { ok: false, mensaje: "Faltan los parámetros de autorización en la URL." };
  }
  return { ok: true, codigo, estado };
}

/**
 * Página a la que Google devuelve al titular tanto para "Iniciar sesión con
 * Google" (desde Login.tsx) como para vincular Google a una cuenta ya
 * logueada (desde Ajustes.tsx) -es la misma `redirect_uri` registrada para
 * los dos flujos (ver `IdentidadGoogleProveedor` en el backend), así que acá
 * hace falta distinguir cuál de los dos fue. Google no da forma de mandar
 * ese dato de vuelta -el `state` va cifrado y esta página no tiene la clave
 * para leerlo- así que se guarda una bandera en `sessionStorage` justo antes
 * de salir hacia Google, y se lee acá al volver.
 */
export function CallbackGoogle({
  onIniciarSesionConGoogle,
}: {
  onIniciarSesionConGoogle: (codigo: string, estado: string) => Promise<void>;
}) {
  const [parametros] = useState(() => leerParametrosDeRetorno());
  const [resultado, setResultado] = useState<Resultado>(
    parametros.ok ? { estado: "cargando" } : { estado: "error", mensaje: parametros.mensaje },
  );
  // El código es de un solo uso -misma guarda que CallbackVinculacion.tsx,
  // para que el doble efecto de StrictMode en desarrollo no lo reenvíe.
  const yaEnviado = useRef(false);

  useEffect(() => {
    if (!parametros.ok || yaEnviado.current) return;
    yaEnviado.current = true;

    const flujo = window.sessionStorage.getItem(CLAVE_FLUJO_GOOGLE);
    window.sessionStorage.removeItem(CLAVE_FLUJO_GOOGLE);

    const promesa =
      flujo === "vincular"
        ? api
            .completarVinculacionGoogle(parametros.codigo, parametros.estado)
            .then(() => "Google quedó vinculado a tu cuenta.")
        : onIniciarSesionConGoogle(parametros.codigo, parametros.estado).then(
            () => "Iniciaste sesión con Google.",
          );

    promesa
      .then((mensaje) => setResultado({ estado: "exito", mensaje }))
      .catch((error: unknown) => {
        const mensaje =
          error instanceof ErrorDeApiError ? error.message : "No se pudo completar con Google.";
        setResultado({ estado: "error", mensaje });
      });
  }, [parametros, onIniciarSesionConGoogle]);

  return (
    <main className="pagina-callback">
      <h1>Conectando con Google</h1>

      {resultado.estado === "cargando" && <p>Confirmando con Google…</p>}

      {resultado.estado === "exito" && <p className="mensaje-exito">{resultado.mensaje}</p>}

      {resultado.estado === "error" && (
        <p className="mensaje-error">No se pudo continuar: {resultado.mensaje}</p>
      )}

      <a href="/" className="enlace-volver">
        Ir a Gastonomo
      </a>
    </main>
  );
}
