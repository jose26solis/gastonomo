import { describe, expect, it } from "vitest";
import { formatearFechaCorta, formatearFechaHora, formatearMes, formatearMonto } from "./formato";

describe("formatearMonto", () => {
  it("antepone el símbolo de la moneda y usa dos decimales", () => {
    expect(formatearMonto(1549.1, "CRC")).toBe("₡1,549.10");
  });

  it("separa los miles con coma", () => {
    expect(formatearMonto(1234567.89, "USD")).toBe("$1,234,567.89");
  });

  it("usa un signo menos (no un paréntesis) para los montos negativos", () => {
    expect(formatearMonto(-3200, "CRC")).toBe("−₡3,200.00");
  });

  it("cero no lleva signo", () => {
    expect(formatearMonto(0, "CRC")).toBe("₡0.00");
  });

  it("cae al código de la moneda cuando no tiene símbolo conocido", () => {
    expect(formatearMonto(10, "GBP")).toBe("GBP 10.00");
  });
});

describe("formatearMes", () => {
  it("abrevia el mes a tres letras en minúscula", () => {
    expect(formatearMes(2026, 8)).toBe("ago 2026");
  });

  it("enero es el primer índice, no el cero", () => {
    expect(formatearMes(2026, 1)).toBe("ene 2026");
  });

  it("diciembre es el último", () => {
    expect(formatearMes(2026, 12)).toBe("dic 2026");
  });
});

describe("formatearFechaCorta", () => {
  it("muestra el día y el mes abreviado, sin el año", () => {
    expect(formatearFechaCorta("2026-08-30T13:27:00")).toBe("30 ago");
  });
});

describe("formatearFechaHora", () => {
  it("incluye día, mes abreviado y hora", () => {
    const resultado = formatearFechaHora("2026-08-30T13:27:00");
    expect(resultado).toContain("30 ago");
    expect(resultado).toMatch(/\d{1,2}:\d{2}/);
  });
});
