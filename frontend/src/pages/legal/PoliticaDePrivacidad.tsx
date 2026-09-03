import { LegalLayout, Seccion } from "./LegalLayout";

/**
 * Política de privacidad real y accesible sin sesión -no una plantilla
 * genérica. Describe exactamente lo que el código hace hoy, campo por campo
 * (ver `Comprobante` en el backend y "Qué lee Gastonomo" en
 * `ConectarCorreo.tsx`), no lo que "cualquier app haría". Un texto que
 * promete más de lo que el sistema hace es peor que no tener política: es
 * la base de la verificación de apps de Google y de la revisión de las
 * tiendas, y tiene que aguantar que alguien la compare contra el código.
 */
export function PoliticaDePrivacidad() {
  return (
    <LegalLayout titulo="Política de privacidad" actualizado="3 de setiembre de 2026">
      <Seccion titulo="Qué es Gastonomo">
        <p>
          Gastonomo es una aplicación de control de gastos personales. Lee las notificaciones de
          compra que el banco ya te manda por correo, extrae los datos de cada transacción y los
          organiza por categoría y presupuesto -no te pide que anotes nada a mano.
        </p>
      </Seccion>

      <Seccion titulo="Qué datos recopilamos">
        <p>
          <strong>De tu cuenta:</strong> nombre, correo y contraseña. La contraseña se guarda
          siempre como un hash (bcrypt) -ni nosotros ni nadie con acceso a la base de datos puede
          leerla en su forma original.
        </p>
        <p>
          <strong>De un buzón de correo que vincules (Outlook o Gmail):</strong> un token de acceso
          cifrado que nos deja leer, en tu nombre, solo los correos que cumplen los dos filtros de
          abajo. El token se guarda cifrado (AES/Fernet); nunca tu contraseña de Microsoft o de
          Google, que jamás pasa por nuestros servidores -la autenticación la hace directamente el
          proveedor.
        </p>
        <p>
          <strong>De cada correo que leemos,</strong> solo si viene de un dominio de BAC Credomatic:
          la fecha, el comercio, el monto, la moneda, la ciudad y el país de la compra, la marca y
          los últimos 4 dígitos de la tarjeta, y el número de autorización. Es lo único que se
          guarda -el cuerpo del correo se descarta después de leer esos campos, no se archiva.
        </p>
        <p>
          <strong>Lo que vos creás dentro de la app:</strong> tus categorías, tus presupuestos, y la
          categoría que le asignes a cada comercio.
        </p>
      </Seccion>

      <Seccion titulo="Qué NO leemos ni guardamos">
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>Correos personales, conversaciones o cualquier mensaje que no sea de BAC Credomatic</li>
          <li>Adjuntos de ningún correo</li>
          <li>Contactos, calendario ni archivos de tu cuenta de Microsoft o Google</li>
          <li>El asunto ni el cuerpo completo de un correo, más allá de los campos ya listados</li>
        </ul>
      </Seccion>

      <Seccion titulo="Con quién compartimos datos">
        <p>
          Con nadie, para fines de publicidad o venta -no compartimos ni vendemos tus datos a
          terceros. Los únicos servicios externos que se tocan son:
        </p>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>Microsoft y Google, para autenticarte y leer el buzón que vos autorizaste</li>
          <li>
            El Banco Central de Costa Rica (o, de respaldo, el Ministerio de Hacienda), para el
            tipo de cambio de referencia -esa consulta no envía ningún dato tuyo, solo pide una
            tasa pública
          </li>
        </ul>
      </Seccion>

      <Seccion titulo="Cuánto tiempo guardamos tus datos">
        <p>
          Mientras tu cuenta exista. Desvincular un buzón borra sus tokens de inmediato -deja de
          poder leerse- pero conserva el historial de transacciones ya sincronizadas, para no
          perder tu resumen de gastos pasados.
        </p>
      </Seccion>

      <Seccion titulo="Tus derechos sobre tus datos">
        <p>
          Podés pedir ver, corregir o eliminar tus datos, o eliminar tu cuenta por completo,
          escribiéndonos a{" "}
          <a href="mailto:soporte@gastonomo.app" style={{ color: "var(--color-accent-200)" }}>
            soporte@gastonomo.app
          </a>
          . Hoy ese pedido lo procesamos manualmente -todavía no hay un botón de autoservicio
          dentro de la app para borrar la cuenta.
        </p>
      </Seccion>

      <Seccion titulo="Seguridad">
        <p>
          Las contraseñas se hashean con bcrypt. Los tokens de acceso a tu correo se cifran con
          AES (Fernet) antes de guardarse. Las sesiones vencen a los 30 días. En producción, toda
          la comunicación con el servidor viaja cifrada (HTTPS).
        </p>
      </Seccion>

      <Seccion titulo="Menores de edad">
        <p>Gastonomo no está dirigida a menores de 13 años, y no recopila datos a sabiendas de ellos.</p>
      </Seccion>

      <Seccion titulo="Cambios a esta política">
        <p>
          Si cambia de forma importante, lo vamos a avisar dentro de la app antes de que el cambio
          entre en vigencia.
        </p>
      </Seccion>

      <Seccion titulo="Contacto">
        <p>
          <a href="mailto:soporte@gastonomo.app" style={{ color: "var(--color-accent-200)" }}>
            soporte@gastonomo.app
          </a>
        </p>
      </Seccion>
    </LegalLayout>
  );
}
