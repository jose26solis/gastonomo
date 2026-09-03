/**
 * Se carga una vez antes de toda la suite (ver `vite.config.ts` -> `test.setupFiles`).
 *
 * `@testing-library/jest-dom` agrega matchers como `toBeInTheDocument()` -sin
 * este import, cada prueba tendría que revisar el DOM a mano en vez de con
 * aserciones legibles.
 */
import "@testing-library/jest-dom/vitest";
