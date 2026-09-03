import { LegalLayout, Seccion } from "./LegalLayout";

export function TerminosDeUso() {
  return (
    <LegalLayout titulo="Términos de uso" actualizado="3 de setiembre de 2026">
      <Seccion titulo="Aceptación">
        <p>
          Al crear una cuenta en Gastonomo aceptás estos términos y nuestra{" "}
          <a href="/privacidad" style={{ color: "var(--color-accent-200)" }}>
            Política de privacidad
          </a>
          . Si no estás de acuerdo, no uses la aplicación.
        </p>
      </Seccion>

      <Seccion titulo="Qué es Gastonomo">
        <p>
          Una herramienta de organización de gastos personales que lee las notificaciones de
          compra de tu correo (hoy, de BAC Credomatic) y las clasifica. No es un banco, no es un
          agregador financiero regulado, no mueve dinero ni tiene acceso a tus cuentas bancarias
          -solo lee correos que vos autorizás explícitamente.
        </p>
      </Seccion>

      <Seccion titulo="Precisión de los datos, sin garantía">
        <p>
          Los montos y categorías se extraen automáticamente del texto de un correo. Un formato de
          notificación inusual, un correo reenviado, o un cambio que el banco haga en su plantilla
          pueden hacer que un monto se lea mal o que una compra no se reconozca. Gastonomo es una
          herramienta de apoyo para organizar tus gastos, no un registro contable ni fiscal
          oficial -para eso usá el estado de cuenta real de tu banco.
        </p>
      </Seccion>

      <Seccion titulo="Tu cuenta">
        <p>
          Sos responsable de mantener tu contraseña en privado y de todo lo que pase en tu cuenta.
          Avisanos si sospechás un acceso no autorizado.
        </p>
      </Seccion>

      <Seccion titulo="Uso aceptable">
        <p>No podés usar Gastonomo para:</p>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>Acceder o intentar acceder a la cuenta o los datos de otra persona</li>
          <li>Interferir con el funcionamiento del servicio o intentar vulnerar su seguridad</li>
          <li>Usar la aplicación de forma que viole alguna ley aplicable</li>
        </ul>
      </Seccion>

      <Seccion titulo="Cancelación">
        <p>
          Podés dejar de usar Gastonomo cuando quieras y pedir que se elimine tu cuenta y tus
          datos (ver la Política de privacidad). Nos reservamos el derecho de suspender una cuenta
          que viole estos términos.
        </p>
      </Seccion>

      <Seccion titulo="Sin garantía">
        <p>
          Gastonomo se ofrece "tal cual", sin garantía de disponibilidad continua ni de que vaya a
          estar libre de errores. No somos responsables por decisiones financieras que tomes
          basándote únicamente en los datos que la aplicación te muestra.
        </p>
      </Seccion>

      <Seccion titulo="Cambios a estos términos">
        <p>
          Si cambian de forma importante, lo vamos a avisar dentro de la app antes de que el
          cambio entre en vigencia.
        </p>
      </Seccion>

      <Seccion titulo="Contacto">
        <p>
          <a href="mailto:info@altiorasys.com" style={{ color: "var(--color-accent-200)" }}>
            info@altiorasys.com
          </a>
        </p>
      </Seccion>
    </LegalLayout>
  );
}
