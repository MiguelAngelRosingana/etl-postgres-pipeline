-- Esquema del proyecto. Se ejecuta automáticamente al crear el contenedor de PostgreSQL
-- (carpeta docker-entrypoint-initdb.d) o con:  python -m etl init-db

CREATE SCHEMA IF NOT EXISTS stg;    -- zona de aterrizaje: datos validados, sin integrar
CREATE SCHEMA IF NOT EXISTS core;   -- modelo definitivo
CREATE SCHEMA IF NOT EXISTS etl;    -- control y auditoría del propio proceso

-- ---------------------------------------------------------------- control del ETL
CREATE TABLE etl.ejecuciones (
    run_id              BIGSERIAL PRIMARY KEY,
    fichero             TEXT        NOT NULL,
    sha256              CHAR(64)    NOT NULL,
    inicio              TIMESTAMPTZ NOT NULL DEFAULT now(),
    fin                 TIMESTAMPTZ,
    estado              TEXT        NOT NULL
                        CHECK (estado IN ('en_curso', 'ok', 'error', 'omitido')),
    filas_leidas        INT,
    filas_validas       INT,
    filas_rechazadas    INT,
    filas_duplicadas    INT,
    ventas_insertadas   INT,
    ventas_actualizadas INT,
    mensaje             TEXT
);
-- Para saber rápido si un fichero ya se procesó correctamente
CREATE INDEX idx_ejecuciones_sha_ok ON etl.ejecuciones (sha256) WHERE estado = 'ok';

CREATE TABLE etl.filas_rechazadas (
    id      BIGSERIAL PRIMARY KEY,
    run_id  BIGINT  NOT NULL REFERENCES etl.ejecuciones (run_id) ON DELETE CASCADE,
    linea   INT     NOT NULL,          -- línea del fichero de origen
    motivo  TEXT    NOT NULL,
    datos   JSONB   NOT NULL           -- la fila tal como llegó
);
CREATE INDEX idx_rechazadas_run ON etl.filas_rechazadas (run_id);  -- índice de la clave foránea

-- ---------------------------------------------------------------- staging
-- UNLOGGED: no escribe en el WAL. Es más rápido y no importa perderla en un fallo,
-- porque se vuelve a llenar en cada ejecución.
CREATE UNLOGGED TABLE stg.ventas (
    linea           INT,
    id_venta        TEXT,
    fecha           DATE,
    cliente_email   TEXT,
    cliente_nombre  TEXT,
    producto        TEXT,
    categoria       TEXT,
    cantidad        INT,
    precio_unitario NUMERIC(10, 2),
    estado          TEXT
);

-- ---------------------------------------------------------------- modelo definitivo
CREATE TABLE core.clientes (
    cliente_id BIGSERIAL   PRIMARY KEY,           -- clave sustituta
    email      TEXT        NOT NULL UNIQUE,       -- clave de negocio
    nombre     TEXT        NOT NULL,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.ventas (
    id_venta        TEXT          PRIMARY KEY,
    fecha           DATE          NOT NULL,
    cliente_id      BIGINT        NOT NULL REFERENCES core.clientes (cliente_id) ON DELETE RESTRICT,
    producto        TEXT          NOT NULL,
    categoria       TEXT,
    cantidad        INT           NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    estado          TEXT          NOT NULL
                    CHECK (estado IN ('pendiente', 'pagado', 'enviado', 'cancelado')),
    total           NUMERIC(12, 2) GENERATED ALWAYS AS (cantidad * precio_unitario) STORED,
    actualizado_en  TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_ventas_cliente ON core.ventas (cliente_id);   -- PostgreSQL no indexa las FK solo
CREATE INDEX idx_ventas_fecha   ON core.ventas (fecha);
