import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { MetodoPago } from "../types";
import { MetodosPago } from "./MetodosPago";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { listarMetodosPago: vi.fn(), crearMetodoPago: vi.fn(), desactivarMetodoPago: vi.fn() },
  };
});

function metodo(overrides: Partial<MetodoPago> = {}): MetodoPago {
  return {
    id: 1,
    usuario_id: 1,
    alias: "Visa BAC",
    tipo: "CREDITO",
    moneda: "CRC",
    ultimos_cuatro: "4321",
    entidad: "BAC",
    dia_corte: 15,
    activo: true,
    ...overrides,
  };
}

describe("<MetodosPago />", () => {
  beforeEach(() => {
    vi.mocked(api.listarMetodosPago).mockReset();
    vi.mocked(api.crearMetodoPago).mockReset();
    vi.mocked(api.desactivarMetodoPago).mockReset();
  });

  it("lista los métodos activos ya registrados", async () => {
    vi.mocked(api.listarMetodosPago).mockResolvedValue([metodo()]);

    render(<MetodosPago usuarioId={1} />);

    expect(await screen.findByText("Visa BAC")).toBeInTheDocument();
    expect(screen.getByText(/••4321/)).toBeInTheDocument();
  });

  it("sin ningún método registrado, lo dice en vez de una lista vacía en silencio", async () => {
    vi.mocked(api.listarMetodosPago).mockResolvedValue([]);

    render(<MetodosPago usuarioId={1} />);

    expect(
      await screen.findByText("Todavía no registraste ningún método de pago."),
    ).toBeInTheDocument();
  });

  it("el botón Registrar está deshabilitado sin un alias", async () => {
    vi.mocked(api.listarMetodosPago).mockResolvedValue([]);
    render(<MetodosPago usuarioId={1} />);
    await screen.findByText("Registrar uno nuevo");

    expect(screen.getByRole("button", { name: /Registrar/ })).toBeDisabled();
  });

  it("registra un método nuevo y lo agrega a la lista sin recargar todo", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarMetodosPago).mockResolvedValue([]);
    vi.mocked(api.crearMetodoPago).mockResolvedValue(
      metodo({ id: 2, alias: "Efectivo diario", tipo: "EFECTIVO", ultimos_cuatro: null, entidad: null, dia_corte: null }),
    );
    render(<MetodosPago usuarioId={1} />);
    await screen.findByText("Registrar uno nuevo");

    await usuario.type(screen.getByPlaceholderText("ej. Visa BAC"), "Efectivo diario");
    await usuario.selectOptions(screen.getByDisplayValue("Crédito"), "EFECTIVO");
    await usuario.click(screen.getByRole("button", { name: /Registrar/ }));

    expect(await screen.findByText("Efectivo diario")).toBeInTheDocument();
    expect(api.crearMetodoPago).toHaveBeenCalledWith(
      expect.objectContaining({ usuarioId: 1, alias: "Efectivo diario", tipo: "EFECTIVO" }),
    );
  });

  it("los últimos 4 dígitos y el día de corte solo se piden para tarjetas de crédito", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarMetodosPago).mockResolvedValue([]);
    render(<MetodosPago usuarioId={1} />);
    await screen.findByText("Registrar uno nuevo");

    // CREDITO es el tipo por defecto: ambos campos empiezan visibles.
    expect(screen.getByText("Últimos 4 dígitos")).toBeInTheDocument();
    expect(screen.getByText(/Día de corte/)).toBeInTheDocument();

    await usuario.selectOptions(screen.getByDisplayValue("Crédito"), "EFECTIVO");

    expect(screen.queryByText("Últimos 4 dígitos")).not.toBeInTheDocument();
    expect(screen.queryByText(/Día de corte/)).not.toBeInTheDocument();
  });

  it("desactivar mueve el método a la lista de desactivados", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarMetodosPago).mockResolvedValue([metodo()]);
    vi.mocked(api.desactivarMetodoPago).mockResolvedValue(metodo({ activo: false }));
    render(<MetodosPago usuarioId={1} />);
    await screen.findByText("Visa BAC");

    await usuario.click(screen.getByRole("button", { name: "Desactivar Visa BAC" }));

    await waitFor(() => expect(screen.getByText(/Desactivados \(1\)/)).toBeInTheDocument());
    expect(api.desactivarMetodoPago).toHaveBeenCalledWith(1, 1);
  });
});
