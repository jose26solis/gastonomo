import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErrorDeApiError } from "../api";
import type { CuentaCorreo } from "../types";
import { useCuentaActiva } from "./useCuentaActiva";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, api: { listarCuentas: vi.fn() } };
});

function cuenta(overrides: Partial<CuentaCorreo> = {}): CuentaCorreo {
  return {
    id: 1,
    usuario_id: 1,
    proveedor: "OUTLOOK",
    direccion: "titular@hotmail.com",
    estado: "ACTIVA",
    ultima_sincronizacion: null,
    ...overrides,
  };
}

describe("useCuentaActiva", () => {
  beforeEach(() => {
    vi.mocked(api.listarCuentas).mockReset();
  });

  it("empieza cargando, sin cuenta activa todavía", () => {
    vi.mocked(api.listarCuentas).mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useCuentaActiva(1));

    expect(result.current.cargando).toBe(true);
    expect(result.current.hayCuentaActiva).toBe(false);
  });

  it("hayCuentaActiva es true si al menos una cuenta está ACTIVA", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([
      cuenta({ id: 1, estado: "DESVINCULADA" }),
      cuenta({ id: 2, estado: "ACTIVA" }),
    ]);

    const { result } = renderHook(() => useCuentaActiva(1));

    await waitFor(() => expect(result.current.cargando).toBe(false));
    expect(result.current.hayCuentaActiva).toBe(true);
    expect(result.current.cuentas).toHaveLength(2);
  });

  it("sin ninguna cuenta ACTIVA, hayCuentaActiva es false", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuenta({ estado: "TOKEN_EXPIRADO" })]);

    const { result } = renderHook(() => useCuentaActiva(1));

    await waitFor(() => expect(result.current.cargando).toBe(false));
    expect(result.current.hayCuentaActiva).toBe(false);
  });

  it("un error de la API queda expuesto en `error`, no revienta el hook", async () => {
    vi.mocked(api.listarCuentas).mockRejectedValue(new ErrorDeApiError("Sesión vencida.", 401));

    const { result } = renderHook(() => useCuentaActiva(1));

    await waitFor(() => expect(result.current.error).toBe("Sesión vencida."));
    expect(result.current.hayCuentaActiva).toBe(false);
  });
});
