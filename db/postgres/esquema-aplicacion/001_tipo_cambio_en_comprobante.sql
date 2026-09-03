-- Guarda, junto a cada comprobante, el tipo de cambio del día en que se
-- sincronizó, para poder convertirlo después sin una consulta histórica.
--
-- POR QUÉ ESTE ARCHIVO EXISTE
--
-- El esquema que usa la aplicación en ejecución no lo maneja Flyway: lo crea
-- SQLAlchemy con `Base.metadata.create_all` (ver `src/app/config/database.py`).
-- `create_all` crea las tablas que faltan, pero **no altera** las que ya
-- existen: en una base nueva estas dos columnas aparecen solas, y en una que ya
-- venía corriendo no. De ahí este archivo, para las bases que ya existen.
--
-- (Las migraciones de `db/postgres/migrations/` son otra cosa: versionan el
-- modelo completo de la propuesta de dominio, no el esquema reducido que la
-- aplicación crea hoy.)
--
-- Es idempotente: correrlo dos veces no hace nada la segunda vez.
--
--   docker compose exec -T postgres psql -U gastonomo -d gastonomo \
--     < db/postgres/esquema-aplicacion/001_tipo_cambio_en_comprobante.sql

ALTER TABLE comprobante
    ADD COLUMN IF NOT EXISTS tipo_cambio_venta NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS tipo_cambio_fecha DATE;

COMMENT ON COLUMN comprobante.tipo_cambio_venta IS
    'Tipo de cambio de venta (colones por dólar) vigente cuando se guardó este '
    'comprobante. NULL en los que se sincronizaron antes de que se empezara a '
    'sellarlos: esos se convierten con la tasa del día en que se consulten.';

COMMENT ON COLUMN comprobante.tipo_cambio_fecha IS
    'De qué día es la tasa guardada. No siempre coincide con comprobante.fecha: '
    'al sincronizar una bandeja vieja por primera vez se sella con la tasa de '
    'hoy una compra de hace meses. Permite distinguir una tasa contemporánea de '
    'una tardía en vez de presentar el total como más preciso de lo que es.';
