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

/** `"2026-08-30T13:27:00"` (o `"2026-08-30"`, sin hora) -> `"30 ago"`.
 *
 * Lee el día y el mes directo del texto, sin pasar por `new Date(iso)`: un
 * `date` sin hora (lo que manda `Compra.fecha`) lo interpreta el motor de
 * JavaScript como medianoche UTC, y `getDate()`/`getMonth()` lo devuelven en
 * hora local -en Costa Rica (UTC-6) esa resta corre el día uno hacia atrás,
 * mostrando "4 set" para una compra del 5. Los primeros diez caracteres son
 * siempre `AAAA-MM-DD` tanto si el texto trae hora como si no, así que
 * tomarlos tal cual evita la conversión de por medio.
 */
export function formatearFechaCorta(iso: string): string {
  const [, mes, dia] = iso.slice(0, 10).split("-").map(Number);
  return `${dia} ${NOMBRES_MES[mes - 1]}`;
}

/** `"2026-08-30T13:27:00Z"` -> `"30 ago, 07:27 a. m."`. Para la bitácora de
 * una compra, donde el orden de los eventos importa tanto como el día. */
export function formatearFechaHora(iso: string): string {
  const fecha = new Date(iso);
  const hora = fecha.toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" });
  return `${fecha.getDate()} ${NOMBRES_MES[fecha.getMonth()]}, ${hora}`;
}
