"""BitacoraRepository: acceso crudo a la colección de Mongo `bitacora_compras`.

No hereda de `BaseRepository`: ese genérico está parametrizado sobre una
entidad de SQLAlchemy y su contrato es el de una sesión transaccional -agregar
sin confirmar, el `commit` lo hace el servicio que sabe si la operación de
negocio completa terminó bien. Mongo acá no tiene ni sesión ni transacción:
cada escritura es su propia operación atómica sobre un documento. Comparte con
`BaseRepository` la posición en la arquitectura -es la capa de datos, y
`BitacoraComprasService` no importa `pymongo` en ningún lado- pero no puede
compartir esa implementación.

El servicio decide **qué** evento se registra (valida el tipo, arma el
documento); este repositorio solo sabe **cómo** se guarda. Por eso tolera acá
-y no en el servicio- que `coleccion` sea `None` (Mongo no configurado en este
ambiente) y que cualquier operación falle por conexión: nunca propaga, solo
devuelve sin escribir ni leer nada. Es el mismo trade-off que documenta
ADR-002 -la bitácora **explica** lo que pasó, no lo **decide**; ningún saldo
ni ningún total del sistema depende de ella.
"""

import logging
from datetime import datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

_registro = logging.getLogger(__name__)


class BitacoraRepository:
    """Lecturas y escrituras crudas de la bitácora de trazabilidad, en Mongo."""

    def __init__(self, coleccion: Collection | None) -> None:
        self._coleccion = coleccion

    def agregar_evento(
        self,
        compra_id: int,
        usuario_id: int,
        estado_actual: str,
        ahora: datetime,
        evento: dict[str, Any],
    ) -> None:
        """Agrega `evento` al documento de `compra_id`, creándolo si es el primero."""
        if self._coleccion is None:
            return
        try:
            self._coleccion.update_one(
                {"compra_id": compra_id},
                {
                    "$setOnInsert": {
                        "compra_id": compra_id,
                        "usuario_id": usuario_id,
                        "abierta_en": ahora,
                    },
                    "$set": {"estado_actual": estado_actual, "actualizada_en": ahora},
                    "$push": {"eventos": evento},
                },
                upsert=True,
            )
        except PyMongoError:
            _registro.warning(
                "No se pudo escribir el evento %s de la compra %s en la bitácora de Mongo.",
                evento.get("tipo"),
                compra_id,
                exc_info=True,
            )

    def obtener(self, compra_id: int) -> dict[str, Any] | None:
        """El documento completo de `compra_id`, o `None` si no existe o Mongo no responde."""
        if self._coleccion is None:
            return None
        try:
            return self._coleccion.find_one({"compra_id": compra_id})
        except PyMongoError:
            _registro.warning(
                "No se pudo leer la bitácora de la compra %s.", compra_id, exc_info=True
            )
            return None

    def contar_eventos(self, compra_id: int) -> int:
        """Cuántos eventos tiene ya `compra_id` -0 si no tiene documento todavía,
        no hay Mongo, o Mongo no responde. Es lo que arma la siguiente secuencia."""
        if self._coleccion is None:
            return 0
        try:
            documento = self._coleccion.find_one({"compra_id": compra_id}, {"eventos": 1})
        except PyMongoError:
            return 0
        if documento is None:
            return 0
        return len(documento.get("eventos", []))
