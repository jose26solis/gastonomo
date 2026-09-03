"""Lecturas de Compra que no encajan en ConciliacionService (que solo escribe)."""

from app.business.errors import RecursoNoEncontrado
from app.data.models.compra import Compra
from app.data.repositories.compra_repository import CompraRepository
from app.data.repositories.usuario_repository import UsuarioRepository


class CompraService:
    """Consultas de compras reales ya conciliadas."""

    def __init__(
        self, compra_repository: CompraRepository, usuario_repository: UsuarioRepository
    ) -> None:
        self.compras = compra_repository
        self.usuarios = usuario_repository

    def obtener_del_titular(self, usuario_id: int, compra_id: int) -> Compra:
        """La compra, solo si pertenece al titular indicado.

        Es la validación que impide que un titular vea la bitácora de la
        compra de otra persona pasando un id ajeno -Mongo, a diferencia de
        PostgreSQL, no tiene ninguna noción de "de quién es esto" propia.
        """
        compra = self.compras.obtener_de_usuario(compra_id, usuario_id)
        if compra is None:
            raise RecursoNoEncontrado(f"La compra {compra_id} no existe en esta cuenta.")
        return compra
