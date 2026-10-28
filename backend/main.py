import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    func,
    not_,
    or_,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./hardware_match.db",
)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))  # 7 días (Tabla 3.8)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE = "escom_session"
# Cuenta de demostración opcional (solo desarrollo). Si DEMO_USER_PASSWORD no está definida,
# el vendedor de los datos de ejemplo se crea con una contraseña aleatoria que nadie conoce.
DEMO_USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo.escom@ipn.mx").strip().lower()
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@escom.ipn.mx").strip()


def send_system_email(to_email: str, subject: str, body_text: str) -> bool:
    """Envía un correo real por SMTP si SMTP_HOST está configurado; de lo contrario opera en modo local."""
    if not SMTP_HOST:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.set_content(body_text)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            if SMTP_PORT in (587, 2525):
                server.starttls()
                server.ehlo()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
except Exception:
    if "db:5432" not in DATABASE_URL:
        DATABASE_URL = "sqlite:///./hardware_match.db"
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ----------------------------------------------------
# MODELOS DE BASE DE DATOS (ORM SQLAlchemy)
# ----------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)

    # Rol Institucional / Tipo de usuario
    role: Mapped[str] = mapped_column(String(50), default="Alumno", nullable=False)

    # Perfil Académico (RN-03)
    career: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ISC, IIA, LCD, ISISA
    semester: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subjects: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # unidades_aprendizaje
    interests: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Verificación de Correo (RN-01, RN-02)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    es_institucional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # RN-02 Insignia IPN

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sessions: Mapped[List["SessionToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tokens: Mapped[List["VerificationToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    publications: Mapped[List["Publication"]] = relationship(back_populates="seller", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class VerificationToken(Base):
    """Tabla de códigos de verificación de correo (CU02, CU03) y restablecimiento de contraseña (CU05, CU06)."""
    __tablename__ = "token_verificacion"

    id_token: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # 'verificacion' | 'restablecimiento'
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="tokens")


class SessionToken(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    user: Mapped[User] = relationship(back_populates="sessions")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'Laptop' o 'Tableta'
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False)  # 'Nuevo', 'Usado - Como nuevo', etc.

    # Especificaciones Técnicas (RN-04)
    processor: Mapped[str] = mapped_column(String(150), nullable=False)
    processor_brand: Mapped[Optional[str]] = mapped_column(String(50), default="Intel", nullable=True)
    ram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_type: Mapped[Optional[str]] = mapped_column(String(30), default="DDR4", nullable=True)
    storage_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'SSD NVMe', 'SSD SATA', 'HDD', 'eMMC'
    gpu: Mapped[Optional[str]] = mapped_column(String(150), default="Integrada", nullable=True)
    screen_size: Mapped[Optional[str]] = mapped_column(String(50), default='15.6"', nullable=True)
    battery_condition: Mapped[Optional[str]] = mapped_column(String(100), default="Buena", nullable=True)
    spec_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # Huella SHA-256 (RN-09)

    # Datos Comerciales
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # cantidad_disponible (RN-09)
    description: Mapped[str] = mapped_column(Text, nullable=False)  # Observaciones / detalles
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Estado y Obsolescencia (RN-08)
    status: Mapped[str] = mapped_column(String(50), default="Activa", nullable=False)  # 'Activa', 'Vendida', 'Obsoleta'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    seller: Mapped[User] = relationship(back_populates="publications")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="publication")


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    publication_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("publications.id", ondelete="SET NULL"), nullable=True
    )
    deleted_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="favorites")
    publication: Mapped[Optional[Publication]] = relationship(back_populates="favorites")


# ----------------------------------------------------
# ESQUEMA COMPLETO DE LAS 13 ENTIDADES RELACIONALES (PostgreSQL)
# ----------------------------------------------------
DDL_13_TABLES_POSTGRES = """
CREATE TABLE IF NOT EXISTS public.usuario (
    id_usuario SERIAL PRIMARY KEY,
    nombre_completo VARCHAR(120) NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    contrasena_hash TEXT NOT NULL,
    medio_contacto VARCHAR(80),
    correo_verificado BOOLEAN NOT NULL DEFAULT FALSE,
    es_institucional BOOLEAN NOT NULL DEFAULT FALSE,
    reportes_acumulados INTEGER NOT NULL DEFAULT 0,
    estado_cuenta VARCHAR(20) NOT NULL DEFAULT 'Activa' CHECK (estado_cuenta IN ('Activa', 'Suspendida', 'Eliminada')),
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.sesion_usuario (
    id_sesion SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expira_en TIMESTAMPTZ NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);

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

CREATE TABLE IF NOT EXISTS public.publicacion (
    id_publicacion SERIAL PRIMARY KEY,
    id_ofertante INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    titulo VARCHAR(160) NOT NULL,
    descripcion TEXT NOT NULL,
    precio NUMERIC(10,2) NOT NULL CHECK (precio > 0),
    cantidad_disponible INTEGER NOT NULL DEFAULT 1 CHECK (cantidad_disponible >= 0),
    estado_publicacion VARCHAR(20) NOT NULL DEFAULT 'Activa' CHECK (estado_publicacion IN ('Activa', 'Vendida', 'Obsoleta')),
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_ultima_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
    tipo_almacenamiento VARCHAR(25) NOT NULL CHECK (tipo_almacenamiento IN ('SSD NVMe', 'SSD SATA', 'eMMC', 'HDD')),
    tiene_gpu_dedicada BOOLEAN NOT NULL DEFAULT FALSE,
    modelo_gpu VARCHAR(120) DEFAULT 'Integrada',
    pantalla VARCHAR(60) NOT NULL DEFAULT '15.6"',
    bateria VARCHAR(100) NOT NULL DEFAULT 'Buena',
    condicion_fisica VARCHAR(50) NOT NULL,
    huella_especificaciones VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.favorito (
    id_favorito SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_publicacion INTEGER REFERENCES public.publicacion(id_publicacion) ON DELETE SET NULL,
    titulo_respaldo VARCHAR(160),
    fecha_agregado TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario, id_publicacion)
);

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

CREATE TABLE IF NOT EXISTS public.voto_comentario (
    id_voto SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    tipo_objeto VARCHAR(20) NOT NULL CHECK (tipo_objeto IN ('publicacion', 'perfil')),
    id_comentario INTEGER NOT NULL,
    valor SMALLINT NOT NULL CHECK (valor IN (-1, 1)),
    fecha_voto TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario, tipo_objeto, id_comentario)
);

CREATE TABLE IF NOT EXISTS public.valoracion_perfil (
    id_valoracion_perf SERIAL PRIMARY KEY,
    id_usuario_evaluado INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_evaluador INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    estrellas SMALLINT NOT NULL CHECK (estrellas BETWEEN 1 AND 5),
    fecha_valoracion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_usuario_evaluado, id_evaluador),
    CHECK (id_usuario_evaluado <> id_evaluador)
);

CREATE TABLE IF NOT EXISTS public.invitacion_valoracion (
    id_invitacion SERIAL PRIMARY KEY,
    id_publicacion INTEGER NOT NULL REFERENCES public.publicacion(id_publicacion) ON DELETE CASCADE,
    id_ofertante INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    id_comprador INTEGER NOT NULL REFERENCES public.usuario(id_usuario) ON DELETE CASCADE,
    estado_invitacion VARCHAR(20) NOT NULL DEFAULT 'Pendiente' CHECK (estado_invitacion IN ('Pendiente', 'Aceptada', 'Rechazada')),
    estrellas_publicacion SMALLINT CHECK (estrellas_publicacion IS NULL OR (estrellas_publicacion BETWEEN 1 AND 5)),
    fecha_invitacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_publicacion, id_comprador),
    CHECK (id_ofertante <> id_comprador)
);

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
"""


# ----------------------------------------------------
# SCHEMAS PYDANTIC
# ----------------------------------------------------
class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(Credentials):
    name: str = Field(min_length=3, max_length=120)
    role: str = Field(default="Alumno", max_length=50)
    career: Optional[str] = Field(default=None, max_length=100)
    semester: Optional[str] = Field(default=None, max_length=50)
    subjects: Optional[str] = Field(default=None, max_length=1000)
    interests: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    code: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: Optional[str] = Field(default=None, max_length=128)


class ProfileUpdateRequest(BaseModel):
    role: Optional[str] = Field(default=None, max_length=50)
    career: Optional[str] = Field(default=None, max_length=100)
    semester: Optional[str] = Field(default=None, max_length=50)
    subjects: Optional[str] = Field(default=None, max_length=1000)
    interests: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    career: Optional[str] = None
    semester: Optional[str] = None
    subjects: Optional[str] = None
    interests: Optional[str] = None
    phone: Optional[str] = None
    is_verified: bool
    verification_token: Optional[str] = None
    es_institucional: bool
    has_complete_profile: bool


class PublicationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    device_type: str = Field(default="Laptop", max_length=50)
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)
    condition: str = Field(default="Usado - Como nuevo", max_length=50)
    processor: str = Field(min_length=2, max_length=150)
    processor_brand: Optional[str] = Field(default=None, max_length=50)
    ram_gb: int = Field(ge=2, le=256)
    ram_type: Optional[str] = Field(default="DDR4", max_length=30)
    storage_gb: int = Field(ge=16, le=16384)
    storage_type: str = Field(default="SSD NVMe", max_length=50)
    gpu: Optional[str] = Field(default="Integrada", max_length=150)
    screen_size: Optional[str] = Field(default='15.6"', max_length=50)
    battery_condition: Optional[str] = Field(default="Buena", max_length=100)
    price: float = Field(gt=0)
    stock: Optional[int] = Field(default=1, ge=1)
    description: str = Field(min_length=5, max_length=2500)
    image_url: Optional[str] = Field(default=None, max_length=1000)
    contact_phone: Optional[str] = Field(default=None, max_length=50)


class PublicationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(Activa|Vendida|Obsoleta)$")


class PublicationResponse(BaseModel):
    id: int
    seller_id: int
    seller_name: str
    seller_role: str
    seller_career: Optional[str] = None
    seller_es_institucional: bool
    title: str
    device_type: str
    brand: str
    model: str
    condition: str
    processor: str
    processor_brand: Optional[str] = None
    ram_gb: int
    ram_type: Optional[str] = None
    storage_gb: int
    storage_type: str
    gpu: Optional[str] = None
    screen_size: Optional[str] = None
    battery_condition: Optional[str] = None
    spec_hash: Optional[str] = None
    price: float
    stock: int
    description: str
    image_url: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False
    unavailable: bool = False
    merged_duplicate: bool = False
    compatibility_score: Optional[int] = None
    compatibility_badge: Optional[str] = None
    compatibility_detail: Optional[str] = None


app = FastAPI(
    title="API TT ESCOM - Recomendación de Laptops y Tabletas",
    description="Backend oficial conforme a especificación de casos de uso TT 2027-A196",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# HELPERS DE SEGURIDAD, HASHING Y SESIÓN
# ----------------------------------------------------
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email_format(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    encode = lambda value: base64.urlsafe_b64encode(value).decode()
    return f"scrypt${encode(salt)}${encode(derived)}"


# Hash de referencia constante para mantener el tiempo de comparación uniforme cuando el correo no existe (RN-13)
DUMMY_PASSWORD_HASH = hash_password("ReferenciaTiempoConstante_RN13_ESCOM!")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_digest = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode())
        expected = base64.urlsafe_b64decode(encoded_digest.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def infer_processor_brand(processor: str, explicit_brand: Optional[str] = None) -> str:
    if explicit_brand and explicit_brand.strip():
        return explicit_brand.strip()
    low = (processor or "").lower()
    if any(k in low for k in ["apple", "m1", "m2", "m3", "m4"]):
        return "Apple Silicon"
    if any(k in low for k in ["amd", "ryzen", "athlon", "threadripper"]):
        return "AMD"
    if any(k in low for k in ["qualcomm", "snapdragon", "kryo"]):
        return "Qualcomm"
    return "Intel"


def infer_ram_type(device_type: str, processor: str, explicit_ram_type: Optional[str] = None) -> str:
    if explicit_ram_type and explicit_ram_type.strip():
        return explicit_ram_type.strip()
    low = (processor or "").lower()
    if any(k in low for k in ["apple", "m1", "m2", "m3", "m4"]):
        return "Unificada"
    if device_type == "Tableta":
        return "LPDDR5"
    if any(k in low for k in ["6800", "7730", "7840", "13", "14", "ddr5"]):
        return "DDR5"
    return "DDR4"


def compute_spec_hash(
    device_type: str,
    brand: str,
    model: str,
    processor: str,
    ram_gb: int,
    storage_gb: int,
    storage_type: str,
    gpu: Optional[str],
    screen_size: Optional[str],
    condition: str,
) -> str:
    """RN-09: Huella criptográfica SHA-256 de las especificaciones técnicas normalizadas."""
    canonical = "||".join(
        [
            (device_type or "").strip().lower(),
            (brand or "").strip().lower(),
            (model or "").strip().lower(),
            (processor or "").strip().lower(),
            str(int(ram_gb)),
            str(int(storage_gb)),
            (storage_type or "").strip().lower(),
            (gpu or "integrada").strip().lower(),
            (screen_size or '15.6"').strip().lower(),
            (condition or "").strip().lower(),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def create_session(db: Session, user: User, response: Response) -> None:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        SessionToken(
            token_hash=token_digest(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS),
        )
    )
    db.commit()
    set_session_cookie(response, raw_token)


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def cleanup_expired_unverified_account(db: Session, email: str) -> None:
    """RN-01: Descarta la cuenta cuyo correo no se verificó en las 24 horas posteriores al registro."""
    existing = db.scalar(select(User).where(User.email == email))
    if existing and not existing.is_verified:
        created = ensure_aware(existing.created_at)
        if datetime.now(timezone.utc) - created > timedelta(hours=24):
            db.delete(existing)
            db.commit()


def refresh_obsolete_publications(db: Session) -> None:
    """RN-08 y CU17: Pasa automáticamente a 'Obsoleta' toda publicación activa con >= 30 días sin actualizar."""
    limit_date = datetime.now(timezone.utc) - timedelta(days=30)
    old_pubs = db.scalars(
        select(Publication).where(Publication.status == "Activa", Publication.updated_at < limit_date)
    ).all()
    if old_pubs:
        for op in old_pubs:
            op.status = "Obsoleta"
        db.commit()


def get_optional_user(request: Request, db: Session) -> Optional[User]:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    session_token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_digest(raw_token)))
    now = datetime.now(timezone.utc)
    if not session_token or ensure_aware(session_token.expires_at) <= now:
        if session_token:
            db.delete(session_token)
            db.commit()
        return None
    return session_token.user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    return user


def is_institutional_domain(email: str) -> bool:
    """RN-02: Compara si el dominio pertenece oficialmente al IPN (@alumno.ipn.mx o @ipn.mx)."""
    domain = email.split("@")[-1].lower()
    return domain == "ipn.mx" or domain == "alumno.ipn.mx" or domain.endswith(".ipn.mx")


def has_complete_profile(user: User) -> bool:
    """RN-03: Verifica si el perfil académico está completo para búsqueda por compatibilidad."""
    if user.role != "Alumno":
        return bool(user.interests or user.subjects or user.career)
    return bool(user.career and user.semester)


# ----------------------------------------------------
# MOTOR CBF (LÍNEA BASE - TRABAJO TERMINAL I)
# ----------------------------------------------------
GPU_INTEGRADA_TERMS = ["integrada", "intel iris", "intel uhd", "vega", "radeon graphics", "adreno"]


def evaluate_compatibility(pub: Publication, user: Optional[User]) -> tuple[int, str, str]:
    if not user or not user.career or user.role != "Alumno":
        if pub.ram_gb >= 16:
            return 90, "Compatible con tu perfil", "Recomendado para productividad avanzada y tareas exigentes."
        elif pub.ram_gb >= 8:
            return 82, "Compatible con tu perfil", "Adecuado para labores académicas y ofimática general."
        return 68, "Gama básica", "Apto para navegación y toma de apuntes."

    career = user.career.upper()
    has_dedicated_gpu = pub.gpu and not any(
        term in pub.gpu.lower() for term in GPU_INTEGRADA_TERMS
    )
    is_m_series = any(m in pub.processor.lower() for m in ["m1", "m2", "m3", "m4"])

    # IIA: Inteligencia Artificial
    if "INTELIGENCIA ARTIFICIAL" in career or "IIA" in career:
        if (has_dedicated_gpu or is_m_series) and pub.ram_gb >= 16:
            return 96, "Compatible con tu perfil (IIA)", "Excelente para entrenamiento de modelos de Machine Learning, Deep Learning y visión computacional con aceleración de GPU/Tensores."
        elif pub.ram_gb >= 16:
            return 83, "Compatible con tu perfil (IIA)", "Memoria adecuada para computación científica, aunque se recomienda GPU dedicada para redes neuronales profundas."
        elif pub.ram_gb >= 8:
            return 72, "Compatible con tu perfil (Tronco básico IIA)", "Permite programar en Python/C++, pero requerirá ampliación de memoria en etapas avanzadas."
        return 58, "Por debajo del umbral para IIA", "Memoria y procesamiento insuficientes para los paquetes de IA de la carrera."

    # ISC: Sistemas Computacionales
    if "SISTEMAS COMPUTACIONALES" in career or "ISC" in career:
        if pub.ram_gb >= 16 and "SSD" in pub.storage_type:
            return 95, "Compatible con tu perfil (ISC)", "Capaz de ejecutar máquinas virtuales, contenedores Docker y entornos de desarrollo pesados sin saturar el sistema."
        elif pub.ram_gb >= 8:
            return 85, "Compatible con tu perfil (ISC)", "Cumple con los requerimientos para programación en C++, Java, Bases de Datos y desarrollo Web."
        return 65, "Por debajo del umbral para ISC", "Puede presentar limitaciones en asignaturas con virtualización o emuladores de desarrollo móvil."

    # LCD: Ciencia de Datos
    if "CIENCIA DE DATOS" in career or "LCD" in career:
        if pub.ram_gb >= 16 and ("SSD" in pub.storage_type):
            return 94, "Compatible con tu perfil (LCD)", "Óptimo para manejo de DataFrames masivos en memoria, cálculo numérico intensivo y minería de datos."
        elif pub.ram_gb >= 8:
            return 80, "Compatible con tu perfil (LCD)", "Apto para estadística descriptiva y programación con conjuntos de datos medianos."
        return 60, "Por debajo del umbral para LCD", "Capacidad de memoria ajustada para procesamiento de Big Data."

    # ISISA: Sistemas Automotrices
    if "AUTOMOTRICES" in career or "ISISA" in career:
        if (has_dedicated_gpu or is_m_series) and pub.ram_gb >= 16:
            return 95, "Compatible con tu perfil (ISISA)", "Excelente para modelado 3D (SolidWorks, AutoCAD), análisis por elementos finitos y simulación mecánica."
        elif pub.ram_gb >= 8:
            return 78, "Compatible con tu perfil (ISISA)", "Adecuado para dibujo técnico y asignaturas de ciencias básicas."
        return 60, "Por debajo del umbral para ISISA", "No cuenta con aceleración gráfica óptima para renderizado automotriz."

    return 80, "Compatible con tu perfil", "Cumple los requerimientos generales de la formación en ingeniería."


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        career=user.career,
        semester=user.semester,
        subjects=user.subjects,
        interests=user.interests,
        phone=user.phone,
        is_verified=user.is_verified,
        verification_token=user.verification_token,
        es_institucional=user.es_institucional,
        has_complete_profile=has_complete_profile(user),
    )


def to_pub_response(
    pub: Publication,
    user: Optional[User],
    db: Optional[Session] = None,
    merged_duplicate: bool = False,
) -> PublicationResponse:
    score, badge, detail = evaluate_compatibility(pub, user)
    is_fav = False
    if user and db:
        is_fav = (
            db.scalar(
                select(Favorite).where(Favorite.user_id == user.id, Favorite.publication_id == pub.id)
            )
            is not None
        )

    proc_brand = infer_processor_brand(pub.processor, pub.processor_brand)
    r_type = infer_ram_type(pub.device_type, pub.processor, pub.ram_type)
    s_hash = pub.spec_hash or compute_spec_hash(
        pub.device_type,
        pub.brand,
        pub.model,
        pub.processor,
        pub.ram_gb,
        pub.storage_gb,
        pub.storage_type,
        pub.gpu,
        pub.screen_size,
        pub.condition,
    )

    return PublicationResponse(
        id=pub.id,
        seller_id=pub.seller_id,
        seller_name=pub.seller.name if pub.seller else "Miembro ESCOM",
        seller_role=pub.seller.role if pub.seller else "Comunidad",
        seller_career=pub.seller.career if pub.seller else None,
        seller_es_institucional=pub.seller.es_institucional if pub.seller else False,
        title=pub.title,
        device_type=pub.device_type,
        brand=pub.brand,
        model=pub.model,
        condition=pub.condition,
        processor=pub.processor,
        processor_brand=proc_brand,
        ram_gb=pub.ram_gb,
        ram_type=r_type,
        storage_gb=pub.storage_gb,
        storage_type=pub.storage_type,
        gpu=pub.gpu,
        screen_size=pub.screen_size,
        battery_condition=pub.battery_condition,
        spec_hash=s_hash,
        price=pub.price,
        stock=pub.stock,
        description=pub.description,
        image_url=pub.image_url,
        # RN-07 y RN-10: El teléfono solo se expone en /contact a usuarios autenticados con perfil completo distintos del vendedor
        contact_phone=pub.contact_phone if (user and user.id == pub.seller_id) else None,
        status=pub.status,
        created_at=pub.created_at,
        updated_at=pub.updated_at,
        is_favorite=is_fav,
        unavailable=False,
        merged_duplicate=merged_duplicate,
        compatibility_score=score,
        compatibility_badge=badge,
        compatibility_detail=detail,
    )


# ----------------------------------------------------
# INICIALIZACIÓN Y OBSOLESCENCIA (RN-08)
# ----------------------------------------------------
@app.on_event("startup")
def initialize_database():
    for attempt in range(10):
        try:
            Base.metadata.create_all(engine)
            # Migraciones directas y despliegue de las 13 entidades en PostgreSQL
            if not DATABASE_URL.startswith("sqlite"):
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'Alumno'"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS career VARCHAR(100)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS semester VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subjects VARCHAR(1000)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS interests VARCHAR(500)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(100)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS es_institucional BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
                    conn.execute(text("ALTER TABLE publications ADD COLUMN IF NOT EXISTS processor_brand VARCHAR(50) DEFAULT 'Intel'"))
                    conn.execute(text("ALTER TABLE publications ADD COLUMN IF NOT EXISTS ram_type VARCHAR(30) DEFAULT 'DDR4'"))
                    conn.execute(text("ALTER TABLE publications ADD COLUMN IF NOT EXISTS spec_hash VARCHAR(64)"))
                    conn.execute(text("ALTER TABLE favorites ALTER COLUMN publication_id DROP NOT NULL"))
                    conn.execute(text("ALTER TABLE favorites ADD COLUMN IF NOT EXISTS deleted_title VARCHAR(200)"))
                    for stmt in [s.strip() for s in DDL_13_TABLES_POSTGRES.split(";") if s.strip()]:
                        conn.execute(text(stmt))
                    conn.commit()

            with SessionLocal() as db:
                refresh_obsolete_publications(db)
                seed_database(db)
            return
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)


def seed_database(db: Session):
    # Actualizar metadatos inferidos en publicaciones existentes si faltan
    all_pubs = db.scalars(select(Publication)).all()
    if all_pubs:
        changed = False
        for p in all_pubs:
            if not p.processor_brand:
                p.processor_brand = infer_processor_brand(p.processor)
                changed = True
            if not p.ram_type:
                p.ram_type = infer_ram_type(p.device_type, p.processor)
                changed = True
            if not p.spec_hash:
                p.spec_hash = compute_spec_hash(
                    p.device_type,
                    p.brand,
                    p.model,
                    p.processor,
                    p.ram_gb,
                    p.storage_gb,
                    p.storage_type,
                    p.gpu,
                    p.screen_size,
                    p.condition,
                )
                changed = True
        if changed:
            db.commit()
        return

    # Usuario demo verificado e institucional
    demo_user = db.scalar(select(User).where(User.email == DEMO_USER_EMAIL))
    if not demo_user:
        demo_user = User(
            name="Comunidad ESCOM (Verificado)",
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD or secrets.token_urlsafe(24)),
            role="Alumno",
            career="Ingeniería en Sistemas Computacionales",
            semester="6° semestre",
            subjects="Sistemas Operativos, Ingeniería de Software, Redes de Computadoras",
            interests="Desarrollo de Software, Inteligencia Artificial, Ciberseguridad",
            phone="5555550101",
            is_verified=True,
            es_institucional=True,
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)

    seed_items = [
        Publication(
            seller_id=demo_user.id,
            title="Lenovo Legion 5 - Ideal para Inteligencia Artificial y Simulación",
            device_type="Laptop",
            brand="Lenovo",
            model="Legion 5 15ACH6H",
            condition="Usado - Como nuevo",
            processor="AMD Ryzen 7 5800H (8 núcleos, 16 hilos)",
            processor_brand="AMD",
            ram_gb=32,
            ram_type="DDR4",
            storage_gb=1024,
            storage_type="SSD NVMe",
            gpu="NVIDIA GeForce RTX 3070 8GB GDDR6 (130W)",
            screen_size='15.6" QHD 165Hz',
            battery_condition="92% de salud, cargador original de 300W",
            price=19500.0,
            stock=1,
            description="Laptop en excelente estado estético y funcional. Perfecta para estudiantes de IIA o ISC que requieran entrenar redes neuronales con CUDA o levantar múltiples contenedores Docker. Incluye caja y mochila original.",
            image_url="https://images.unsplash.com/photo-1603302576837-37561b2e2302?auto=format&fit=crop&w=800&q=80",
            contact_phone="5555550101",
            status="Activa",
        ),
        Publication(
            seller_id=demo_user.id,
            title="Dell Latitude 5420 - Portátil empresarial para programación y clases",
            device_type="Laptop",
            brand="Dell",
            model="Latitude 5420",
            condition="Usado - Buen estado",
            processor="Intel Core i5-1135G7 (4.2 GHz Turbo)",
            processor_brand="Intel",
            ram_gb=16,
            ram_type="DDR4",
            storage_gb=512,
            storage_type="SSD NVMe",
            gpu="Intel Iris Xe Graphics (Integrada)",
            screen_size='14.0" Full HD Mate',
            battery_condition="88% de salud, 6 horas de batería continua",
            price=9200.0,
            stock=1,
            description="Equipo ligero y resistente, ideal para llevar todos los días a la ESCOM. Teclado retroiluminado, puertos USB-C Thunderbolt y HDMI nativo para proyectores. Probada con Ubuntu 22.04 y Windows 11.",
            image_url="https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?auto=format&fit=crop&w=800&q=80",
            contact_phone="5555550102",
            status="Activa",
        ),
        Publication(
            seller_id=demo_user.id,
            title="Apple MacBook Air M2 - Gran autonomía para desarrollo de software",
            device_type="Laptop",
            brand="Apple",
            model="MacBook Air M2 2022",
            condition="Usado - Como nuevo",
            processor="Apple M2 (CPU 8 núcleos / GPU 8 núcleos)",
            processor_brand="Apple Silicon",
            ram_gb=16,
            ram_type="Unificada",
            storage_gb=512,
            storage_type="SSD NVMe",
            gpu="Apple M2 GPU 8-core",
            screen_size='13.6" Liquid Retina',
            battery_condition="96% de condición (98 ciclos de carga)",
            price=18800.0,
            stock=1,
            description="Color Midnight. Configurada de fábrica con 16GB de memoria unificada. Excelente para desarrollo frontend, backend, iOS y ofimática. La batería dura más de 12 horas en el campus.",
            image_url="https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80",
            contact_phone="5555550101",
            status="Activa",
        ),
        Publication(
            seller_id=demo_user.id,
            title="Samsung Galaxy Tab S8 - Productividad, apuntes y lectura de PDFs",
            device_type="Tableta",
            brand="Samsung",
            model="Galaxy Tab S8 Wi-Fi",
            condition="Usado - Como nuevo",
            processor="Qualcomm Snapdragon 8 Gen 1",
            processor_brand="Qualcomm",
            ram_gb=8,
            ram_type="LPDDR5",
            storage_gb=128,
            storage_type="eMMC",
            gpu="Adreno 730",
            screen_size='11.0" 120Hz LTPS TFT',
            battery_condition="95% de salud, dura hasta 2 días de clases",
            price=8500.0,
            stock=1,
            description="Incluye S Pen original de baja latencia y funda con teclado magnético. Ideal para tomar notas en clase de matemáticas/algoritmos, leer libros técnicos y usar como segunda pantalla inalámbrica.",
            image_url="https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=800&q=80",
            contact_phone="5555550102",
            status="Activa",
        ),
        Publication(
            seller_id=demo_user.id,
            title="ASUS TUF Gaming A15 - Potencia para ISISA y Ciencia de Datos",
            device_type="Laptop",
            brand="Asus",
            model="TUF Gaming A15 FA506",
            condition="Usado - Buen estado",
            processor="AMD Ryzen 7 6800H",
            processor_brand="AMD",
            ram_gb=16,
            ram_type="DDR5",
            storage_gb=512,
            storage_type="SSD NVMe",
            gpu="NVIDIA GeForce RTX 3050 4GB GDDR6",
            screen_size='15.6" FHD 144Hz',
            battery_condition="85% de capacidad, incluye eliminador original",
            price=14200.0,
            stock=1,
            description="Excelente opción costo-beneficio para modelado en SolidWorks, AutoCAD y análisis de datos. Construcción con certificación militar MIL-STD-810H. Teclado RGB.",
            image_url="https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=800&q=80",
            contact_phone="5555550101",
            status="Activa",
        ),
    ]

    for item in seed_items:
        item.spec_hash = compute_spec_hash(
            item.device_type,
            item.brand,
            item.model,
            item.processor,
            item.ram_gb,
            item.storage_gb,
            item.storage_type,
            item.gpu,
            item.screen_size,
            item.condition,
        )
        db.add(item)
    db.commit()


# ----------------------------------------------------
# ENDPOINTS REST: AUTENTICACIÓN, VERIFICACIÓN Y RECUPERACIÓN (CU01 a CU09)
# ----------------------------------------------------
@app.get("/")
def read_root():
    return {
        "status": "ok",
        "sistema": "ESCOM Hardware Match API",
        "tt": "2027-A196",
        "motor_bd": "Conectado",
    }


# CU01 Crear Cuenta y CU02 Mandar Correo de Verificación (RN-01, RN-03)
@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    name = payload.name.strip()
    if len(name) < 3 or "<" in name or ">" in name or not validate_email_format(email):
        raise HTTPException(status_code=400, detail="Datos de registro inválidos. Verifica nombre y formato de correo.")

    # RN-01: Si existe una cuenta con ese correo sin verificar con más de 24 horas, se descarta
    cleanup_expired_unverified_account(db, email)

    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(
            status_code=409,
            detail="El correo electrónico ingresado ya se encuentra registrado.",  # MSG-E01
        )

    # CU02: Genera código aleatorio de 32 bytes y guarda su hash SHA-256 en token_verificacion
    raw_verification_code = secrets.token_hex(32)

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role or "Alumno",
        career=payload.career,
        semester=payload.semester,
        subjects=payload.subjects,
        interests=payload.interests,
        phone=payload.phone,
        is_verified=False,
        verification_token=raw_verification_code,
        es_institucional=False,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El correo electrónico ingresado ya se encuentra registrado.") from None

    db.refresh(user)
    db.add(
        VerificationToken(
            id_usuario=user.id,
            token_hash=token_digest(raw_verification_code),
            tipo="verificacion",
            expira_en=datetime.now(timezone.utc) + timedelta(hours=24),
            usado=False,
        )
    )
    db.commit()
    send_system_email(
        to_email=user.email,
        subject="Código de verificación de cuenta · ESCOM Hardware Match",
        body_text=(
            f"Hola {user.name},\n\n"
            f"Tu código de verificación (vigente por 24 horas) es:\n\n"
            f"{raw_verification_code}\n\n"
            f"ESCOM Hardware Match · IPN"
        ),
    )
    create_session(db, user, response)
    return to_user_response(user)


# CU03 Confirmar Correo de Verificación (RN-01, RN-02)
@app.post("/auth/verify-email", response_model=UserResponse)
@app.post("/api/auth/verify-email", response_model=UserResponse)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    clean_token = token.strip()
    hashed = token_digest(clean_token)

    tok_record = db.scalar(
        select(VerificationToken).where(
            VerificationToken.token_hash == hashed,
            VerificationToken.tipo == "verificacion",
        )
    )
    user = None
    if tok_record:
        if tok_record.usado:
            raise HTTPException(status_code=400, detail="El código de verificación es inválido o ya fue utilizado.")
        if ensure_aware(tok_record.expira_en) <= datetime.now(timezone.utc):
            target_user = tok_record.user
            if target_user and not target_user.is_verified:
                db.delete(target_user)
                db.commit()
            raise HTTPException(
                status_code=400,
                detail="El código de verificación venció y la cuenta fue descartada. Regístrate de nuevo con tu correo.",
            )
        user = tok_record.user
        tok_record.usado = True
    else:
        user = db.scalar(select(User).where(User.verification_token == clean_token))

    if not user:
        raise HTTPException(status_code=400, detail="El código de verificación es inválido o ya fue utilizado.")

    user.is_verified = True
    user.verification_token = None
    # RN-02: Asignar insignia "Comunidad IPN" si el dominio pertenece al IPN
    user.es_institucional = is_institutional_domain(user.email)

    db.commit()
    db.refresh(user)
    return to_user_response(user)


# CU04 Iniciar Sesión (RN-01, RN-13, RNF-02, RNF-03)
@app.post("/auth/login", response_model=UserResponse)
@app.post("/api/auth/login", response_model=UserResponse)
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if not validate_email_format(email):
        raise HTTPException(status_code=400, detail="Credenciales inválidas. Verifica tu correo y contraseña.")

    user = db.scalar(select(User).where(User.email == email))
    if not user:
        # RN-13: Comparación contra hash de referencia para mantener respuesta uniforme
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Credenciales inválidas. Verifica tu correo y contraseña.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas. Verifica tu correo y contraseña.")

    create_session(db, user, response)
    return to_user_response(user)


# CU05 Solicitar Restablecimiento de Contraseña (RN-01, RN-13)
@app.post("/auth/forgot-password")
@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if not validate_email_format(email):
        raise HTTPException(status_code=400, detail="Captura un correo electrónico con formato válido.")  # MSG-E10

    uniform_msg = (
        "Si el correo corresponde a una cuenta con el correo verificado, "
        "recibirás un código para restablecer tu contraseña. Revisa tu bandeja de entrada."
    )  # MSG-28 (RN-13)

    user = db.scalar(select(User).where(User.email == email))
    dev_code = None
    if user and user.is_verified:
        # Invalidar códigos de restablecimiento anteriores de la cuenta
        prev_tokens = db.scalars(
            select(VerificationToken).where(
                VerificationToken.id_usuario == user.id,
                VerificationToken.tipo == "restablecimiento",
                VerificationToken.usado.is_(False),
            )
        ).all()
        for pt in prev_tokens:
            pt.usado = True

        raw_code = secrets.token_hex(32)
        db.add(
            VerificationToken(
                id_usuario=user.id,
                token_hash=token_digest(raw_code),
                tipo="restablecimiento",
                expira_en=datetime.now(timezone.utc) + timedelta(hours=24),
                usado=False,
            )
        )
        db.commit()
        sent = send_system_email(
            to_email=user.email,
            subject="Código para restablecer contraseña · ESCOM Hardware Match",
            body_text=(
                f"Hola {user.name},\n\n"
                f"Solicitaste restablecer tu contraseña. Tu código (vigente por 24 horas) es:\n\n"
                f"{raw_code}\n\n"
                f"Si no realizaste esta solicitud, puedes ignorar este mensaje."
            ),
        )
        if not sent:
            dev_code = raw_code

    return {
        "message": uniform_msg,
        "dev_reset_code": dev_code,
    }


# CU06 Confirmar Restablecimiento de Contraseña (RN-01, RNF-02, RNF-03)
@app.post("/auth/reset-password")
@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, response: Response, db: Session = Depends(get_db)):
    if payload.confirm_password is not None and payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="La contraseña y su confirmación no coinciden.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")  # MSG-E02

    code_hash = token_digest(payload.code.strip())
    tok = db.scalar(
        select(VerificationToken).where(
            VerificationToken.token_hash == code_hash,
            VerificationToken.tipo == "restablecimiento",
        )
    )
    now = datetime.now(timezone.utc)
    if not tok or tok.usado or ensure_aware(tok.expira_en) <= now:
        raise HTTPException(
            status_code=400,
            detail="El código de restablecimiento es inválido, ya fue utilizado o venció. Solicita uno nuevo.",  # MSG-E11
        )

    user = tok.user
    if not user or not user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="El código de restablecimiento es inválido, ya fue utilizado o venció. Solicita uno nuevo.",
        )

    # Derivar nuevo hash scrypt con sal nueva
    user.password_hash = hash_password(payload.new_password)
    tok.usado = True

    # Invalidar otros códigos de restablecimiento y cerrar todas las sesiones de la cuenta
    other_tokens = db.scalars(
        select(VerificationToken).where(
            VerificationToken.id_usuario == user.id,
            VerificationToken.tipo == "restablecimiento",
        )
    ).all()
    for ot in other_tokens:
        ot.usado = True

    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")

    return {"message": "Contraseña restablecida. Inicia sesión con tu nueva contraseña."}  # MSG-29


# CU08 Ver Perfil propio
@app.get("/auth/me", response_model=UserResponse)
@app.get("/api/profile", response_model=UserResponse)
def me(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    return to_user_response(user)


# CU09 Editar Perfil Académico
@app.put("/auth/profile", response_model=UserResponse)
@app.put("/api/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if payload.role is not None:
        user.role = payload.role
    if payload.career is not None:
        user.career = payload.career
    if payload.semester is not None:
        user.semester = payload.semester
    if payload.subjects is not None:
        user.subjects = payload.subjects
    if payload.interests is not None:
        user.interests = payload.interests
    if payload.phone is not None:
        user.phone = payload.phone

    db.commit()
    db.refresh(user)
    return to_user_response(user)


# Restablecer / limpiar datos del perfil académico
@app.delete("/auth/profile", response_model=UserResponse)
@app.delete("/api/profile", response_model=UserResponse)
def delete_profile(
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    user.career = None
    user.semester = None
    user.subjects = None
    user.interests = None
    db.commit()
    db.refresh(user)
    return to_user_response(user)


# CU07 Cerrar Sesión
@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == token_digest(raw_token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


# ----------------------------------------------------
# ENDPOINTS REST: PUBLICACIONES, 13 FILTROS Y MOTOR CBF (CU11 a CU28)
# ----------------------------------------------------
@app.get("/api/filters/options")
def get_filter_options(db: Session = Depends(get_db)):
    """Opciones dinámicas para los 13 filtros técnicos del catálogo (CU20, Tabla 3.9)."""
    active = Publication.status == "Activa"
    brands = db.scalars(select(Publication.brand).where(active).distinct().order_by(Publication.brand)).all()
    min_p, max_p = db.execute(
        select(func.min(Publication.price), func.max(Publication.price)).where(active)
    ).one()
    return {
        "brands": brands,
        "device_types": ["Laptop", "Tableta"],
        "processor_brands": ["Intel", "AMD", "Apple Silicon", "Qualcomm"],
        "ram_types": ["DDR4", "DDR5", "LPDDR4X", "LPDDR5", "Unificada"],
        "conditions": ["Nuevo", "Usado - Como nuevo", "Usado - Buen estado", "Usado - Con detalles"],
        "storage_types": ["SSD NVMe", "SSD SATA", "HDD", "eMMC"],
        "ram_options": [4, 8, 12, 16, 24, 32, 64],
        "storage_options": [128, 256, 512, 1024, 2048],
        "sort_options": ["recientes", "precio_asc", "precio_desc", "compatibilidad"],
        "price_range": {"min": min_p or 0, "max": max_p or 0},
    }


@app.get("/api/publications", response_model=List[PublicationResponse])
def get_publications(
    request: Request,
    # 1. Término de búsqueda libre
    search: Optional[str] = Query(None, description="Búsqueda libre por texto"),
    q: Optional[str] = Query(None, description="Alias q de búsqueda libre (Tabla 3.9)"),
    # 2. Categoría de dispositivo
    device_type: Optional[str] = Query(None, description="Filtrar por 'Laptop' o 'Tableta'"),
    categoria: Optional[str] = Query(None, description="Alias categoria (Tabla 3.9)"),
    # 3. Marca del fabricante
    brand: Optional[str] = Query(None, description="Marca del equipo"),
    marca: Optional[str] = Query(None, description="Alias marca (Tabla 3.9)"),
    # 4 y 5. Precio mínimo y máximo
    min_price: Optional[float] = Query(None, ge=0),
    precio_min: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    # 6. Familia / Marca de CPU
    processor_brand: Optional[str] = Query(None, description="Intel, AMD, Apple Silicon o Qualcomm"),
    procesador_marca: Optional[str] = Query(None, description="Alias procesador_marca (Tabla 3.9)"),
    # 7. Memoria RAM mínima
    min_ram: Optional[int] = Query(None, ge=1, description="RAM mínima en GB"),
    ram_min: Optional[int] = Query(None, ge=1, description="Alias ram_min (Tabla 3.9)"),
    # 8. Tipo de memoria RAM
    ram_type: Optional[str] = Query(None, description="DDR4, DDR5, LPDDR4X, LPDDR5 o Unificada"),
    tipo_ram: Optional[str] = Query(None, description="Alias tipo_ram (Tabla 3.9)"),
    # 9. Almacenamiento mínimo
    min_storage: Optional[int] = Query(None, ge=1, description="Almacenamiento mínimo en GB"),
    almacenamiento_min: Optional[int] = Query(None, ge=1, description="Alias almacenamiento_min (Tabla 3.9)"),
    # 10. Tipo de almacenamiento
    storage_type: Optional[str] = Query(None, description="SSD NVMe, SSD SATA, HDD o eMMC"),
    tipo_almacenamiento: Optional[str] = Query(None, description="Alias tipo_almacenamiento (Tabla 3.9)"),
    # 11. Tarjeta gráfica dedicada (GPU)
    gpu_type: Optional[str] = Query(None, description="'dedicada' o 'integrada'"),
    gpu_dedicada: Optional[bool] = Query(None, description="Alias booleano gpu_dedicada (Tabla 3.9)"),
    # 12. Condición / Estado físico
    condition: Optional[str] = Query(None, description="Filtrar por estado físico del equipo"),
    condicion_fisica: Optional[str] = Query(None, description="Alias condicion_fisica (Tabla 3.9)"),
    # 13. Ofertante con Insignia IPN
    ipn_sellers_only: bool = Query(False, description="Solo vendedores con correo institucional"),
    solo_institucional: bool = Query(False, description="Alias solo_institucional (Tabla 3.9)"),
    # Ordenamiento y modo de compatibilidad CBF (CU22, CU23)
    sort_by: str = Query("recientes", description="recientes, precio_asc, precio_desc o compatibilidad"),
    only_compatible: bool = Query(False, description="Activar Búsqueda por Compatibilidad de Perfil (RN-05)"),
    compatible: bool = Query(False, description="Alias compatible (CU22)"),
    db: Session = Depends(get_db),
):
    # RN-08 (CU17): Actualizar por obsolescencia al consultar el catálogo
    refresh_obsolete_publications(db)

    user = get_optional_user(request, db)

    eff_search = search if search is not None else q
    eff_device = device_type or categoria
    eff_brand = brand or marca
    eff_min_price = min_price if min_price is not None else precio_min
    eff_max_price = max_price if max_price is not None else precio_max
    eff_proc_brand = processor_brand or procesador_marca
    eff_min_ram = min_ram if min_ram is not None else ram_min
    eff_ram_type = ram_type or tipo_ram
    eff_min_storage = min_storage if min_storage is not None else almacenamiento_min
    eff_storage_type = storage_type or tipo_almacenamiento
    eff_condition = condition or condicion_fisica
    eff_ipn_only = ipn_sellers_only or solo_institucional
    eff_compatible = only_compatible or compatible

    if eff_min_price is not None and eff_max_price is not None and eff_min_price > eff_max_price:
        raise HTTPException(status_code=400, detail="El precio mínimo no puede ser mayor que el precio máximo.")

    # RN-03: Si se activa compatibilidad pero el usuario no tiene sesión o perfil completo, emitir error controlado
    if eff_compatible:
        if not user:
            raise HTTPException(
                status_code=400,
                detail="Debes iniciar sesión para activar el filtro de compatibilidad de perfil.",
            )
        if not has_complete_profile(user):
            raise HTTPException(
                status_code=400,
                detail="Para activar la búsqueda por compatibilidad primero debes completar tu perfil académico.",
            )

    query = select(Publication).where(Publication.status == "Activa")

    if eff_device and eff_device not in ("Todos", "Todas"):
        query = query.where(Publication.device_type == eff_device)

    if eff_condition and eff_condition not in ("Todas", "Todos"):
        query = query.where(Publication.condition.ilike(f"%{eff_condition.strip()}%"))

    if eff_min_price is not None:
        query = query.where(Publication.price >= eff_min_price)

    if eff_max_price is not None:
        query = query.where(Publication.price <= eff_max_price)

    if eff_brand and eff_brand not in ("Todas", "Todos"):
        query = query.where(Publication.brand.ilike(eff_brand.strip()))

    if eff_proc_brand and eff_proc_brand not in ("Todas", "Todos"):
        pb = eff_proc_brand.strip().lower()
        if "apple" in pb:
            query = query.where(
                or_(
                    Publication.processor_brand.ilike("%Apple%"),
                    Publication.processor.ilike("%Apple%"),
                    Publication.processor.ilike("%M1%"),
                    Publication.processor.ilike("%M2%"),
                    Publication.processor.ilike("%M3%"),
                )
            )
        else:
            query = query.where(
                or_(
                    Publication.processor_brand.ilike(f"%{eff_proc_brand.strip()}%"),
                    Publication.processor.ilike(f"%{eff_proc_brand.strip()}%"),
                )
            )

    if eff_min_ram is not None:
        query = query.where(Publication.ram_gb >= eff_min_ram)

    if eff_ram_type and eff_ram_type not in ("Todas", "Todos"):
        query = query.where(Publication.ram_type.ilike(eff_ram_type.strip()))

    if eff_min_storage is not None:
        query = query.where(Publication.storage_gb >= eff_min_storage)

    if eff_storage_type and eff_storage_type not in ("Todos", "Todas"):
        query = query.where(Publication.storage_type == eff_storage_type)

    eff_gpu = gpu_type
    if gpu_dedicada is True:
        eff_gpu = "dedicada"
    elif gpu_dedicada is False:
        eff_gpu = "integrada"

    if eff_gpu in ("dedicada", "integrada"):
        is_integrated = or_(
            Publication.gpu.is_(None),
            *[Publication.gpu.ilike(f"%{term}%") for term in GPU_INTEGRADA_TERMS],
        )
        query = query.where(is_integrated if eff_gpu == "integrada" else not_(is_integrated))

    if eff_ipn_only:
        query = query.join(User, User.id == Publication.seller_id).where(User.es_institucional.is_(True))

    if eff_search:
        st = f"%{eff_search.strip().lower()}%"
        query = query.where(
            (Publication.title.ilike(st))
            | (Publication.brand.ilike(st))
            | (Publication.model.ilike(st))
            | (Publication.processor.ilike(st))
            | (Publication.description.ilike(st))
        )

    if sort_by == "precio_asc":
        query = query.order_by(Publication.price.asc())
    elif sort_by == "precio_desc":
        query = query.order_by(Publication.price.desc())
    else:
        query = query.order_by(Publication.created_at.desc())

    publications = db.scalars(query).all()
    results = [to_pub_response(pub, user, db) for pub in publications]

    if eff_compatible:
        # RN-05: Etiquetar y priorizar aquellas que cumplen el umbral de compatibilidad (>= 70%)
        results = [r for r in results if (r.compatibility_score or 0) >= 70]
        results.sort(key=lambda x: (x.compatibility_score or 0), reverse=True)
    elif sort_by == "compatibilidad":
        results.sort(key=lambda x: (x.compatibility_score or 0), reverse=True)

    return results


# CU12 / CU24: Ver Detalle de Publicación de Oferta
@app.get("/api/publications/{publication_id}", response_model=PublicationResponse)
def get_publication(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Esta publicación ya no está disponible.")
    return to_pub_response(pub, user, db)


# Ver Datos de Contacto
@app.get("/api/publications/{publication_id}/contact")
def get_contact_info(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not has_complete_profile(user):
        raise HTTPException(
            status_code=403,
            detail="Debes contar con sesión iniciada y perfil académico registrado para consultar los datos de contacto.",
        )

    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    if pub.seller_id == user.id:
        raise HTTPException(status_code=400, detail="Eres el vendedor de esta publicación.")

    contact = pub.contact_phone or pub.seller.phone or pub.seller.email
    return {
        "seller_name": pub.seller.name,
        "seller_email": pub.seller.email,
        "seller_role": pub.seller.role,
        "seller_career": pub.seller.career,
        "seller_es_institucional": pub.seller.es_institucional,
        "contact": contact,
        "notice": "Datos de contacto visibles. Recuerda que la plataforma no procesa pagos; coordina la revisión dentro de la ESCOM.",
    }


# CU11: Crear Publicación de Oferta (RN-04, RN-08, RN-09)
@app.post("/api/publications", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
def create_publication(
    payload: PublicationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)

    proc_brand = infer_processor_brand(payload.processor, payload.processor_brand)
    r_type = infer_ram_type(payload.device_type, payload.processor, payload.ram_type)
    new_spec_hash = compute_spec_hash(
        payload.device_type,
        payload.brand,
        payload.model,
        payload.processor,
        payload.ram_gb,
        payload.storage_gb,
        payload.storage_type,
        payload.gpu,
        payload.screen_size,
        payload.condition,
    )

    # RN-09: Detección de duplicados mediante huella SHA-256 contra publicaciones propias (activas u obsoletas)
    existing_candidates = db.scalars(
        select(Publication).where(
            Publication.seller_id == user.id,
            Publication.status.in_(["Activa", "Obsoleta"]),
            or_(
                Publication.spec_hash == new_spec_hash,
                (
                    Publication.brand.ilike(payload.brand.strip())
                    & Publication.model.ilike(payload.model.strip())
                    & Publication.processor.ilike(payload.processor.strip())
                    & (Publication.ram_gb == payload.ram_gb)
                    & (Publication.storage_gb == payload.storage_gb)
                ),
            ),
        )
    ).all()

    for existing_duplicate in existing_candidates:
        # Si coinciden las especificaciones y también las observaciones/descripción: incrementa stock (CU13)
        if existing_duplicate.description.strip().lower() == payload.description.strip().lower():
            existing_duplicate.stock += payload.stock or 1
            existing_duplicate.status = "Activa"
            existing_duplicate.spec_hash = new_spec_hash
            existing_duplicate.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_duplicate)
            return to_pub_response(existing_duplicate, user, db, merged_duplicate=True)

    # Sin coincidencia completa de observaciones o nuevo equipo: publicar como nueva
    image = payload.image_url
    if not image:
        if payload.device_type == "Tableta":
            image = "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=800&q=80"
        else:
            image = "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80"

    contact = payload.contact_phone or user.phone or "Contacto vía correo"

    pub = Publication(
        seller_id=user.id,
        title=payload.title.strip(),
        device_type=payload.device_type,
        brand=payload.brand.strip(),
        model=payload.model.strip(),
        condition=payload.condition,
        processor=payload.processor.strip(),
        processor_brand=proc_brand,
        ram_gb=payload.ram_gb,
        ram_type=r_type,
        storage_gb=payload.storage_gb,
        storage_type=payload.storage_type,
        gpu=payload.gpu.strip() if payload.gpu else "Integrada",
        screen_size=payload.screen_size or '15.6"',
        battery_condition=payload.battery_condition or "Buena",
        spec_hash=new_spec_hash,
        price=payload.price,
        stock=payload.stock or 1,
        description=payload.description.strip(),
        image_url=image,
        contact_phone=contact,
        status="Activa",
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)
    return to_pub_response(pub, user, db)


# CU13: Editar Publicación de Oferta
@app.put("/api/publications/{publication_id}", response_model=PublicationResponse)
def edit_publication(
    publication_id: int,
    payload: PublicationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if pub.seller_id != user.id:
        raise HTTPException(status_code=403, detail="No eres el propietario de esta publicación")

    pub.title = payload.title.strip()
    pub.device_type = payload.device_type
    pub.brand = payload.brand.strip()
    pub.model = payload.model.strip()
    pub.condition = payload.condition
    pub.processor = payload.processor.strip()
    pub.processor_brand = infer_processor_brand(payload.processor, payload.processor_brand)
    pub.ram_gb = payload.ram_gb
    pub.ram_type = infer_ram_type(payload.device_type, payload.processor, payload.ram_type)
    pub.storage_gb = payload.storage_gb
    pub.storage_type = payload.storage_type
    pub.gpu = payload.gpu.strip() if payload.gpu else "Integrada"
    pub.screen_size = payload.screen_size or pub.screen_size
    pub.battery_condition = payload.battery_condition or pub.battery_condition
    pub.spec_hash = compute_spec_hash(
        pub.device_type,
        pub.brand,
        pub.model,
        pub.processor,
        pub.ram_gb,
        pub.storage_gb,
        pub.storage_type,
        pub.gpu,
        pub.screen_size,
        pub.condition,
    )
    pub.price = payload.price
    pub.stock = payload.stock or pub.stock
    pub.description = payload.description.strip()
    if payload.image_url:
        pub.image_url = payload.image_url
    if payload.contact_phone:
        pub.contact_phone = payload.contact_phone
    pub.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(pub)
    return to_pub_response(pub, user, db)


# CU16: Actualizar Estado de Publicación de Oferta
@app.patch("/api/publications/{publication_id}/status")
def update_publication_status(
    publication_id: int,
    payload: PublicationStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if pub.seller_id != user.id:
        raise HTTPException(status_code=403, detail="No eres el propietario de esta publicación")

    prev_stock = pub.stock
    pub.status = payload.status
    pub.updated_at = datetime.now(timezone.utc)

    invite_rating = False
    if payload.status == "Vendida":
        pub.stock = 0
        if prev_stock == 1:
            invite_rating = True
    elif payload.status == "Activa" and pub.stock == 0:
        pub.stock = 1

    db.commit()
    db.refresh(pub)
    return {
        "status": pub.status,
        "stock": pub.stock,
        "invite_rating": invite_rating,
        "message": (
            "Estado de la publicación actualizado a Vendida (stock ajustado a 0)."
            if payload.status == "Vendida"
            else "Estado de la publicación actualizado."
        ),
    }


# CU14: Eliminar Publicación de Oferta (conservando aviso en Favoritos conforme a RN-12)
@app.delete("/api/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if pub.seller_id != user.id:
        raise HTTPException(status_code=403, detail="No eres el propietario de esta publicación")

    # RN-12: Conservar en favoritos de otros usuarios como "[Esta publicación ya no está disponible]"
    linked_favs = db.scalars(select(Favorite).where(Favorite.publication_id == pub.id)).all()
    for fav in linked_favs:
        fav.deleted_title = pub.title
        fav.publication_id = None

    db.delete(pub)
    db.commit()


# CU15: Consultar Publicaciones de Ofertas Creadas ("Mis publicaciones")
@app.get("/api/my-publications", response_model=List[PublicationResponse])
def get_my_publications(
    request: Request,
    status_filter: Optional[str] = Query(None, description="Filtrar por Activa, Vendida u Obsoleta"),
    db: Session = Depends(get_db),
):
    refresh_obsolete_publications(db)
    user = current_user(request, db)
    stmt = select(Publication).where(Publication.seller_id == user.id)
    if status_filter and status_filter not in ("Todas", "Todos"):
        stmt = stmt.where(Publication.status == status_filter)
    publications = db.scalars(stmt.order_by(Publication.created_at.desc())).all()
    return [to_pub_response(pub, user, db) for pub in publications]


# ----------------------------------------------------
# FAVORITOS (CU29, CU30, CU31 - RN-12)
# ----------------------------------------------------
@app.get("/api/favorites", response_model=List[PublicationResponse])
def get_favorites(
    request: Request,
    db: Session = Depends(get_db),
):
    refresh_obsolete_publications(db)
    user = current_user(request, db)
    fav_rows = db.scalars(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    ).all()

    response_list: List[PublicationResponse] = []
    for fav in fav_rows:
        if fav.publication is not None:
            response_list.append(to_pub_response(fav.publication, user, db))
        else:
            # RN-12: Tarjeta gris "[Esta publicación ya no está disponible]"
            response_list.append(
                PublicationResponse(
                    id=-fav.id,
                    seller_id=0,
                    seller_name="No disponible",
                    seller_role="",
                    seller_career=None,
                    seller_es_institucional=False,
                    title="[Esta publicación ya no está disponible]",
                    device_type="Equipo",
                    brand=fav.deleted_title or "Publicación retirada",
                    model="",
                    condition="No disponible",
                    processor="—",
                    processor_brand="—",
                    ram_gb=0,
                    ram_type="—",
                    storage_gb=0,
                    storage_type="—",
                    gpu="—",
                    screen_size="—",
                    battery_condition="—",
                    spec_hash=None,
                    price=0.0,
                    stock=0,
                    description="El ofertante eliminó esta publicación.",
                    image_url=None,
                    contact_phone=None,
                    status="No disponible",
                    created_at=fav.created_at,
                    updated_at=fav.created_at,
                    is_favorite=True,
                    unavailable=True,
                )
            )
    return response_list


@app.post("/api/favorites/{publication_id}")
def add_favorite(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    existing = db.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.publication_id == publication_id)
    )
    if not existing:
        db.add(Favorite(user_id=user.id, publication_id=publication_id, deleted_title=pub.title))
        db.commit()
    return {"message": "Publicación agregada a tus favoritos."}


@app.delete("/api/favorites/{publication_id}")
def remove_favorite(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if publication_id < 0:
        fav = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.id == abs(publication_id)))
    else:
        fav = db.scalar(
            select(Favorite).where(Favorite.user_id == user.id, Favorite.publication_id == publication_id)
        )
    if fav:
        db.delete(fav)
        db.commit()
    return {"message": "Publicación eliminada de tu lista de favoritos."}  # MSG-24
