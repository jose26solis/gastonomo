-- Trae el dominio completo de "Compra" -Compra, LineaCompra, MetodoPago,
-- ReglaCategorizacion, TipoCambio histórico, CategoriaEstandar- a la app que
-- corre de verdad. Antes de esto, ese modelo solo existía en el esquema que
-- migra Flyway (db/postgres/migrations/), un ejercicio académico aparte del
-- Laboratorio 2; esta migración es la versión SQLAlchemy-managed que usa el
-- backend en ejecución, con los mismos nombres de columna donde tiene sentido.
--
-- POR QUÉ ESTE ARCHIVO EXISTE
--
-- Mismo motivo que 001/003/004: `create_all()` crea las tablas NUEVAS solas,
-- pero no altera las que ya existían (`categoria`, `comprobante`,
-- `presupuesto` ganan columnas acá).
--
-- Es idempotente: correrlo dos veces no hace nada la segunda vez.
--
--   docker compose exec -T postgres psql -U gastonomo -d gastonomo \
--     < db/postgres/esquema-aplicacion/005_compra_real_y_conciliacion.sql

CREATE TABLE IF NOT EXISTS categoria_estandar (
    id BIGSERIAL PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    descripcion VARCHAR(255),
    color_hex VARCHAR(7) NOT NULL DEFAULT '#6B7280',
    orden INTEGER NOT NULL,
    CONSTRAINT uq_categoria_estandar_codigo UNIQUE (codigo)
);

ALTER TABLE categoria
    ADD COLUMN IF NOT EXISTS categoria_estandar_id BIGINT
        REFERENCES categoria_estandar(id);

CREATE TABLE IF NOT EXISTS metodo_pago (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuario(id),
    alias VARCHAR(60) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    moneda VARCHAR(3) NOT NULL DEFAULT 'CRC',
    ultimos_cuatro VARCHAR(4),
    entidad VARCHAR(80),
    dia_corte INTEGER,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_metodo_pago_usuario_alias UNIQUE (usuario_id, alias),
    CONSTRAINT uq_metodo_pago_usuario_ultimos_cuatro UNIQUE (usuario_id, ultimos_cuatro)
);

CREATE TABLE IF NOT EXISTS compra (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuario(id),
    comercio_id BIGINT NOT NULL REFERENCES comercio(id),
    metodo_pago_id BIGINT REFERENCES metodo_pago(id),
    fecha DATE NOT NULL,
    descripcion VARCHAR(255),
    moneda VARCHAR(3) NOT NULL DEFAULT 'CRC',
    estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR',
    origen VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    subtotal NUMERIC(14, 2) NOT NULL DEFAULT 0,
    descuento NUMERIC(14, 2) NOT NULL DEFAULT 0,
    impuesto NUMERIC(14, 2) NOT NULL DEFAULT 0,
    impuesto_desglosado BOOLEAN NOT NULL DEFAULT FALSE,
    total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tipo_cambio_aplicado NUMERIC(14, 6) NOT NULL DEFAULT 1,
    total_moneda_base NUMERIC(14, 2) NOT NULL DEFAULT 0,
    requiere_revision BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_compra_usuario_id ON compra (usuario_id);
CREATE INDEX IF NOT EXISTS ix_compra_comercio_id ON compra (comercio_id);
CREATE INDEX IF NOT EXISTS ix_compra_fecha ON compra (fecha);

CREATE TABLE IF NOT EXISTS linea_compra (
    id BIGSERIAL PRIMARY KEY,
    compra_id BIGINT NOT NULL REFERENCES compra(id) ON DELETE CASCADE,
    categoria_id BIGINT REFERENCES categoria(id),
    descripcion VARCHAR(255) NOT NULL,
    cantidad NUMERIC(12, 3) NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(14, 2) NOT NULL,
    descuento NUMERIC(14, 2) NOT NULL DEFAULT 0,
    exento_impuesto BOOLEAN NOT NULL DEFAULT FALSE,
    subtotal NUMERIC(14, 2) NOT NULL,
    categorizada_automaticamente BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_linea_compra_compra_id ON linea_compra (compra_id);

CREATE TABLE IF NOT EXISTS regla_categorizacion (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuario(id),
    categoria_destino_id BIGINT NOT NULL REFERENCES categoria(id),
    nombre VARCHAR(80) NOT NULL,
    campo VARCHAR(30) NOT NULL DEFAULT 'COMERCIO_NORMALIZADO',
    patron VARCHAR(200) NOT NULL,
    prioridad INTEGER NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    veces_aplicada INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_regla_usuario_nombre UNIQUE (usuario_id, nombre),
    CONSTRAINT uq_regla_usuario_prioridad UNIQUE (usuario_id, prioridad)
);

CREATE TABLE IF NOT EXISTS tipo_cambio (
    id BIGSERIAL PRIMARY KEY,
    moneda_origen VARCHAR(3) NOT NULL,
    moneda_destino VARCHAR(3) NOT NULL,
    fecha DATE NOT NULL,
    tasa NUMERIC(14, 6) NOT NULL,
    fuente VARCHAR(60) NOT NULL DEFAULT 'BCCR',
    CONSTRAINT uq_tipo_cambio_par_fecha UNIQUE (moneda_origen, moneda_destino, fecha)
);

CREATE INDEX IF NOT EXISTS ix_tipo_cambio_fecha ON tipo_cambio (fecha);

ALTER TABLE comprobante
    ADD COLUMN IF NOT EXISTS compra_id BIGINT REFERENCES compra(id);

ALTER TABLE presupuesto
    ADD COLUMN IF NOT EXISTS monto_consumido NUMERIC(14, 2) NOT NULL DEFAULT 0;

COMMENT ON TABLE compra IS
    'Compra real de negocio, creada por ConciliacionService a partir de un Comprobante ya parseado con confianza suficiente, o capturada a mano en el futuro.';
COMMENT ON COLUMN presupuesto.monto_consumido IS
    'Acumulado dentro de la misma transaccion que registra cada compra real (ConciliacionService), no recalculado en cada consulta.';
COMMENT ON COLUMN comprobante.compra_id IS
    'La Compra real que nacio de este comprobante -NULL si la confianza del parseo no alcanzo para conciliar solo.';
