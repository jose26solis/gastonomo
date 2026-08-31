import { useEffect, useRef, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { Proveedor } from "../types";

type Resultado =
  | { estado: "cargando" }
  | { estado: "exito"; direccion: string }
  | { estado: "error"; mensaje: string };

type ParametrosDeRetorno =
  | { ok: true; codigo: string; estado: string }
  | { ok: false; mensaje: string };

const nombreProveedor: Record<Proveedor, string> = {
  OUTLOOK: "Outlook",
  GMAIL: "Gmail",
};

/** Lee `code`/`state` (o el error) que trajo el redirect del proveedor. */
function leerParametrosDeRetorno(proveedor: Proveedor): ParametrosDeRetorno {
  const parametros = new URLSearchParams(window.location.search);

  const errorDelProveedor = parametros.get("error");
  if (errorDelProveedor) {
    // El titular cerró la ventana de consentimiento o la rechazó: no es un
    // error nuestro, es una decisión válida que hay que mostrar sin drama.
    const descripcion = parametros.get("error_description");
    return {
      ok: false,
      mensaje: descripcion ?? `${nombreProveedor[proveedor]} rechazó la autorización.`,
    };
  }

  const codigo = parametros.get("code");
  const estado = parametros.get("state");
  if (!codigo || !estado) {
    return { ok: false, mensaje: "Faltan los parámetros de autorización en la URL." };
  }
  return { ok: true, codigo, estado };
}

/**
 * Página a la que Microsoft o Google devuelven al titular tras autorizar.
 *
 * Es esta página -no el backend- la dueña del `redirect_uri` que se registró
 * en Azure/Google Cloud. Lee `code` y `state` de la URL y se los pasa al
 * backend por `fetch`: así el usuario nunca ve un JSON crudo, que es lo que
 * pasaría si el navegador aterrizara directo en el endpoint de la API.
 */
export function CallbackVinculacion({ proveedor }: { proveedor: Proveedor }) {
  // Se lee una sola vez, en la inicialización: la URL no cambia durante la
  // vida de esta página, y derivarlo aquí evita disparar un setState
  // síncrono dentro del efecto para el caso de error.
  const [parametros] = useState(() => leerParametrosDeRetorno(proveedor));
  const [resultado, setResultado] = useState<Resultado>(
    parametros.ok ? { estado: "cargando" } : { estado: "error", mensaje: parametros.mensaje },
  );
  // El código de autorización es de un solo uso. En desarrollo, StrictMode
  // ejecuta los efectos dos veces a propósito para detectar side effects mal
  // limpiados; sin esta guarda, la segunda ejecución reenviaría el mismo
  // código y Microsoft/Google la rechazarían por "ya usado" o "expirado",
  // aunque la primera sí haya vinculado la cuenta.
  const yaEnviado = useRef(false);

  useEffect(() => {
    if (!parametros.ok || yaEnviado.current) return;
    yaEnviado.current = true;
    api
      .completarVinculacion(proveedor, parametros.codigo, parametros.estado)
      .then((cuenta) => setResultado({ estado: "exito", direccion: cuenta.direccion }))
      .catch((error: unknown) => {
        const mensaje =
          error instanceof ErrorDeApiError
            ? error.message
            : "No se pudo completar la vinculación.";
        setResultado({ estado: "error", mensaje });
      });
  }, [parametros, proveedor]);

  return (
    <main className="pagina-callback">
      <h1>Vinculando {nombreProveedor[proveedor]}</h1>

      {resultado.estado === "cargando" && <p>Confirmando con {nombreProveedor[proveedor]}…</p>}

      {resultado.estado === "exito" && (
        <p className="mensaje-exito">
          Listo: <strong>{resultado.direccion}</strong> quedó vinculado.
        </p>
      )}

      {resultado.estado === "error" && (
        <p className="mensaje-error">No se pudo vincular la cuenta: {resultado.mensaje}</p>
      )}

      <a href="/" className="enlace-volver">
        Volver a mis cuentas
      </a>
    </main>
  );
}
