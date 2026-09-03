"""Bitácora de trazabilidad de una compra, en MongoDB.

Escribe en la colección `bitacora_compras` -mismo validador de 13 tipos de
evento que ya define `db/mongo/init/01_bitacora_compras.js` para el
Laboratorio 2 (`TIPOS_DE_EVENTO` de abajo es la misma lista, no una nueva)-
pero ahora desde la aplicación que corre de verdad, disparada por
`ConciliacionService` en vez de solo por el seed académico.

Nunca bloquea la conciliación en PostgreSQL: cualquier fallo de conexión o de
escritura a Mongo se traga y no revienta la transacción de negocio. Es el
mismo trade-off que documenta ADR-002 -la bitácora **explica** lo que pasó,
no lo **decide**; ningún saldo ni ningún total del sistema depende de ella.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

_registro = logging.getLogger(__name__)

# Vocabulario cerrado, idéntico al validador de Mongo. Un tipo que no esté
# acá nunca debería intentar escribirse -si hiciera falta uno nuevo, primero
# se agrega ahí y aquí a la vez.
TIPOS_DE_EVENTO = (
    "INGESTA_RECIBIDA",
    "PARSEO_COMPROBANTE",
    "EMPAREJAMIENTO_METODO_PAGO",
    "RESOLUCION_COMERCIO",
    "CATEGORIZACION_AUTOMATICA",
    "CORRECCION_MANUAL",
    "DESGLOSE_MANUAL",
    "CONVERSION_MONEDA",
    "IMPACTO_PRESUPUESTO",
    "ALERTA_PRESUPUESTO",
    "CAMBIO_ESTADO",
    "REVISION_REQUERIDA",
    "ANULACION",
)


@dataclass(frozen=True)
class Actor:
    """Quién provocó el evento: una persona, la ingesta, o una regla que se disparó sola."""

    tipo: str  # "TITULAR" | "SERVICIO" | "SISTEMA"
    usuario_id: int | None = None
    nombre: str | None = None


class BitacoraComprasService:
    """Agrega eventos a la bitácora de una compra, tolerando que Mongo no responda.

    `coleccion` puede ser `None` -por ejemplo si Mongo no está configurado en
    este ambiente- y el servicio simplemente no escribe nada, en vez de
    exigir que todo el sistema sepa de Mongo para poder arrancar.
    """

    def __init__(self, coleccion: Collection | None) -> None:
        self._coleccion = coleccion

    def registrar_evento(
        self,
        compra_id: int,
        usuario_id: int,
        estado_actual: str,
        tipo: str,
        datos: dict[str, Any],
        actor: Actor,
    ) -> None:
        """Agrega un evento a la bitácora de `compra_id`, creándola si es el primero.

        No propaga ninguna excepción: un Mongo caído o una escritura
        rechazada quedan solo en el log, nunca revierten lo que ya se
        confirmó en PostgreSQL.
        """
        if self._coleccion is None:
            return
        if tipo not in TIPOS_DE_EVENTO:
            raise ValueError(f"Tipo de evento desconocido: {tipo!r}")

        ahora = datetime.now(UTC)
        evento = {
            "secuencia": self._siguiente_secuencia(compra_id),
            "tipo": tipo,
            "ocurrido_en": ahora,
            "actor": {"tipo": actor.tipo, "usuario_id": actor.usuario_id, "nombre": actor.nombre},
            "datos": datos,
        }
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
                tipo,
                compra_id,
                exc_info=True,
            )

    def bitacora_de(self, compra_id: int) -> list[dict[str, Any]] | None:
        """Los eventos de una compra, en el orden en que ocurrieron. `None` si no hay Mongo
        disponible o la compra todavía no tiene ningún evento."""
        if self._coleccion is None:
            return None
        try:
            documento = self._coleccion.find_one({"compra_id": compra_id})
        except PyMongoError:
            _registro.warning(
                "No se pudo leer la bitácora de la compra %s.", compra_id, exc_info=True
            )
            return None
        return documento.get("eventos") if documento else None

    def _siguiente_secuencia(self, compra_id: int) -> int:
        try:
            documento = self._coleccion.find_one({"compra_id": compra_id}, {"eventos": 1})
        except PyMongoError:
            return 1
        if documento is None:
            return 1
        return len(documento.get("eventos", [])) + 1
