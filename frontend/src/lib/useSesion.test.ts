import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { Usuario } from "../types";
import { useSesion } from "./useSesion";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { yo: vi.fn(), registrar: vi.fn(), iniciarSesion: vi.fn(), completarLoginGoogle: vi.fn() },
  };
});

const CLAVE_TOKEN = "gastonomo.token";

function usuario(overrides: Partial<Usuario> = {}): Usuario {
  return {
    id: 1,
    nombre_completo: "Titular de prueba",
    correo: "titular@gastonomo.cr",
    moneda_preferida: "CRC",
    tiene_contrasena: true,
    google_vinculado: false,
    leer_transferencias_sinpe: false,
    ...overrides,
  };
}

describe("useSesion", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(api.yo).mockReset();
    vi.mocked(api.registrar).mockReset();
    vi.mocked(api.iniciarSesion).mockReset();
  });

  it("sin token guardado, termina de cargar sin usuario y sin llamar a la API", async () => {
    const { result } = renderHook(() => useSesion());

    await waitFor(() => expect(result.current.cargando).toBe(false));
    expect(result.current.usuario).toBeNull();
    expect(api.yo).not.toHaveBeenCalled();
  });

  it("con un token guardado, lo confirma contra /api/auth/yo y entra directo", async () => {
    window.localStorage.setItem(CLAVE_TOKEN, "token-guardado");
    vi.mocked(api.yo).mockResolvedValue(usuario());

    const { result } = renderHook(() => useSesion());

    await waitFor(() => expect(result.current.cargando).toBe(false));
    expect(result.current.usuario).toEqual(usuario());
  });

  it("un token vencido o inválido se descarta -no deja al titular en un estado a medias", async () => {
    window.localStorage.setItem(CLAVE_TOKEN, "token-vencido");
    vi.mocked(api.yo).mockRejectedValue(new Error("401"));

    const { result } = renderHook(() => useSesion());

    await waitFor(() => expect(result.current.cargando).toBe(false));
    expect(result.current.usuario).toBeNull();
    expect(window.localStorage.getItem(CLAVE_TOKEN)).toBeNull();
  });

  it("iniciarSesion guarda el token nuevo en localStorage y actualiza el usuario", async () => {
    vi.mocked(api.iniciarSesion).mockResolvedValue({ token: "nuevo-token", usuario: usuario() });
    const { result } = renderHook(() => useSesion());
    await waitFor(() => expect(result.current.cargando).toBe(false));

    await act(async () => {
      await result.current.iniciarSesion("titular@gastonomo.cr", "clave123");
    });

    expect(result.current.usuario).toEqual(usuario());
    expect(window.localStorage.getItem(CLAVE_TOKEN)).toBe("nuevo-token");
  });

  it("cerrarSesion borra el token y el usuario, sin llamar al servidor", async () => {
    window.localStorage.setItem(CLAVE_TOKEN, "token-guardado");
    vi.mocked(api.yo).mockResolvedValue(usuario());
    const { result } = renderHook(() => useSesion());
    await waitFor(() => expect(result.current.usuario).not.toBeNull());

    act(() => result.current.cerrarSesion());

    expect(result.current.usuario).toBeNull();
    expect(window.localStorage.getItem(CLAVE_TOKEN)).toBeNull();
  });
});
