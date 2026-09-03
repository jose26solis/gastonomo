import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Empaqueta el mismo frontend de React -sin reescribir nada- en un shell
 * nativo instalable en App Store y Play Store. `webDir` apunta al build de
 * producción (`npm run build`): Capacitor copia ese `dist/` dentro del
 * proyecto nativo y lo sirve localmente, no desde un servidor remoto -así
 * la app abre al instante y funciona sin conexión para todo lo que no
 * necesite el backend (login, sincronizar correo, sí lo necesitan).
 *
 * `appId` es un placeholder: tiene que ser el identificador real que se
 * registre en App Store Connect y en Play Console antes de publicar -useq
 * cambia esto, junto con los recursos de `recursos-nativos/`, cuando esas
 * cuentas existan. Cambiarlo después de la primera publicación en cualquiera
 * de las dos tiendas requiere subir la app como una ficha nueva, no una
 * actualización.
 */
const config: CapacitorConfig = {
  appId: "com.gastonomo.app",
  appName: "Gastonomo",
  webDir: "dist",
  backgroundColor: "#161826",
};

export default config;
