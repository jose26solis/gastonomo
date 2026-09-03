"""Registro, inicio de sesión y verificación de la sesión de un titular.

El token de sesión reusa el mismo mecanismo que ya protege el `state` del
handshake de OAuth2 (`cuentas_correo.py`): Fernet, con la misma clave
simétrica (`GASTONOMO_CLAVE_CIFRADO_TOKENS`) y un `ttl_segundos` en el
descifrado en vez de una fecha de expiración guardada aparte. No hace falta
una tabla de sesiones ni una librería de JWT -el propio Fernet ya firma y
cifra el contenido, y ya sabe rechazar un token vencido.

Es información suficiente para no necesitar guardar nada del lado del
servidor: el token *es* la sesión. Cerrar sesión es responsabilidad del
cliente (borrar el token guardado) -no hay como "revocar" uno ya emitido
antes de que expire por su cuenta, la misma limitación que tiene cualquier
JWT sin lista de revocación.
"""

import json
import secrets
from dataclasses import dataclass

from app.business.errors import CredencialesInvalidas, DatosInvalidos, ReglaDeNegocioViolada
from app.business.seguridad.cifrado import TokenIlegible, cifrar, descifrar
from app.business.seguridad.contrasenas import hashear_contrasena, verificar_contrasena
from app.business.services.identidad_google import IdentidadGoogleProveedor
from app.data.models.usuario import Usuario
from app.data.repositories.usuario_repository import UsuarioRepository

# 30 días: una sesión de un tracker de gastos personal, en un solo
# dispositivo, no necesita expirar cada pocas horas como la de un banco. El
# costo de una sesión larga es que un dispositivo robado o compartido queda
# con acceso más tiempo -aceptable acá, donde lo que hay detrás son gastos
# clasificados, no dinero movible.
_TTL_SESION_SEGUNDOS = 60 * 60 * 24 * 30

_LARGO_MINIMO_CONTRASENA = 8

# Ver la nota equivalente en `cuentas_correo.py`: sin este campo, el `state`
# de un handshake de OAuth2 -de vida mucho más corta, pero con la misma
# forma de JSON y la misma clave de cifrado- serviría como token de sesión
# válido mientras no venciera.
_PROPOSITO_SESION = "sesion"

# Dos "state" distintos para Google, con el mismo motivo de siempre -que no
# se puedan confundir entre sí ni con ningún otro token cifrado con esta
# misma clave. "Iniciar sesión con Google" es público: todavía no hay
# titular identificado, así que el state solo lleva un nonce anti-CSRF.
# "Vincular Google" (desde Ajustes, ya logueado) sí lleva el usuario_id,
# igual que el `state` de vincular un buzón en `cuentas_correo.py` -es la
# única forma en que el callback, que no recibe ningún encabezado de sesión,
# sabe a quién pertenece.
_PROPOSITO_LOGIN_GOOGLE = "login-google"
_PROPOSITO_VINCULAR_GOOGLE = "vincular-google"
_TTL_ESTADO_GOOGLE_SEGUNDOS = 600  # 10 minutos: de sobra para el handshake, poco para reusar


@dataclass(frozen=True)
class RegistrarUsuarioComando:
    """Datos que llegan del formulario de registro."""

    nombre_completo: str
    correo: str
    contrasena: str


@dataclass(frozen=True)
class IniciarSesionComando:
    """Datos que llegan del formulario de login."""

    correo: str
    contrasena: str


@dataclass(frozen=True)
class Sesion:
    """Lo que se le devuelve al cliente tras registrarse o iniciar sesión."""

    token: str
    usuario: Usuario


class AuthService:
    """Aplica las reglas de registro y autenticación de un titular."""

    def __init__(
        self,
        usuario_repository: UsuarioRepository,
        google: IdentidadGoogleProveedor | None = None,
    ) -> None:
        self.usuarios = usuario_repository
        # Opcional a propósito, igual que los proveedores de correo: sin
        # credenciales de Google configuradas, el resto del login sigue
        # funcionando -solo fallan los tres endpoints de /api/auth/google.
        self.google = google

    def registrar(self, comando: RegistrarUsuarioComando) -> Sesion:
        """Crea la cuenta y devuelve una sesión ya iniciada -no hace falta loguearse aparte."""
        nombre_completo = comando.nombre_completo.strip()
        correo = _normalizar_correo(comando.correo)

        if not nombre_completo:
            raise DatosInvalidos("El nombre no puede venir vacío.")
        if "@" not in correo or correo.startswith("@") or correo.endswith("@"):
            raise DatosInvalidos("El correo no es válido.")
        if len(comando.contrasena) < _LARGO_MINIMO_CONTRASENA:
            raise DatosInvalidos(
                f"La contraseña debe tener al menos {_LARGO_MINIMO_CONTRASENA} caracteres."
            )
        if self.usuarios.buscar_por_correo(correo) is not None:
            # Mismo motivo que en iniciar_sesion: no distinguir el mensaje
            # revelaría que ese correo específico ya tiene cuenta. Acá sí
            # hace falta ser un poco más explícito -"and now what?"- porque
            # a diferencia del login, quien registra sabe que ese correo es
            # el suyo; no hay nada que ocultarle a él mismo.
            raise ReglaDeNegocioViolada(f"Ya existe una cuenta con el correo {correo}.")

        usuario = Usuario(
            nombre_completo=nombre_completo,
            correo=correo,
            contrasena_hash=hashear_contrasena(comando.contrasena),
        )
        self.usuarios.agregar(usuario)
        self.usuarios.sesion.commit()
        return Sesion(token=self._token_de(usuario), usuario=usuario)

    def iniciar_sesion(self, comando: IniciarSesionComando) -> Sesion:
        """Verifica correo y contraseña, y devuelve una sesión nueva."""
        usuario = self.usuarios.buscar_por_correo(_normalizar_correo(comando.correo))
        # `contrasena_hash is None` cubre una cuenta creada solo con Google:
        # no tiene nada que verificar, y `verificar_contrasena` reventaría
        # con un `None` en vez de dar el mismo error parejo de siempre.
        if (
            usuario is None
            or usuario.contrasena_hash is None
            or not verificar_contrasena(comando.contrasena, usuario.contrasena_hash)
        ):
            raise CredencialesInvalidas("El correo o la contraseña no son correctos.")
        if not usuario.activo:
            raise CredencialesInvalidas("El correo o la contraseña no son correctos.")
        return Sesion(token=self._token_de(usuario), usuario=usuario)

    def url_de_inicio_sesion_google(self) -> str:
        """Arma la URL de Google para "Iniciar sesión con Google".

        A diferencia del `state` de vincular un buzón, este no lleva ningún
        `usuario_id` -nadie está identificado todavía, es justamente lo que
        este flujo va a resolver. Lleva un nonce solo para que el `state`
        no sea predecible y sirva de protección CSRF real.
        """
        estado = cifrar(
            json.dumps({"proposito": _PROPOSITO_LOGIN_GOOGLE, "nonce": secrets.token_urlsafe(16)})
        )
        return self._proveedor_google().url_de_autorizacion(estado)

    def iniciar_sesion_con_google(self, codigo: str, estado: str) -> Sesion:
        """Resuelve o crea la cuenta del titular detrás de esa cuenta de Google.

        Si ya existía una cuenta local con ese correo pero todavía sin
        vincular, no se linkea sola: nadie confirmó que quien tiene la
        cuenta de Google ahora mismo sea la misma persona dueña de esa
        contraseña. Vincular es un paso explícito, ya logueado, desde
        Ajustes (`vincular_google`).
        """
        self._verificar_estado_google(estado, _PROPOSITO_LOGIN_GOOGLE)
        perfil = self._proveedor_google().perfil_desde_codigo(codigo)
        if not perfil.correo_verificado:
            raise DatosInvalidos("Google no confirmó ese correo electrónico.")

        usuario = self.usuarios.buscar_por_google_id(perfil.id)
        if usuario is None:
            correo = _normalizar_correo(perfil.correo)
            if self.usuarios.buscar_por_correo(correo) is not None:
                raise ReglaDeNegocioViolada(
                    f"Ya existe una cuenta con el correo {correo}. Iniciá sesión con tu "
                    "contraseña y vinculá Google desde Ajustes."
                )
            usuario = Usuario(
                nombre_completo=perfil.nombre.strip() or correo,
                correo=correo,
                contrasena_hash=None,
                google_id=perfil.id,
            )
            self.usuarios.agregar(usuario)
            self.usuarios.sesion.commit()

        if not usuario.activo:
            raise CredencialesInvalidas("Esta cuenta está desactivada.")
        return Sesion(token=self._token_de(usuario), usuario=usuario)

    def url_de_vinculacion_google(self, usuario_id: int) -> str:
        """Arma la URL de Google para vincular Google a una cuenta ya logueada."""
        estado = cifrar(
            json.dumps({"proposito": _PROPOSITO_VINCULAR_GOOGLE, "usuario_id": usuario_id})
        )
        return self._proveedor_google().url_de_autorizacion(estado)

    def vincular_google(self, codigo: str, estado: str) -> Usuario:
        usuario_id = self._verificar_estado_google(estado, _PROPOSITO_VINCULAR_GOOGLE)
        assert usuario_id is not None  # este propósito siempre lo lleva

        perfil = self._proveedor_google().perfil_desde_codigo(codigo)
        if not perfil.correo_verificado:
            raise DatosInvalidos("Google no confirmó ese correo electrónico.")

        usuario = self.usuarios.obtener_por_id(usuario_id)
        if usuario is None:
            raise CredencialesInvalidas("La sesión no es válida o expiró.")

        ya_vinculada = self.usuarios.buscar_por_google_id(perfil.id)
        if ya_vinculada is not None and ya_vinculada.id != usuario.id:
            raise ReglaDeNegocioViolada("Esa cuenta de Google ya está vinculada a otro titular.")

        usuario.google_id = perfil.id
        self.usuarios.sesion.commit()
        return usuario

    def desvincular_google(self, usuario: Usuario) -> Usuario:
        """Quita Google como método de acceso -nunca si es el único que le queda al titular."""
        if usuario.contrasena_hash is None:
            raise ReglaDeNegocioViolada(
                "Google es tu único método de acceso: poné una contraseña antes de desvincularlo."
            )
        usuario.google_id = None
        self.usuarios.sesion.commit()
        return usuario

    def cambiar_contrasena(
        self, usuario: Usuario, contrasena_actual: str | None, contrasena_nueva: str
    ) -> None:
        """Cambia la contraseña, o le pone una por primera vez a una cuenta que llegó por Google.

        Si el titular ya tenía contraseña, exige la actual -sin eso, alguien
        que robó una sesión activa (el token de 30 días, por ejemplo) podría
        secuestrar la cuenta por completo con solo cambiarle la contraseña.
        Si todavía no tenía ninguna (`contrasena_hash is None`, una cuenta
        de solo-Google), no hay nada previo que confirmar.
        """
        if usuario.contrasena_hash is not None and (
            contrasena_actual is None
            or not verificar_contrasena(contrasena_actual, usuario.contrasena_hash)
        ):
            raise CredencialesInvalidas("La contraseña actual no es correcta.")
        if len(contrasena_nueva) < _LARGO_MINIMO_CONTRASENA:
            raise DatosInvalidos(
                f"La contraseña debe tener al menos {_LARGO_MINIMO_CONTRASENA} caracteres."
            )
        usuario.contrasena_hash = hashear_contrasena(contrasena_nueva)
        self.usuarios.sesion.commit()

    def actualizar_preferencia_sinpe(self, usuario: Usuario, activo: bool) -> Usuario:
        """Prende o apaga la lectura de transferencias SINPE para este titular.

        Es el interruptor "Leer transferencias SINPE" de Ajustes.
        `CuentaCorreoService.transferencias_sinpe_de_usuario` respeta esta
        bandera antes de tocar la red -ver la nota en ese método.
        """
        usuario.leer_transferencias_sinpe = activo
        self.usuarios.sesion.commit()
        return usuario

    def _proveedor_google(self) -> IdentidadGoogleProveedor:
        if self.google is None:
            raise DatosInvalidos("Iniciar sesión con Google no está configurado en este servidor.")
        return self.google

    def _verificar_estado_google(self, estado: str, proposito_esperado: str) -> int | None:
        """Descifra y valida un `state` de Google, devolviendo el `usuario_id` si lo lleva.

        El mismo error para cualquier motivo de rechazo -mal formado, de
        otro propósito, vencido- por lo mismo que en `usuario_de_token`:
        nadie que llegue hasta acá necesita distinguir el porqué exacto.
        """
        try:
            datos = json.loads(descifrar(estado, ttl_segundos=_TTL_ESTADO_GOOGLE_SEGUNDOS))
            if datos.get("proposito") != proposito_esperado:
                raise ValueError("proposito de state inesperado")
            usuario_id = datos.get("usuario_id")
            return int(usuario_id) if usuario_id is not None else None
        except (TokenIlegible, ValueError, KeyError, TypeError) as error:
            raise DatosInvalidos("El enlace de Google no es válido o expiró.") from error

    def usuario_de_token(self, token: str) -> Usuario:
        """Resuelve el titular dueño de un token de sesión. Lanza CredencialesInvalidas si no calza.

        Cubre todos los motivos por los que un token puede no servir -mal
        formado, cifrado con otra clave, vencido, de otro propósito, de un
        usuario que ya no existe o que fue desactivado- con el mismo error:
        quien llama solo necesita saber "esta sesión no sirve, hay que
        volver a loguearse", no por qué exactamente.
        """
        try:
            datos = json.loads(descifrar(token, ttl_segundos=_TTL_SESION_SEGUNDOS))
            if datos.get("proposito") != _PROPOSITO_SESION:
                raise ValueError("no es un token de sesión")
            usuario_id = int(datos["usuario_id"])
        except (TokenIlegible, ValueError, KeyError, TypeError) as error:
            raise CredencialesInvalidas("La sesión no es válida o expiró.") from error

        usuario = self.usuarios.obtener_por_id(usuario_id)
        if usuario is None or not usuario.activo:
            raise CredencialesInvalidas("La sesión no es válida o expiró.")
        return usuario

    def _token_de(self, usuario: Usuario) -> str:
        return cifrar(json.dumps({"usuario_id": usuario.id, "proposito": _PROPOSITO_SESION}))


def _normalizar_correo(correo: str) -> str:
    """Minúsculas y sin espacios: `Ana@Gmail.com` y `ana@gmail.com` son la misma cuenta."""
    return correo.strip().lower()
