"""Reglas de negocio de las cuentas de correo vinculadas."""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.business.errors import RecursoNoEncontrado, ReglaDeNegocioViolada
from app.business.seguridad.cifrado import cifrar, descifrar
from app.business.services.correo.proveedor import MensajeResumido, ProveedorDeCorreo
from app.data.models.cuenta_correo import CuentaCorreo
from app.data.models.enums import EstadoCuentaCorreo, ProveedorCorreo
from app.data.repositories.cuenta_correo_repository import CuentaCorreoRepository
from app.data.repositories.usuario_repository import UsuarioRepository


@dataclass(frozen=True)
class VincularCuentaComando:
    """Orden que recibe el negocio tras volver del proveedor con un código."""

    usuario_id: int
    proveedor: ProveedorCorreo
    codigo: str


class CuentaCorreoService:
    """Aplica las reglas del dominio sobre los buzones vinculados de un titular.

    No sabe hablar HTTP con Microsoft ni con Google: eso lo hacen los
    `ProveedorDeCorreo` que recibe inyectados, uno por cada `ProveedorCorreo`
    que el sistema soporta. Este servicio solo decide qué hacer con lo que el
    proveedor devuelve -cifrar los tokens, crear o actualizar la cuenta,
    confirmar la transacción- y nunca con cuál proveedor específico habla.
    """

    def __init__(
        self,
        cuenta_correo_repository: CuentaCorreoRepository,
        usuario_repository: UsuarioRepository,
        proveedores: dict[ProveedorCorreo, ProveedorDeCorreo],
    ) -> None:
        self.cuentas = cuenta_correo_repository
        self.usuarios = usuario_repository
        self.proveedores = proveedores

    def url_de_autorizacion(self, usuario_id: int, proveedor: ProveedorCorreo, estado: str) -> str:
        """Arma la URL a la que se manda al titular para que autorice el acceso."""
        self._asegurar_usuario_activo(usuario_id)
        return self._proveedor(proveedor).url_de_autorizacion(estado)

    def vincular(self, comando: VincularCuentaComando) -> CuentaCorreo:
        """Cambia el código de autorización por tokens y crea o actualiza la cuenta.

        Vincular un buzón que ya estaba vinculado no duplica la fila: renueva
        sus tokens y la vuelve a marcar activa. Es lo que pasa, por ejemplo,
        cuando el titular reautoriza tras revocar el acceso desde su cuenta de
        Microsoft o Google.
        """
        self._asegurar_usuario_activo(comando.usuario_id)
        proveedor = self._proveedor(comando.proveedor)

        tokens = proveedor.intercambiar_codigo(comando.codigo)
        direccion = proveedor.obtener_direccion(tokens.token_acceso)

        cuenta = self.cuentas.buscar_por_direccion(comando.usuario_id, comando.proveedor, direccion)
        if cuenta is None:
            cuenta = CuentaCorreo(
                usuario_id=comando.usuario_id,
                proveedor=comando.proveedor,
                direccion=direccion,
            )

        cuenta.token_acceso_cifrado = cifrar(tokens.token_acceso)
        if tokens.token_refresco is not None:
            cuenta.token_refresco_cifrado = cifrar(tokens.token_refresco)
        cuenta.expira_en = tokens.expira_en
        cuenta.estado = EstadoCuentaCorreo.ACTIVA

        self.cuentas.agregar(cuenta)
        self.cuentas.sesion.commit()
        return cuenta

    def listar(self, usuario_id: int) -> list[CuentaCorreo]:
        """Lista los buzones vinculados de un titular."""
        self._asegurar_usuario_activo(usuario_id)
        return self.cuentas.listar_de_usuario(usuario_id)

    def probar_conexion(
        self, usuario_id: int, cuenta_id: int, limite: int = 5
    ) -> list[MensajeResumido]:
        """Trae los últimos mensajes del buzón para confirmar que el token sirve.

        No descarga el cuerpo de ningún mensaje -solo remitente, asunto y
        fecha- porque esto es una prueba de conexión, no la ingesta real. La
        ingesta que sí lee y descarta el contenido es un proceso aparte.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        token_acceso = self._token_acceso_vigente(cuenta)
        try:
            mensajes = self._proveedor(cuenta.proveedor).listar_mensajes_recientes(
                token_acceso, limite
            )
        except Exception:
            cuenta.estado = EstadoCuentaCorreo.ERROR
            self.cuentas.sesion.commit()
            raise
        cuenta.ultima_sincronizacion = datetime.now(UTC)
        self.cuentas.sesion.commit()
        return mensajes

    def desvincular(self, usuario_id: int, cuenta_id: int) -> None:
        """Desvincula un buzón sin borrar la cuenta del titular.

        Se limpian los tokens -ya no sirven de nada guardados, y son el dato
        más sensible de la fila- pero la fila se conserva en estado
        `DESVINCULADA` para que el historial de qué buzones tuvo alguna vez
        siga siendo consultable.
        """
        cuenta = self._obtener_cuenta_del_titular(usuario_id, cuenta_id)
        cuenta.token_acceso_cifrado = None
        cuenta.token_refresco_cifrado = None
        cuenta.estado = EstadoCuentaCorreo.DESVINCULADA
        self.cuentas.sesion.commit()

    def _token_acceso_vigente(self, cuenta: CuentaCorreo) -> str:
        if cuenta.estado == EstadoCuentaCorreo.DESVINCULADA:
            raise ReglaDeNegocioViolada(f"La cuenta {cuenta.id} ya fue desvinculada.")
        if cuenta.token_acceso_cifrado is None:
            raise ReglaDeNegocioViolada(f"La cuenta {cuenta.id} no tiene un token guardado.")

        ahora = datetime.now(UTC)
        vencido = cuenta.expira_en is not None and cuenta.expira_en <= ahora
        if not vencido:
            return descifrar(cuenta.token_acceso_cifrado)

        if cuenta.token_refresco_cifrado is None:
            cuenta.estado = EstadoCuentaCorreo.TOKEN_EXPIRADO
            self.cuentas.sesion.commit()
            raise ReglaDeNegocioViolada(
                f"El token de la cuenta {cuenta.id} vencio y no hay token de refresco; "
                "hay que volver a vincularla."
            )

        tokens = self._proveedor(cuenta.proveedor).refrescar(
            descifrar(cuenta.token_refresco_cifrado)
        )
        cuenta.token_acceso_cifrado = cifrar(tokens.token_acceso)
        if tokens.token_refresco is not None:
            cuenta.token_refresco_cifrado = cifrar(tokens.token_refresco)
        cuenta.expira_en = tokens.expira_en
        cuenta.estado = EstadoCuentaCorreo.ACTIVA
        self.cuentas.sesion.commit()
        return tokens.token_acceso

    def _obtener_cuenta_del_titular(self, usuario_id: int, cuenta_id: int) -> CuentaCorreo:
        self._asegurar_usuario_activo(usuario_id)
        cuenta = self.cuentas.obtener_de_usuario(cuenta_id, usuario_id)
        if cuenta is None:
            raise RecursoNoEncontrado(f"La cuenta de correo {cuenta_id} no existe en esta cuenta.")
        return cuenta

    def _proveedor(self, proveedor: ProveedorCorreo) -> ProveedorDeCorreo:
        return self.proveedores[proveedor]

    def _asegurar_usuario_activo(self, usuario_id: int) -> None:
        usuario = self.usuarios.obtener_por_id(usuario_id)
        if usuario is None:
            raise RecursoNoEncontrado(f"El usuario {usuario_id} no existe.")
        if not usuario.activo:
            raise ReglaDeNegocioViolada(f"El usuario {usuario_id} esta desactivado.")
