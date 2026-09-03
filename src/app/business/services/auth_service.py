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
from dataclasses import dataclass

from app.business.errors import CredencialesInvalidas, DatosInvalidos, ReglaDeNegocioViolada
from app.business.seguridad.cifrado import TokenIlegible, cifrar, descifrar
from app.business.seguridad.contrasenas import hashear_contrasena, verificar_contrasena
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

    def __init__(self, usuario_repository: UsuarioRepository) -> None:
        self.usuarios = usuario_repository

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
        if usuario is None or not verificar_contrasena(comando.contrasena, usuario.contrasena_hash):
            raise CredencialesInvalidas("El correo o la contraseña no son correctos.")
        if not usuario.activo:
            raise CredencialesInvalidas("El correo o la contraseña no son correctos.")
        return Sesion(token=self._token_de(usuario), usuario=usuario)

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
