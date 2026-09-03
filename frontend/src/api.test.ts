import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErrorDeApiError, establecerTokenDeSesion } from "./api";

function respuestaOk(cuerpo: unknown, status = 200) {
  return {
    ok: true,
    status,
    json: () => Promise.resolve(cuerpo),
  } as Response;
}

function respuestaError(detalle: string, status: number) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ detalle }),
  } as Response;
}

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    establecerTokenDeSesion(null);
    vi.unstubAllGlobals();
  });

  it("arma la URL contra el backend, sin encabezados si no hay sesión", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(respuestaOk({ id: 1 }));

    await api.yo();

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/auth/yo",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("agrega el encabezado Authorization una vez que hay un token de sesión", async () => {
    establecerTokenDeSesion("un-token-real");
    vi.mocked(fetch).mockResolvedValueOnce(respuestaOk({ id: 1 }));

    await api.yo();

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ headers: { Authorization: "Bearer un-token-real" } }),
    );
  });

  it("traduce una respuesta que no es 2xx en un ErrorDeApiError con el detalle del backend", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(respuestaError("Credenciales inválidas.", 401));

    const intento = api.iniciarSesion("a@b.com", "mal");

    await expect(intento).rejects.toMatchObject({ message: "Credenciales inválidas.", status: 401 });
    await expect(intento).rejects.toBeInstanceOf(ErrorDeApiError);
  });

  it("si el cuerpo del error no es JSON válido, usa un mensaje genérico con el status", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no es JSON")),
    } as unknown as Response);

    await expect(api.yo()).rejects.toMatchObject({ message: "La API respondió 500" });
  });

  it("arma el cuerpo y el método correctos al iniciar sesión", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(respuestaOk({ token: "t", usuario: { id: 1 } }));

    await api.iniciarSesion("titular@gastonomo.cr", "clave123");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init).toMatchObject({ method: "POST" });
    expect(JSON.parse(init!.body as string)).toEqual({
      correo: "titular@gastonomo.cr",
      contrasena: "clave123",
    });
  });

  it("crearMetodoPago convierte los campos opcionales ausentes a null, no a undefined", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(respuestaOk({ id: 1 }));

    await api.crearMetodoPago({
      usuarioId: 1,
      alias: "Efectivo",
      tipo: "EFECTIVO",
      moneda: "CRC",
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/metodos-pago");
    expect(JSON.parse(init!.body as string)).toEqual({
      usuario_id: 1,
      alias: "Efectivo",
      tipo: "EFECTIVO",
      moneda: "CRC",
      ultimos_cuatro: null,
      entidad: null,
      dia_corte: null,
    });
  });

  it("bitacoraDeCompra pide la ruta de la compra con el usuario_id como query", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(respuestaOk([]));

    await api.bitacoraDeCompra(1, 42);

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/compras/42/bitacora?usuario_id=1",
      expect.anything(),
    );
  });

  it("una respuesta 204 no intenta parsear un cuerpo", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true, status: 204, json: () => Promise.reject() } as unknown as Response);

    await expect(api.desvincular(1, 2)).resolves.toBeUndefined();
  });
});
