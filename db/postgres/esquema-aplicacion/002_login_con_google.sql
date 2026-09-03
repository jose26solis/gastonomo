-- Permite "Iniciar sesión con Google": agrega la columna que guarda el
-- identificador estable de la cuenta de Google, y afloja contrasena_hash
-- para que una cuenta creada así -sin contraseña propia- pueda existir.
--
-- Ver la nota de 001_tipo_cambio_en_comprobante.sql sobre por qué este
-- archivo existe: create_all() crea tablas que faltan pero nunca altera una
-- columna existente, así que una base que ya tenía `usuario` desde antes de
-- este login necesita este ALTER a mano.
--
-- Es idempotente: correrlo dos veces no hace nada la segunda vez.
--
--   docker compose exec -T postgres psql -U gastonomo -d gastonomo \
--     < db/postgres/esquema-aplicacion/002_login_con_google.sql

ALTER TABLE usuario
    ALTER COLUMN contrasena_hash DROP NOT NULL;

ALTER TABLE usuario
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(255);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_usuario_google_id'
    ) THEN
        ALTER TABLE usuario ADD CONSTRAINT uq_usuario_google_id UNIQUE (google_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_usuario_google_id ON usuario (google_id);

COMMENT ON COLUMN usuario.contrasena_hash IS
    'Hash bcrypt de la contraseña. NULL en una cuenta que solo inicia sesión '
    'con Google -no tiene contraseña propia.';

COMMENT ON COLUMN usuario.google_id IS
    'El "sub" (identificador estable) de la cuenta de Google vinculada como '
    'método de acceso, si el titular activó "Iniciar sesión con Google".';
