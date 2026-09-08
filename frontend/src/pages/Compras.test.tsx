import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { Categoria, Compra, LineaCompra, MetodoPago } from "../types";
import { Compras } from "./Compras";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      listarCompras: vi.fn(),
      listarMetodosPago: vi.fn(),
      listarCategorias: vi.fn(),
      resolverRevisionCompra: vi.fn(),
      desglosarCompra: vi.fn(),
      // PanelBitacora vive dentro de esta pantalla y también llama a `api`.
      bitacoraDeCompra: vi.fn(),
    },
  };
});

function lineaCompra(overrides: Partial<LineaCompra> = {}): LineaCompra {
  return {
    id: 1,
    descripcion: "WALMART SAN SEBASTIAN",
    cantidad: "1",
    precio_unitario: "7870.00",
    descuento: "0",
    exento_impuesto: false,
    subtotal: "7870.00",
    categoria_id: null,
    categoria_nombre: null,
    categorizada_automaticamente: false,
    ...overrides,
  };
}

function compra(overrides: Partial<Compra> = {}): Compra {
  return {
    id: 1,
    usuario_id: 1,
    comercio_id: 1,
    comercio_nombre: "WALMART SAN SEBASTIAN",
    metodo_pago_id: null,
    metodo_pago_alias: null,
    categoria_id: null,
    categoria_nombre: null,
    fecha: "2026-08-30",
    descripcion: "WALMART SAN SEBASTIAN",
    moneda: "CRC",
    total: "7870.00",
    total_moneda_base: "7870.00",
    tipo_cambio_aplicado: "1.000000",
    estado: "REGISTRADA",
    origen: "INGESTA_CORREO",
    requiere_revision: true,
    creado_en: "2026-08-30T13:27:00Z",
    lineas: [lineaCompra()],
    ...overrides,
  };
}

function metodoPago(overrides: Partial<MetodoPago> = {}): MetodoPago {
  return {
    id: 1,
    usuario_id: 1,
    alias: "Amex",
    tipo: "CREDITO",
    moneda: "CRC",
    ultimos_cuatro: "4321",
    entidad: "BAC",
    dia_corte: null,
    activo: true,
    ...overrides,
  };
}

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

describe("<Compras />", () => {
  beforeEach(() => {
    vi.mocked(api.listarCompras).mockReset();
    vi.mocked(api.listarMetodosPago).mockReset().mockResolvedValue([metodoPago()]);
    vi.mocked(api.listarCategorias).mockReset().mockResolvedValue([categoria()]);
    vi.mocked(api.resolverRevisionCompra).mockReset();
  });

  it("pide las pendientes de revisión por defecto", async () => {
    vi.mocked(api.listarCompras).mockResolvedValue([compra()]);

    render(<Compras usuarioId={1} />);

    await screen.findByText("WALMART SAN SEBASTIAN");
    expect(api.listarCompras).toHaveBeenCalledWith(1, { requiereRevision: true });
  });

  it("sin ninguna compra pendiente, lo dice en vez de una lista vacía en silencio", async () => {
    vi.mocked(api.listarCompras).mockResolvedValue([]);

    render(<Compras usuarioId={1} />);

    expect(
      await screen.findByText(
        "Ninguna compra necesita revisión -todas quedaron con método de pago y categoría.",
      ),
    ).toBeInTheDocument();
  });

  it("cambiar a 'Todas' pide sin el filtro de revisión", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([compra({ requiere_revision: false })]);
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");

    await usuario.selectOptions(screen.getByDisplayValue("Pendientes de revisión"), "todas");

    await waitFor(() =>
      expect(api.listarCompras).toHaveBeenLastCalledWith(1, { requiereRevision: undefined }),
    );
  });

  it("una compra sin método de pago muestra el selector para corregirla", async () => {
    vi.mocked(api.listarCompras).mockResolvedValue([compra({ categoria_id: 1, categoria_nombre: "Supermercado" })]);

    render(<Compras usuarioId={1} />);

    await screen.findByText("WALMART SAN SEBASTIAN");
    expect(screen.getByText("Elegir método de pago…")).toBeInTheDocument();
    expect(screen.queryByText("Elegir categoría…")).not.toBeInTheDocument();
  });

  it("corregir el método de pago llama a resolverRevisionCompra y la saca de pendientes", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([
      compra({ categoria_id: 1, categoria_nombre: "Supermercado" }),
    ]);
    vi.mocked(api.resolverRevisionCompra).mockResolvedValue(
      compra({
        metodo_pago_id: 1,
        metodo_pago_alias: "Amex",
        categoria_id: 1,
        categoria_nombre: "Supermercado",
        requiere_revision: false,
      }),
    );
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");

    await usuario.selectOptions(screen.getByDisplayValue("Elegir método de pago…"), "1");
    await usuario.click(screen.getByRole("button", { name: "Corregir" }));

    await waitFor(() =>
      expect(api.resolverRevisionCompra).toHaveBeenCalledWith(1, 1, {
        metodoPagoId: 1,
        categoriaId: undefined,
      }),
    );
    // Se resolvió del todo -en "Pendientes" desaparece de la lista.
    await waitFor(() =>
      expect(screen.queryByText("WALMART SAN SEBASTIAN")).not.toBeInTheDocument(),
    );
  });

  it("abre el panel de bitácora al hacer clic en el botón de reloj", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([compra()]);
    vi.mocked(api.bitacoraDeCompra).mockResolvedValue([]);
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");

    await usuario.click(screen.getByRole("button", { name: /Ver bitácora de/ }));

    expect(await screen.findByText("Trazabilidad completa")).toBeInTheDocument();
  });

  it("abre el panel de desglose y precarga el renglón existente más uno vacío", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([compra()]);
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");

    await usuario.click(screen.getByRole("button", { name: "Desglosar WALMART SAN SEBASTIAN" }));

    const descripciones = screen.getAllByPlaceholderText("Descripción");
    expect(descripciones).toHaveLength(2);
    expect(descripciones[0]).toHaveValue("WALMART SAN SEBASTIAN");
    expect(screen.getAllByPlaceholderText("Monto")[0]).toHaveValue("7870.00");
  });

  it("una suma que no calza con el total deja 'Guardar desglose' deshabilitado", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([compra()]);
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");
    await usuario.click(screen.getByRole("button", { name: "Desglosar WALMART SAN SEBASTIAN" }));

    const monto = screen.getAllByPlaceholderText("Monto")[0];
    await usuario.clear(monto);
    await usuario.type(monto, "1000.00");

    expect(screen.getByText(/Suma:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar desglose" })).toBeDisabled();
  });

  it("desglosar reparte el monto entre dos renglones y llama a la API", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.listarCompras).mockResolvedValue([compra()]);
    vi.mocked(api.desglosarCompra).mockResolvedValue(
      compra({
        requiere_revision: true, // el segundo renglón queda sin categoría
        categoria_id: null,
        categoria_nombre: "Varias categorías",
        lineas: [
          lineaCompra({
            id: 10,
            descripcion: "Víveres",
            subtotal: "5000.00",
            categoria_id: 1,
            categoria_nombre: "Supermercado",
          }),
          lineaCompra({ id: 11, descripcion: "Limpieza", subtotal: "2870.00" }),
        ],
      }),
    );
    render(<Compras usuarioId={1} />);
    await screen.findByText("WALMART SAN SEBASTIAN");
    await usuario.click(screen.getByRole("button", { name: "Desglosar WALMART SAN SEBASTIAN" }));

    const montos = screen.getAllByPlaceholderText("Monto");
    await usuario.clear(montos[0]);
    await usuario.type(montos[0], "5000.00");
    await usuario.type(screen.getAllByPlaceholderText("Descripción")[1], "Limpieza");
    await usuario.type(montos[1], "2870.00");
    expect(screen.getByRole("button", { name: "Guardar desglose" })).toBeEnabled();

    await usuario.click(screen.getByRole("button", { name: "Guardar desglose" }));

    await waitFor(() =>
      expect(api.desglosarCompra).toHaveBeenCalledWith(1, 1, [
        {
          descripcion: "WALMART SAN SEBASTIAN",
          cantidad: "1",
          precioUnitario: "5000.00",
          categoriaId: undefined,
        },
        { descripcion: "Limpieza", cantidad: "1", precioUnitario: "2870.00", categoriaId: undefined },
      ]),
    );
    // El texto vive en un `div` con varios fragmentos ("29 ago · ... ·
    // Varias categorías") -por eso una expresión regular, no el texto exacto.
    expect(await screen.findByText(/Varias categorías/)).toBeInTheDocument();
  });
});
