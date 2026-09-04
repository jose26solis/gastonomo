import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { Categoria, ReglaCategorizacion } from "../types";
import { ReglasCategorizacion } from "./ReglasCategorizacion";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      listarReglasCategorizacion: vi.fn(),
      listarCategorias: vi.fn(),
      crearReglaCategorizacion: vi.fn(),
      desactivarReglaCategorizacion: vi.fn(),
    },
  };
});

function categoria(overrides: Partial<Categoria> = {}): Categoria {
  return {
    id: 1,
    usuario_id: 1,
    nombre: "Supermercado",
    descripcion: null,
    color_hex: "#22C55E",
    categoria_padre_id: null,
    es_hoja: true,
    activa: true,
    ...overrides,
  };
}

function regla(overrides: Partial<ReglaCategorizacion> = {}): ReglaCategorizacion {
  return {
    id: 1,
    usuario_id: 1,
    nombre: "Walmart es supermercado",
    campo: "COMERCIO_NORMALIZADO",
    patron: "WALMART",
    categoria_destino_id: 1,
    categoria_destino_nombre: "Supermercado",
    prioridad: 1,
    activa: true,
    veces_aplicada: 0,
    ...overrides,
  };
}

describe("<ReglasCategorizacion />", () => {
  beforeEach(() => {
    vi.mocked(api.listarReglasCategorizacion).mockReset();
    vi.mocked(api.listarCategorias).mockReset();
    vi.mocked(api.crearReglaCategorizacion).mockReset();
    vi.mocked(api.desactivarReglaCategorizacion).mockReset();
  });

  it("lista las reglas activas ya creadas", async () => {
    vi.mocked(api.listarReglasCategorizacion).mockResolvedValue([regla()]);
    vi.mocked(api.listarCategorias).mockResolvedValue([categoria()]);

    render(<ReglasCategorizacion usuarioId={1} />);

    expect(await screen.findByText("Walmart es supermercado")).toBeInTheDocument();
    expect(screen.getByText(/"WALMART" → Supermercado/)).toBeInTheDocument();
  });

  it("sin ninguna categoría creada todavía, pide crear una primero", async () => {
    vi.mocked(api.listarReglasCategorizacion).mockResolvedValue([]);
    vi.mocked(api.listarCategorias).mockResolvedValue([]);

    render(<ReglasCategorizacion usuarioId={1} />);

    expect(
      await screen.findByText("Creá una categoría primero en la pantalla de Categorías."),
    ).toBeInTheDocument();
  });

  it("crea una regla nueva y la agrega a la lista", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarReglasCategorizacion).mockResolvedValue([]);
    vi.mocked(api.listarCategorias).mockResolvedValue([categoria()]);
    vi.mocked(api.crearReglaCategorizacion).mockResolvedValue(regla({ id: 2, prioridad: 1 }));
    render(<ReglasCategorizacion usuarioId={1} />);
    await screen.findByText("Crear una regla");

    await usuario.type(screen.getByPlaceholderText("ej. Walmart es supermercado"), "Regla nueva");
    await usuario.type(screen.getByPlaceholderText("ej. WALMART"), "walmart");
    await usuario.selectOptions(screen.getByDisplayValue("Elegir categoría…"), "1");
    await usuario.click(screen.getByRole("button", { name: /Crear regla/ }));

    expect(await screen.findByText("Walmart es supermercado")).toBeInTheDocument();
    expect(api.crearReglaCategorizacion).toHaveBeenCalledWith(
      expect.objectContaining({ usuarioId: 1, nombre: "Regla nueva", patron: "WALMART" }),
    );
  });

  it("el botón de crear está deshabilitado hasta completar los tres campos", async () => {
    vi.mocked(api.listarReglasCategorizacion).mockResolvedValue([]);
    vi.mocked(api.listarCategorias).mockResolvedValue([categoria()]);
    render(<ReglasCategorizacion usuarioId={1} />);
    await screen.findByText("Crear una regla");

    expect(screen.getByRole("button", { name: /Crear regla/ })).toBeDisabled();
  });

  it("desactivar mueve la regla a la lista de desactivadas", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarReglasCategorizacion).mockResolvedValue([regla()]);
    vi.mocked(api.listarCategorias).mockResolvedValue([categoria()]);
    vi.mocked(api.desactivarReglaCategorizacion).mockResolvedValue(regla({ activa: false }));
    render(<ReglasCategorizacion usuarioId={1} />);
    await screen.findByText("Walmart es supermercado");

    await usuario.click(screen.getByRole("button", { name: "Desactivar Walmart es supermercado" }));

    expect(await screen.findByText(/Desactivadas \(1\)/)).toBeInTheDocument();
    expect(api.desactivarReglaCategorizacion).toHaveBeenCalledWith(1, 1);
  });
});
