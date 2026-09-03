-- Crea la tabla de transferencias SINPE ya parseadas y la bandera de
-- preferencia en usuario que decide si se sincronizan.
--
-- POR QUÉ ESTE ARCHIVO EXISTE
--
-- El esquema que usa la aplicación en ejecución no lo maneja Flyway: lo crea
-- SQLAlchemy con `Base.metadata.create_all` (ver `src/app/config/database.py`).
-- `create_all` SÍ crea `transferencia_sinpe` sola en cualquier base -es una
-- tabla nueva-, pero **no altera** `usuario`, que ya existe: la columna nueva
-- (`leer_transferencias_sinpe`) no aparece sola en una base que ya venía
-- corriendo. De ahí este archivo.
--
-- (Las migraciones de `db/postgres/migrations/` son otra cosa: versionan el
-- modelo completo de la propuesta de dominio, no el esquema reducido que la
-- aplicación crea hoy.)
--
-- Es idempotente: correrlo dos veces no hace nada la segunda vez.
--
--   docker compose exec -T postgres psql -U gastonomo -d gastonomo \
--     < db/postgres/esquema-aplicacion/003_transferencias_sinpe.sql

ALTER TABLE usuario
    ADD COLUMN IF NOT EXISTS leer_transferencias_sinpe BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN usuario.leer_transferencias_sinpe IS
    'Si esta prendido, CuentaCorreoService.transferencias_sinpe_de_usuario busca '
    '"sinpe" en cada buzon activo y guarda lo que sepa leer. Apagado por default: '
    'es una peticion real por cuenta antes de poder parsear nada.';

CREATE TABLE IF NOT EXISTS transferencia_sinpe (
    id BIGSERIAL PRIMARY KEY,
    cuenta_correo_id BIGINT NOT NULL REFERENCES cuenta_correo(id),
    mensaje_id VARCHAR(300) NOT NULL,
    banco VARCHAR(80) NOT NULL,
    destinatario VARCHAR(200),
    cuenta_destino VARCHAR(40),
    fecha TIMESTAMP,
    moneda VARCHAR(3),
    monto NUMERIC(14, 2),
    concepto VARCHAR(300),
    referencia VARCHAR(60),
    comprobante VARCHAR(60),
    confianza DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_transferencia_sinpe_cuenta_mensaje UNIQUE (cuenta_correo_id, mensaje_id)
);

CREATE INDEX IF NOT EXISTS ix_transferencia_sinpe_cuenta_correo_id
    ON transferencia_sinpe (cuenta_correo_id);

CREATE INDEX IF NOT EXISTS ix_transferencia_sinpe_fecha
    ON transferencia_sinpe (fecha);

COMMENT ON TABLE transferencia_sinpe IS
    'Cache de notificaciones de SINPE recibida ya parseadas -mismo motivo que '
    'comprobante: no releer ni reparsear un mensaje ya sincronizado.';
