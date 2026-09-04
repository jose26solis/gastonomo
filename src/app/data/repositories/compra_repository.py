"""Consultas de Compra."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models.compra import Compra
from app.data.repositories.base_repository import BaseRepository


class CompraRepository(BaseRepository[Compra]):
    """Acceso a las compras de un titular."""

    def __init__(self, sesion: Session) -> None:
        super().__init__(sesion, Compra)

    def obtener_de_usuario(self, identificador: int, usuario_id: int) -> Compra | None:
        return self.sesion.scalars(
            select(Compra).where(Compra.id == identificador, Compra.usuario_id == usuario_id)
        ).first()

    def listar_de_usuario(
        self, usuario_id: int, requiere_revision: bool | None = None, limite: int = 50
    ) -> list[Compra]:
        """Las compras del titular, más recientes primero.

        `requiere_revision` filtra por esa columna cuando no es `None` -es lo
        que arma la lista de "compras que necesitan revisión" sin traer todo
        el historial para filtrarlo en Python.
        """
        consulta = select(Compra).where(Compra.usuario_id == usuario_id)
        if requiere_revision is not None:
            consulta = consulta.where(Compra.requiere_revision.is_(requiere_revision))
        consulta = consulta.order_by(Compra.fecha.desc(), Compra.id.desc()).limit(limite)
        return list(self.sesion.scalars(consulta))
