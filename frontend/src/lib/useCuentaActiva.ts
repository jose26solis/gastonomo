import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { CuentaCorreo } from "../types";

/** Busca la cuenta de correo activa de un usuario. Varias pantallas lo necesitan. */
export function useCuentaActiva(usuarioId: number) {
  const [cuentas, setCuentas] = useState<CuentaCorreo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    // Reinicio deliberado antes de recargar: evita mostrar cuentas obsoletas
    // mientras el fetch para el nuevo usuarioId está en curso.
    // oxlint-disable-next-line react/set-state-in-effect
    setCuentas(null);
    setError(null);
    api
      .listarCuentas(usuarioId)
      .then((c) => {
        if (!cancelado) setCuentas(c);
      })
      .catch((e: unknown) => {
        if (!cancelado) {
          setError(e instanceof ErrorDeApiError ? e.message : "Ocurrió un error inesperado.");
        }
      });
    return () => {
      cancelado = true;
    };
  }, [usuarioId]);

  return {
    cargando: cuentas === null,
    cuentaActiva: cuentas?.find((c) => c.estado === "ACTIVA") ?? null,
    error,
  };
}
