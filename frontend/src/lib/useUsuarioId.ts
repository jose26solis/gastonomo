import { useState } from "react";

/**
 * Vincula el `usuario_id` a `localStorage` en vez de a un login.
 *
 * El Laboratorio 1 sembró un usuario de demostración con id 1
 * (`sembrar_usuario_de_demostracion` en `config/database.py`); la
 * autenticación real es trabajo de un laboratorio posterior. Mientras tanto,
 * este hook deja probar el flujo con cualquier id sin tener que hardcodearlo,
 * y lo comparten todas las pantallas de la app.
 */
export function useUsuarioId(): [number, (id: number) => void] {
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
