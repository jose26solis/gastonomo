import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { Categoria, Compra, ComprobanteManualAnalizado, MetodoPago } from "../types";
import { CargarComprobante } from "./CargarComprobante";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      listarMetodosPago: vi.fn(),
      listarCategorias: vi.fn(),
      analizarComprobanteManual: vi.fn(),
      crearComprobanteManual: vi.fn(),
    },
  };
});

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

function analizado(overrides: Partial<ComprobanteManualAnalizado> = {}): ComprobanteManualAnalizado {
  return {
    banco: "Banco Popular",
    comercio: "AUTOMERCADO ESCAZU",
    fecha: "2026-09-05T00:00:00",
    marca_tarjeta: "VISA",
    ultimos_cuatro: "5566",
    autorizacion: null,
    referencia: null,
    moneda: "CRC",
    monto: "15420.50",
    confianza: 1.0,
    ...overrides,
  };
}

function compra(overrides: Partial<Compra> = {}): Compra {
  return {
    id: 1,
    usuario_id: 1,
    comercio_id: 1,
    comercio_nombre: "AUTOMERCADO ESCAZU",
    metodo_pago_id: null,
    metodo_pago_alias: null,
    categoria_id: null,
    categoria_nombre: null,
    fecha: "2026-09-05",
    descripcion: "AUTOMERCADO ESCAZU",
    moneda: "CRC",
    total: "15420.50",
    total_moneda_base: "15420.50",
    tipo_cambio_aplicado: "1.000000",
    estado: "REGISTRADA",
    origen: "MANUAL",
    requiere_revision: true,
    creado_en: "2026-09-05T12:00:00Z",
    lineas: [],
    ...overrides,
  };
}

describe("<CargarComprobante />", () => {
  beforeEach(() => {
    vi.mocked(api.listarMetodosPago).mockReset().mockResolvedValue([metodoPago()]);
    vi.mocked(api.listarCategorias).mockReset().mockResolvedValue([categoria()]);
    vi.mocked(api.analizarComprobanteManual).mockReset();
    vi.mocked(api.crearComprobanteManual).mockReset();
  });

  it("el botón Analizar arranca deshabilitado hasta llenar banco y texto", async () => {
    const usuario = userEvent.setup();
    render(<CargarComprobante usuarioId={1} onIrACompras={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Analizar" })).toBeDisabled();

    await usuario.type(screen.getByPlaceholderText("ej. Banco Popular"), "Banco Popular");
    expect(screen.getByRole("button", { name: "Analizar" })).toBeDisabled();

    await usuario.type(
      screen.getByPlaceholderText("Pegá acá el correo o SMS completo de la compra"),
      "Comercio: AUTOMERCADO ESCAZU",
    );
    expect(screen.getByRole("button", { name: "Analizar" })).toBeEnabled();
  });

  it("analizar precarga el formulario de confirmación con lo que encontró el lector", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.analizarComprobanteManual).mockResolvedValue(analizado());
    render(<CargarComprobante usuarioId={1} onIrACompras={vi.fn()} />);

    await usuario.type(screen.getByPlaceholderText("ej. Banco Popular"), "Banco Popular");
    await usuario.type(
      screen.getByPlaceholderText("Pegá acá el correo o SMS completo de la compra"),
      "Comercio: AUTOMERCADO ESCAZU\nMonto: CRC 15,420.50",
    );
    await usuario.click(screen.getByRole("button", { name: "Analizar" }));

    await waitFor(() =>
      expect(api.analizarComprobanteManual).toHaveBeenCalledWith(
        "Banco Popular",
        "Comercio: AUTOMERCADO ESCAZU\nMonto: CRC 15,420.50",
      ),
    );
    expect(await screen.findByDisplayValue("AUTOMERCADO ESCAZU")).toBeInTheDocument();
    expect(screen.getByDisplayValue("15420.50")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-09-05")).toBeInTheDocument();
  });

  it("una confianza baja avisa que hay que revisar todo con cuidado", async () => {
    const usuario = userEvent.setup();
    vi.mocked(api.analizarComprobanteManual).mockResolvedValue(
      analizado({ comercio: null, confianza: 0.25 }),
    );
    render(<CargarComprobante usuarioId={1} onIrACompras={vi.fn()} />);
    await usuario.type(screen.getByPlaceholderText("ej. Banco Popular"), "Banco X");
    await usuario.type(
      screen.getByPlaceholderText("Pegá acá el correo o SMS completo de la compra"),
      "algo",
    );

    await usuario.click(screen.getByRole("button", { name: "Analizar" }));

    expect(
      await screen.findByText(/El lector encontró poco en el texto/),
    ).toBeInTheDocument();
  });

  it("confirmar crea la compra y muestra el mensaje de éxito", async () => {
    const usuario = userEvent.setup();
    const alIrACompras = vi.fn();
    vi.mocked(api.analizarComprobanteManual).mockResolvedValue(analizado());
    vi.mocked(api.crearComprobanteManual).mockResolvedValue(compra());
    render(<CargarComprobante usuarioId={1} onIrACompras={alIrACompras} />);
    await usuario.type(screen.getByPlaceholderText("ej. Banco Popular"), "Banco Popular");
    await usuario.type(
      screen.getByPlaceholderText("Pegá acá el correo o SMS completo de la compra"),
      "algo",
    );
    await usuario.click(screen.getByRole("button", { name: "Analizar" }));
    await screen.findByDisplayValue("AUTOMERCADO ESCAZU");

    await usuario.click(screen.getByRole("button", { name: "Confirmar y crear la compra" }));

    await waitFor(() =>
      expect(api.crearComprobanteManual).toHaveBeenCalledWith({
        usuarioId: 1,
        banco: "Banco Popular",
        comercio: "AUTOMERCADO ESCAZU",
        fecha: "2026-09-05",
        moneda: "CRC",
        monto: "15420.50",
        ultimosCuatro: "5566",
        metodoPagoId: undefined,
        categoriaId: undefined,
      }),
    );
    expect(await screen.findByText(/Se creó la compra de AUTOMERCADO ESCAZU/)).toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: "Ver en Compras" }));
    expect(alIrACompras).toHaveBeenCalled();
  });

  it("un error al analizar se muestra y no rompe el formulario", async () => {
    const usuario = userEvent.setup();
    const { ErrorDeApiError } = await import("../api");
    vi.mocked(api.analizarComprobanteManual).mockRejectedValue(
      new ErrorDeApiError("El texto no puede venir vacío.", 422),
    );
    render(<CargarComprobante usuarioId={1} onIrACompras={vi.fn()} />);
    await usuario.type(screen.getByPlaceholderText("ej. Banco Popular"), "Banco X");
    await usuario.type(
      screen.getByPlaceholderText("Pegá acá el correo o SMS completo de la compra"),
      "algo",
    );

    await usuario.click(screen.getByRole("button", { name: "Analizar" }));

    expect(await screen.findByText("El texto no puede venir vacío.")).toBeInTheDocument();
  });
});
