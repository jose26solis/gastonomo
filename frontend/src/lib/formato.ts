const NOMBRES_MES = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "set", "oct", "nov", "dic",
]; // fmt: skip

const SIMBOLO_MONEDA: Record<string, string> = {
  CRC: "₡",
  USD: "$",
  EUR: "€",
};

/** `1549.1, "CRC"` -> `"₡1,549.10"`. Nunca mezcla monedas: cada total ya viene separado por moneda. */
export function formatearMonto(monto: number, moneda: string): string {
  const simbolo = SIMBOLO_MONEDA[moneda] ?? moneda + " ";
  const texto = Math.abs(monto).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (monto < 0 ? "−" : "") + simbolo + texto;
}

/** `2026, 8` -> `"ago 2026"`. */
export function formatearMes(anio: number, mes: number): string {
  return `${NOMBRES_MES[mes - 1]} ${anio}`;
}

/** `"2026-08-30T13:27:00"` -> `"30 ago"`. */
export function formatearFechaCorta(iso: string): string {
  const fecha = new Date(iso);
  return `${fecha.getDate()} ${NOMBRES_MES[fecha.getMonth()]}`;
}

/** `"2026-08-30T13:27:00Z"` -> `"30 ago, 07:27 a. m."`. Para la bitácora de
 * una compra, donde el orden de los eventos importa tanto como el día. */
export function formatearFechaHora(iso: string): string {
  const fecha = new Date(iso);
  const hora = fecha.toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" });
  return `${fecha.getDate()} ${NOMBRES_MES[fecha.getMonth()]}, ${hora}`;
}
