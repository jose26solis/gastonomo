-- Agrega la bandera que distingue una transferencia leída con el lector
-- exacto de un banco (BAC, Banco Nacional) de una leída con el lector
-- genérico -patrones sueltos, para un banco sin lector propio todavía.
--
-- POR QUÉ ESTE ARCHIVO EXISTE
--
-- Mismo motivo que 001 y 003: `create_all()` no altera una tabla que ya
-- existe. `transferencia_sinpe` es nueva en 003; esta columna se agregó
-- después de que 003 ya podía estar corriendo en una base real, así que
-- necesita su propio script en vez de editar 003 -las migraciones de esta
-- carpeta nunca se reescriben una vez que existen, se suman.
--
-- Es idempotente: correrlo dos veces no hace nada la segunda vez.
--
--   docker compose exec -T postgres psql -U gastonomo -d gastonomo \
--     < db/postgres/esquema-aplicacion/004_confirmado_en_transferencia_sinpe.sql

ALTER TABLE transferencia_sinpe
    ADD COLUMN IF NOT EXISTS confirmado BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN transferencia_sinpe.confirmado IS
    'False si salio del lector generico (patrones sueltos: monto, cuenta IBAN, '
    'fecha, referencia) en vez de un lector validado contra una notificacion '
    'real de ese banco en particular. La pantalla lo marca para revisar.';
