import { useEffect, useState } from "react";
import { api, ErrorDeApiError } from "../api";
import type { CuentaCorreo } from "../types";

/**
 * Busca las cuentas de correo del usuario. Varias pantallas solo necesitan
 * saber si hay al menos una vinculada y activa -para eso está
 * `hayCuentaActiva`- porque los datos en sí ya se piden combinando todas las
 * cuentas activas (`api.resumenFinanciero`, `api.listarComercios`, etc.), no
 * de una cuenta puntual. Antes este hook devolvía "la" cuenta activa (la
 * primera que encontrara); con dos cuentas vinculadas a la vez eso hacía que,
 * según cuál hubiera quedado activa más recientemente, el resto del
 * historial pareciera desaparecer de la vista.
 */
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
    cuentas: cuentas ?? [],
    hayCuentaActiva: cuentas?.some((c) => c.estado === "ACTIVA") ?? false,
    error,
  };
}
