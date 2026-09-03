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

    def listar_de_usuario(self, usuario_id: int) -> list[Compra]:
        return list(
            self.sesion.scalars(
                select(Compra).where(Compra.usuario_id == usuario_id).order_by(Compra.fecha.desc())
            )
        )
