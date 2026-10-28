-- =============================================================================
-- ESQUEMA FÍSICO RELACIONAL EN TERCERA FORMA NORMAL (3FN) - 13 ENTIDADES
-- Trabajo Terminal No. 2027-A196 – ESCOM, IPN
-- "Prototipo de aplicación web para la recomendación de publicaciones de oferta
--  de laptops y tabletas entre la comunidad de la ESCOM"
-- =============================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

-- -----------------------------------------------------------------------------
-- 1. Entidad: usuario (Identidad, credenciales scrypt e insignia IPN RN-02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.usuario (
    id_usuario SERIAL PRIMARY KEY,
    nombre_completo VARCHAR(120) NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    contrasena_hash TEXT NOT NULL,
    medio_contacto VARCHAR(80),
    correo_verificado BOOLEAN NOT NULL DEFAULT FALSE,
    es_institucional BOOLEAN NOT NULL DEFAULT FALSE,
    reportes_acumulados INTEGER NOT NULL DEFAULT 0,
    estado_cuenta VARCHAR(20) NOT NULL DEFAULT 'Activa'
        CHECK (estado_cuenta IN ('Activa', 'Suspendida', 'Eliminada')),
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. Entidad: token_verificacion (Códigos SHA-256 de verificación y recuperación)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.token_verificacion (
    id_token SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('verificacion', 'restablecimiento')),
    expira_en TIMESTAMPTZ NOT NULL,
    usado BOOLEAN NOT NULL DEFAULT FALSE
);

-- -----------------------------------------------------------------------------
-- 3. Entidad: sesion_usuario (Sesiones activas protegidas por hash SHA-256)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.sesion_usuario (
    id_sesion SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expira_en TIMESTAMPTZ NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);

-- -----------------------------------------------------------------------------
-- 4. Entidad: perfil_academico (Relación 1:1 con usuario para el motor CBF)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.perfil_academico (
    id_perfil SERIAL PRIMARY KEY,
    id_usuario INTEGER UNIQUE NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    carrera VARCHAR(80),
    semestre SMALLINT CHECK (semestre IS NULL OR (semestre BETWEEN 1 AND 10)),
    rol_academico VARCHAR(30) NOT NULL DEFAULT 'Alumno',
    proyectar_dos_semestres BOOLEAN NOT NULL DEFAULT FALSE,
    es_aspirante BOOLEAN NOT NULL DEFAULT FALSE,
    unidades_aprendizaje TEXT[] DEFAULT '{}',
    areas_interes TEXT[] DEFAULT '{}',
    perfil_completo BOOLEAN NOT NULL DEFAULT FALSE
);

-- -----------------------------------------------------------------------------
-- 5. Entidad: requerimiento_unidad (Catálogo curricular parametrizado CBF)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.requerimiento_unidad (
    id_requerimiento SERIAL PRIMARY KEY,
    nombre_clave VARCHAR(120) UNIQUE NOT NULL,
    tipo_criterio VARCHAR(20) NOT NULL CHECK (tipo_criterio IN ('Unidad', 'Interes', 'Carrera')),
    carrera VARCHAR(80),
    semestre SMALLINT,
    ram_recomendada_gb INTEGER NOT NULL CHECK (ram_recomendada_gb >= 2),
    ssd_recomendado_gb INTEGER NOT NULL CHECK (ssd_recomendado_gb >= 32),
    nucleos_min INTEGER NOT NULL DEFAULT 4 CHECK (nucleos_min >= 2),
    requiere_gpu BOOLEAN NOT NULL DEFAULT FALSE,
    peso_ram NUMERIC(4,2) NOT NULL DEFAULT 0.35,
    peso_cpu NUMERIC(4,2) NOT NULL DEFAULT 0.25,
    peso_gpu NUMERIC(4,2) NOT NULL DEFAULT 0.20,
    peso_ssd NUMERIC(4,2) NOT NULL DEFAULT 0.20
);

-- -----------------------------------------------------------------------------
-- 6. Entidad: publicacion (Ciclo de vida comercial y vigencia de 30 días RN-08)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.publicacion (
    id_publicacion SERIAL PRIMARY KEY,
    id_ofertante INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    titulo VARCHAR(160) NOT NULL,
    descripcion TEXT NOT NULL,
    precio NUMERIC(10,2) NOT NULL CHECK (precio > 0),
    cantidad_disponible INTEGER NOT NULL DEFAULT 1 CHECK (cantidad_disponible >= 0),
    estado_publicacion VARCHAR(20) NOT NULL DEFAULT 'Activa'
        CHECK (estado_publicacion IN ('Activa', 'Vendida', 'Obsoleta')),
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_ultima_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 7. Entidad: especificacion_tecnica (Relación 1:1 con publicacion, RN-04 y RN-09)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.especificacion_tecnica (
    id_especificacion SERIAL PRIMARY KEY,
    id_publicacion INTEGER UNIQUE NOT NULL REFERENCES public.publicacion(id_publicacion) ON DELETE CASCADE,
    categoria VARCHAR(20) NOT NULL CHECK (categoria IN ('Laptop', 'Tableta')),
    marca VARCHAR(60) NOT NULL,
    modelo VARCHAR(120) NOT NULL,
    procesador_marca VARCHAR(40) NOT NULL,
    generacion_cpu VARCHAR(80) NOT NULL,
    nucleos_cpu INTEGER NOT NULL DEFAULT 4 CHECK (nucleos_cpu BETWEEN 2 AND 64),
    ram_gb INTEGER NOT NULL CHECK (ram_gb BETWEEN 2 AND 256),
    tipo_ram VARCHAR(25) NOT NULL DEFAULT 'DDR4',
    almacenamiento_gb INTEGER NOT NULL CHECK (almacenamiento_gb BETWEEN 16 AND 16384),
    tipo_almacenamiento VARCHAR(25) NOT NULL
        CHECK (tipo_almacenamiento IN ('SSD NVMe', 'SSD SATA', 'eMMC', 'HDD')),
    tiene_gpu_dedicada BOOLEAN NOT NULL DEFAULT FALSE,
    modelo_gpu VARCHAR(120) DEFAULT 'Integrada',
    pantalla VARCHAR(60) NOT NULL DEFAULT '15.6"',
    bateria VARCHAR(100) NOT NULL DEFAULT 'Buena',
    condicion_fisica VARCHAR(50) NOT NULL,
    huella_especificaciones VARCHAR(64) NOT NULL
);

-- -----------------------------------------------------------------------------
-- 8. Entidad: favorito (Seguimiento en vivo de ofertas, RN-12)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.favorito (
    id_favorito SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_publicacion INTEGER REFERENCES public.publicacion(id_publicacion) ON DELETE SET NULL,
    titulo_respaldo VARCHAR(160),
    fecha_agregado TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario, id_publicacion)
);

-- -----------------------------------------------------------------------------
-- 9. Entidad: comentario_publicacion (Preguntas, respuestas y reseñas verificadas)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.comentario_publicacion (
    id_comentario_pub SERIAL PRIMARY KEY,
    id_publicacion INTEGER NOT NULL REFERENCES public.publicacion(id_publicacion) ON DELETE CASCADE,
    id_autor INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_padre INTEGER REFERENCES public.comentario_publicacion(id_comentario_pub) ON DELETE CASCADE,
    contenido TEXT NOT NULL CHECK (char_length(contenido) BETWEEN 2 AND 1000),
    es_comprador_verificado BOOLEAN NOT NULL DEFAULT FALSE,
    editado BOOLEAN NOT NULL DEFAULT FALSE,
    votos_positivos INTEGER NOT NULL DEFAULT 0,
    votos_negativos INTEGER NOT NULL DEFAULT 0,
    fecha_comentario TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 10. Entidad: comentario_perfil (Comentarios y respuestas en perfiles públicos)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.comentario_perfil (
    id_comentario_perf SERIAL PRIMARY KEY,
    id_perfil_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_autor INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_padre INTEGER REFERENCES public.comentario_perfil(id_comentario_perf) ON DELETE CASCADE,
    contenido TEXT NOT NULL CHECK (char_length(contenido) BETWEEN 2 AND 1000),
    editado BOOLEAN NOT NULL DEFAULT FALSE,
    votos_positivos INTEGER NOT NULL DEFAULT 0,
    votos_negativos INTEGER NOT NULL DEFAULT 0,
    fecha_comentario TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 11. Entidad: voto_comentario (Automoderación comunitaria +1 / -1, RN-11)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.voto_comentario (
    id_voto SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    tipo_objeto VARCHAR(20) NOT NULL CHECK (tipo_objeto IN ('publicacion', 'perfil')),
    id_comentario INTEGER NOT NULL,
    valor SMALLINT NOT NULL CHECK (valor IN (-1, 1)),
    fecha_voto TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario, tipo_objeto, id_comentario)
);

-- -----------------------------------------------------------------------------
-- 12. Entidad: valoracion_perfil (Calificación en estrellas 1..5 a perfiles)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.valoracion_perfil (
    id_valoracion_perf SERIAL PRIMARY KEY,
    id_usuario_evaluado INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_evaluador INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    estrellas SMALLINT NOT NULL CHECK (estrellas BETWEEN 1 AND 5),
    fecha_valoracion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario_evaluado, id_evaluador),
    CHECK (id_usuario_evaluado <> id_evaluador)
);

-- -----------------------------------------------------------------------------
-- 13. Entidad: invitacion_valoracion (Comprador verificado, CU18, CU45, CU46)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invitacion_valoracion (
    id_invitacion SERIAL PRIMARY KEY,
    id_publicacion INTEGER NOT NULL REFERENCES public.publicacion(id_publicacion) ON DELETE CASCADE,
    id_ofertante INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_comprador INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    estado_invitacion VARCHAR(20) NOT NULL DEFAULT 'Pendiente'
        CHECK (estado_invitacion IN ('Pendiente', 'Aceptada', 'Rechazada')),
    estrellas_publicacion SMALLINT
        CHECK (estrellas_publicacion IS NULL OR (estrellas_publicacion BETWEEN 1 AND 5)),
    fecha_invitacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_publicacion, id_comprador),
    CHECK (id_ofertante <> id_comprador)
);

-- -----------------------------------------------------------------------------
-- 11 ÍNDICES ESPECIALIZADOS (B-Tree y GIN)
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_usuario_correo ON public.usuario USING btree (correo);
CREATE INDEX IF NOT EXISTS idx_sesion_usuario_expira ON public.sesion_usuario USING btree (expira_en);
CREATE INDEX IF NOT EXISTS idx_perfil_unidades_gin ON public.perfil_academico USING gin (unidades_aprendizaje);
CREATE INDEX IF NOT EXISTS idx_perfil_intereses_gin ON public.perfil_academico USING gin (areas_interes);
CREATE INDEX IF NOT EXISTS idx_publicacion_estado_fecha ON public.publicacion USING btree (estado_publicacion, fecha_ultima_actualizacion DESC);
CREATE INDEX IF NOT EXISTS idx_publicacion_precio ON public.publicacion USING btree (precio);
CREATE INDEX IF NOT EXISTS idx_espec_ram_ssd ON public.especificacion_tecnica USING btree (ram_gb, almacenamiento_gb);
CREATE INDEX IF NOT EXISTS idx_espec_huella ON public.especificacion_tecnica USING btree (huella_especificaciones);
CREATE INDEX IF NOT EXISTS idx_favorito_usuario ON public.favorito USING btree (id_usuario);
CREATE INDEX IF NOT EXISTS idx_comentario_pub_id ON public.comentario_publicacion USING btree (id_publicacion);
CREATE INDEX IF NOT EXISTS idx_invitacion_comprador ON public.invitacion_valoracion USING btree (id_comprador, estado_invitacion);
