import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { BancoDetectado, CuentaCorreo } from "../types";
import { Bancos } from "./Bancos";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, api: { listarCuentas: vi.fn(), detectarBancos: vi.fn() } };
});

function cuentaActiva(): CuentaCorreo {
  return {
    id: 1,
    usuario_id: 1,
    proveedor: "OUTLOOK",
    direccion: "titular@hotmail.com",
    estado: "ACTIVA",
    ultima_sincronizacion: null,
  };
}

function banco(overrides: Partial<BancoDetectado> = {}): BancoDetectado {
  return {
    dominio: "baccredomatic.cr",
    remitente_ejemplo: "notificaciones@baccredomatic.cr",
    cantidad_mensajes: 12,
    mensaje_mas_reciente: "2026-08-30T13:27:00",
    es_bac: true,
    cuenta_correo_id: 1,
    proveedor: "OUTLOOK",
    direccion: "titular@hotmail.com",
    ...overrides,
  };
}

describe("<Bancos />", () => {
  beforeEach(() => {
    vi.mocked(api.listarCuentas).mockReset();
    vi.mocked(api.detectarBancos).mockReset();
  });

  it("sin ningún buzón vinculado, invita a conectar correo en vez de buscar bancos", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([]);

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    expect(await screen.findByText("Todavía no hay ningún buzón vinculado")).toBeInTheDocument();
    expect(api.detectarBancos).not.toHaveBeenCalled();
  });

  it("mientras busca bancos, muestra el estado de carga", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuentaActiva()]);
    vi.mocked(api.detectarBancos).mockReturnValue(new Promise(() => {}));

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    expect(await screen.findByText(/Buscando avisos de banco/)).toBeInTheDocument();
  });

  it("con un buzón activo, termina mostrando la lista de bancos detectados", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuentaActiva()]);
    vi.mocked(api.detectarBancos).mockResolvedValue([banco()]);

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    expect(await screen.findByText("baccredomatic.cr")).toBeInTheDocument();
    expect(screen.getByText("Conectado")).toBeInTheDocument();
  });

  it("un candidato sin soporte se distingue de uno con parser real (BAC)", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuentaActiva()]);
    vi.mocked(api.detectarBancos).mockResolvedValue([banco({ dominio: "otrobanco.cr", es_bac: false })]);

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    expect(await screen.findByText("Candidato, sin soporte todavía")).toBeInTheDocument();
  });

  it("sin ningún banco detectado, lo dice en vez de mostrar una lista vacía en silencio", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuentaActiva()]);
    vi.mocked(api.detectarBancos).mockResolvedValue([]);

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    expect(
      await screen.findByText('No encontramos correos con la palabra "banco" en tus buzones vinculados.'),
    ).toBeInTheDocument();
  });

  it("un error al buscar bancos se muestra sin tumbar el resto de la pantalla", async () => {
    vi.mocked(api.listarCuentas).mockResolvedValue([cuentaActiva()]);
    vi.mocked(api.detectarBancos).mockRejectedValue(new Error("fallo de red"));

    render(<Bancos usuarioId={1} onIrAConectar={() => {}} />);

    await waitFor(() => expect(screen.getByText("Ocurrió un error inesperado.")).toBeInTheDocument());
  });
});
