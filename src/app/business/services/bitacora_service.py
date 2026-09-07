"""Bitácora de trazabilidad de una compra, en MongoDB.

Escribe en la colección `bitacora_compras` -mismo validador de 13 tipos de
evento que ya define `db/mongo/init/01_bitacora_compras.js` para el
Laboratorio 2 (`TIPOS_DE_EVENTO` de abajo es la misma lista, no una nueva)-
pero ahora desde la aplicación que corre de verdad, disparada por
`ConciliacionService` en vez de solo por el seed académico.

El acceso a Mongo en sí -`update_one`, `find_one`, tolerar que la colección
no esté disponible- vive en `BitacoraRepository` (`data/repositories/`), no
acá: este servicio solo decide qué evento se registra (valida el tipo, arma
el documento) y deja que el repositorio decida cómo se guarda. Nunca bloquea
la conciliación en PostgreSQL: cualquier fallo de conexión o de escritura a
Mongo se traga en el repositorio y no revienta la transacción de negocio. Es
el mismo trade-off que documenta ADR-002 -la bitácora **explica** lo que
pasó, no lo **decide**; ningún saldo ni ningún total del sistema depende de
ella.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.data.repositories.bitacora_repository import BitacoraRepository

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
    """Decide qué evento se registra en la bitácora de una compra.

    Recibe un `BitacoraRepository` -nunca `pymongo` directo- y solo valida el
    tipo de evento y arma el documento; el repositorio ya tolera que Mongo no
    esté configurado o no responda, así que este servicio no necesita saberlo.
    """

    def __init__(self, repositorio: BitacoraRepository) -> None:
        self.bitacora = repositorio

    def registrar_evento(
        self,
        compra_id: int,
        usuario_id: int,
        estado_actual: str,
        tipo: str,
        datos: dict[str, Any],
        actor: Actor,
    ) -> None:
        """Agrega un evento a la bitácora de `compra_id`, creándola si es el primero."""
        if tipo not in TIPOS_DE_EVENTO:
            raise ValueError(f"Tipo de evento desconocido: {tipo!r}")

        ahora = datetime.now(UTC)
        evento = {
            "secuencia": self.bitacora.contar_eventos(compra_id) + 1,
            "tipo": tipo,
            "ocurrido_en": ahora,
            "actor": {"tipo": actor.tipo, "usuario_id": actor.usuario_id, "nombre": actor.nombre},
            "datos": datos,
        }
        self.bitacora.agregar_evento(compra_id, usuario_id, estado_actual, ahora, evento)

    def bitacora_de(self, compra_id: int) -> list[dict[str, Any]] | None:
        """Los eventos de una compra, en el orden en que ocurrieron. `None` si no hay Mongo
        disponible o la compra todavía no tiene ningún evento."""
        documento = self.bitacora.obtener(compra_id)
        return documento.get("eventos") if documento else None
