import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
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
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE = "escom_session"
# Cuenta de demostración opcional (solo desarrollo). Si DEMO_USER_PASSWORD no está definida,
# el vendedor de los datos de ejemplo se crea con una contraseña aleatoria que nadie conoce.
DEMO_USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo.escom@ipn.mx").strip().lower()
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "")

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
# MODELOS DE BASE DE DATOS
# ----------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)

    # Rol Institucional
    role: Mapped[str] = mapped_column(String(50), default="Alumno", nullable=False)

    # Perfil Académico (RN-03)
    career: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ISC, IIA, LCD, ISISA
    semester: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    interests: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Verificación de Correo (RN-01, RN-02)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    es_institucional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # RN-02 Insignia IPN

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sessions: Mapped[List["SessionToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    publications: Mapped[List["Publication"]] = relationship(back_populates="seller", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")


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
    ram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'SSD NVMe', 'SSD SATA', 'HDD', 'eMMC'
    gpu: Mapped[Optional[str]] = mapped_column(String(150), default="Integrada", nullable=True)
    screen_size: Mapped[Optional[str]] = mapped_column(String(50), default='15.6"', nullable=True)
    battery_condition: Mapped[Optional[str]] = mapped_column(String(100), default="Buena", nullable=True)

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
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="publication", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="favorites")
    publication: Mapped[Publication] = relationship(back_populates="favorites")


# ----------------------------------------------------
# SCHEMAS PYDANTIC
# ----------------------------------------------------
class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(Credentials):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="Alumno", max_length=50)
    career: Optional[str] = Field(default=None, max_length=100)
    semester: Optional[str] = Field(default=None, max_length=50)
    interests: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)


class ProfileUpdateRequest(BaseModel):
    career: Optional[str] = Field(default=None, max_length=100)
    semester: Optional[str] = Field(default=None, max_length=50)
    interests: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    career: Optional[str] = None
    semester: Optional[str] = None
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
    ram_gb: int = Field(ge=2, le=256)
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
    ram_gb: int
    storage_gb: int
    storage_type: str
    gpu: Optional[str] = None
    screen_size: Optional[str] = None
    battery_condition: Optional[str] = None
    price: float
    stock: int
    description: str
    image_url: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False
    compatibility_score: Optional[int] = None
    compatibility_badge: Optional[str] = None
    compatibility_detail: Optional[str] = None


app = FastAPI(
    title="API TT ESCOM - Recomendación de Laptops y Tabletas",
    description="Backend oficial conforme a especificación de casos de uso TT 2027-A196",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# HELPERS DE SEGURIDAD Y SESIÓN
# ----------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    encode = lambda value: base64.urlsafe_b64encode(value).decode()
    return f"scrypt${encode(salt)}${encode(derived)}"


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


def get_optional_user(request: Request, db: Session) -> Optional[User]:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    session_token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_digest(raw_token)))
    now = datetime.now(timezone.utc)
    if not session_token or session_token.expires_at <= now:
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
    """RN-02: Compara si el dominio pertenece oficialmente al IPN."""
    domain = email.split("@")[-1].lower()
    return domain.endswith("ipn.mx")


def has_complete_profile(user: User) -> bool:
    """RN-03: Verifica si el perfil académico está completo para búsqueda por compatibilidad."""
    if user.role != "Alumno":
        return True
    return bool(user.career and user.semester)


# ----------------------------------------------------
# MOTOR CBF (LÍNEA BASE - SPRINT 5)
# ----------------------------------------------------
GPU_INTEGRADA_TERMS = ["integrada", "intel iris", "intel uhd", "vega", "radeon graphics", "adreno"]


def evaluate_compatibility(pub: Publication, user: Optional[User]) -> tuple[int, str, str]:
    if not user or not user.career or user.role != "Alumno":
        if pub.ram_gb >= 16:
            return 90, "Equipo de alto rendimiento", "Recomendado para productividad avanzada y tareas exigentes."
        elif pub.ram_gb >= 8:
            return 82, "Equipo balanceado", "Adecuado para labores académicas y ofimática general."
        return 70, "Gama básica", "Apto para navegación y toma de apuntes."

    career = user.career.upper()
    has_dedicated_gpu = pub.gpu and not any(
        term in pub.gpu.lower() for term in GPU_INTEGRADA_TERMS
    )
    is_m_series = any(m in pub.processor.lower() for m in ["m1", "m2", "m3", "m4"])

    # IIA: Inteligencia Artificial
    if "INTELIGENCIA ARTIFICIAL" in career or "IIA" in career:
        if (has_dedicated_gpu or is_m_series) and pub.ram_gb >= 16:
            return 96, "Altamente compatible con IIA", "Excelente para entrenamiento de modelos de Machine Learning, Deep Learning y visión computacional con aceleración de GPU/Tensores."
        elif pub.ram_gb >= 16:
            return 83, "Compatible para fundamentos de IA", "Memoria adecuada para computación científica, aunque se recomienda GPU dedicada para redes neuronales profundas."
        elif pub.ram_gb >= 8:
            return 72, "Aceptable para primeros semestres", "Permite programar en Python/C++, pero requerirá ampliación de memoria en etapas avanzadas."
        return 58, "No recomendado para IA", "Memoria y procesamiento insuficientes para los paquetes de IA de la carrera."

    # ISC: Sistemas Computacionales
    if "SISTEMAS COMPUTACIONALES" in career or "ISC" in career:
        if pub.ram_gb >= 16 and "SSD" in pub.storage_type:
            return 95, "Altamente compatible con ISC", "Capaz de ejecutar máquinas virtuales, contenedores Docker y entornos de desarrollo pesados sin saturar el sistema."
        elif pub.ram_gb >= 8:
            return 85, "Compatible con plan ISC", "Cumple con los requerimientos para programación en C++, Java, Bases de Datos y desarrollo Web."
        return 65, "Básico para ISC", "Puede presentar limitaciones en asignaturas con virtualización o emuladores de desarrollo móvil."

    # LCD: Ciencia de Datos
    if "CIENCIA DE DATOS" in career or "LCD" in career:
        if pub.ram_gb >= 16 and ("SSD" in pub.storage_type):
            return 94, "Altamente compatible con LCD", "Óptimo para manejo de DataFrames masivos en memoria, cálculo numérico intensivo y minería de datos."
        elif pub.ram_gb >= 8:
            return 80, "Compatible con análisis básico", "Apto para estadística descriptiva y programación con conjuntos de datos medianos."
        return 60, "Rendimiento limitado para LCD", "Capacidad de memoria ajustada para procesamiento de Big Data."

    # ISISA: Sistemas Automotrices
    if "AUTOMOTRICES" in career or "ISISA" in career:
        if (has_dedicated_gpu or is_m_series) and pub.ram_gb >= 16:
            return 95, "Altamente compatible con ISISA", "Excelente para modelado 3D (SolidWorks, AutoCAD), análisis por elementos finitos y simulación mecánica."
        elif pub.ram_gb >= 8:
            return 78, "Compatible para diseño ligero", "Adecuado para dibujo técnico y asignaturas de ciencias básicas."
        return 60, "Limitado para CAD", "No cuenta con aceleración gráfica óptima para renderizado automotriz."

    return 80, "Compatible con perfil", "Cumple los requerimientos generales de la formación en ingeniería."


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        career=user.career,
        semester=user.semester,
        interests=user.interests,
        phone=user.phone,
        is_verified=user.is_verified,
        verification_token=user.verification_token,
        es_institucional=user.es_institucional,
        has_complete_profile=has_complete_profile(user),
    )


def to_pub_response(pub: Publication, user: Optional[User], db: Optional[Session] = None) -> PublicationResponse:
    score, badge, detail = evaluate_compatibility(pub, user)
    is_fav = False
    if user and db:
        is_fav = db.scalar(
            select(Favorite).where(Favorite.user_id == user.id, Favorite.publication_id == pub.id)
        ) is not None

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
        ram_gb=pub.ram_gb,
        storage_gb=pub.storage_gb,
        storage_type=pub.storage_type,
        gpu=pub.gpu,
        screen_size=pub.screen_size,
        battery_condition=pub.battery_condition,
        price=pub.price,
        stock=pub.stock,
        description=pub.description,
        image_url=pub.image_url,
        # El teléfono solo se expone al propietario; los demás lo obtienen en /contact (requiere sesión)
        contact_phone=pub.contact_phone if (user and user.id == pub.seller_id) else None,
        status=pub.status,
        created_at=pub.created_at,
        updated_at=pub.updated_at,
        is_favorite=is_fav,
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
            # Migraciones directas para tablas existentes en PostgreSQL
            if not DATABASE_URL.startswith("sqlite"):
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'Alumno'"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS career VARCHAR(100)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS semester VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS interests VARCHAR(500)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(100)"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS es_institucional BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
                    conn.commit()

            # Actualizar por obsolescencia: publicaciones activas con más de 30 días pasan a "Obsoleta" (RN-08)
            with SessionLocal() as db:
                limit_date = datetime.now(timezone.utc) - timedelta(days=30)
                old_pubs = db.scalars(
                    select(Publication).where(Publication.status == "Activa", Publication.updated_at < limit_date)
                ).all()
                for op in old_pubs:
                    op.status = "Obsoleta"
                db.commit()
                seed_database(db)
            return
        except OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)


def seed_database(db: Session):
    existing_pubs = db.scalar(select(Publication).limit(1))
    if existing_pubs:
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
            interests="Desarrollo Web & Software, Inteligencia Artificial, Redes",
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
            ram_gb=32,
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
            ram_gb=16,
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
            ram_gb=16,
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
            ram_gb=8,
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
            ram_gb=16,
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
        db.add(item)
    db.commit()


# ----------------------------------------------------
# ENDPOINTS REST: AUTENTICACIÓN Y CUENTAS
# ----------------------------------------------------
@app.get("/")
def read_root():
    return {
        "status": "ok",
        "sistema": "ESCOM Hardware Match API",
        "tt": "2027-A196",
        "motor_bd": "Conectado",
    }


# CU: Crear Nueva Cuenta (Pág. 2)
@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    name = payload.name.strip()
    if not name or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="Datos de registro inválidos")

    # Flujo alterno: Correo ya registrado
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="El correo electrónico ya se encuentra registrado")

    # «include» Mandar Correo de Verificación (RN-01): Se genera token de verificación
    verification_token = secrets.token_hex(16)

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role or "Alumno",
        career=payload.career,
        semester=payload.semester,
        interests=payload.interests,
        phone=payload.phone,
        is_verified=False,
        verification_token=verification_token,
        es_institucional=False,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="No fue posible completar el registro") from None

    db.refresh(user)
    create_session(db, user, response)
    return to_user_response(user)


# CU: Confirmar Correo de Verificación (Pág. 4 & 5 - RN-01, RN-02)
@app.post("/auth/verify-email", response_model=UserResponse)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.verification_token == token))
    if not user:
        raise HTTPException(status_code=400, detail="Enlace o token de verificación inválido o expirado")

    user.is_verified = True
    user.verification_token = None

    # «include» Asignar Insignia de Cuenta Institucional (RN-02)
    user.es_institucional = is_institutional_domain(user.email)

    db.commit()
    db.refresh(user)
    return to_user_response(user)


# CU: Iniciar Sesión (Pág. 1)
@app.post("/auth/login", response_model=UserResponse)
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    create_session(db, user, response)
    return to_user_response(user)


# CU: Ver Perfil propio (Pág. 7)
@app.get("/auth/me", response_model=UserResponse)
def me(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    return to_user_response(user)


# CU: Editar Perfil (Académico) (Pág. 6)
@app.put("/auth/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if payload.career is not None:
        user.career = payload.career
    if payload.semester is not None:
        user.semester = payload.semester
    if payload.interests is not None:
        user.interests = payload.interests
    if payload.phone is not None:
        user.phone = payload.phone

    db.commit()
    db.refresh(user)
    return to_user_response(user)


# CU: Eliminar Perfil (Académico) (Pág. 8)
@app.delete("/auth/profile", response_model=UserResponse)
def delete_profile(
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    # Borra los datos del perfil académico (RN-03 impedirá búsqueda por compatibilidad)
    user.career = None
    user.semester = None
    user.interests = None
    db.commit()
    db.refresh(user)
    return to_user_response(user)


# Cerrar Sesión
@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == token_digest(raw_token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


# ----------------------------------------------------
# ENDPOINTS REST: PUBLICACIONES Y BÚSQUEDA
# ----------------------------------------------------

# CU: Buscar Publicaciones de Oferta (Pág. 16, 17, 18, 19, 20)
@app.get("/api/filters/options")
def get_filter_options(db: Session = Depends(get_db)):
    """Opciones dinámicas para los filtros del catálogo (marcas y rango de precios)."""
    active = Publication.status == "Activa"
    brands = db.scalars(select(Publication.brand).where(active).distinct().order_by(Publication.brand)).all()
    min_p, max_p = db.execute(
        select(func.min(Publication.price), func.max(Publication.price)).where(active)
    ).one()
    return {
        "brands": brands,
        "device_types": ["Laptop", "Tableta"],
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
    search: Optional[str] = Query(None, description="Búsqueda libre por texto"),
    device_type: Optional[str] = Query(None, description="Filtrar por 'Laptop' o 'Tableta'"),
    condition: Optional[str] = Query(None, description="Filtrar por estado del equipo"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    brand: Optional[str] = Query(None, description="Marca del equipo"),
    min_ram: Optional[int] = Query(None, ge=1, description="RAM mínima en GB"),
    min_storage: Optional[int] = Query(None, ge=1, description="Almacenamiento mínimo en GB"),
    storage_type: Optional[str] = Query(None, description="SSD NVMe, SSD SATA, HDD o eMMC"),
    gpu_type: Optional[str] = Query(None, description="'dedicada' o 'integrada'"),
    ipn_sellers_only: bool = Query(False, description="Solo vendedores con correo institucional"),
    sort_by: str = Query("recientes", description="recientes, precio_asc, precio_desc o compatibilidad"),
    only_compatible: bool = Query(False, description="Activar Búsqueda por Compatibilidad de Perfil (RN-05)"),
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)

    # RN-03: Si se activa compatibilidad pero el usuario no tiene perfil completo, emitir aviso/error controlado
    if only_compatible:
        if not user:
            raise HTTPException(status_code=400, detail="Debes iniciar sesión para activar el filtro de compatibilidad de perfil.")
        if not has_complete_profile(user):
            raise HTTPException(status_code=400, detail="Perfil académico incompleto (RN-03). Por favor completa tu carrera y semestre en tu perfil.")

    query = select(Publication).where(Publication.status == "Activa")

    if device_type and device_type != "Todos":
        query = query.where(Publication.device_type == device_type)

    if condition and condition != "Todas":
        query = query.where(Publication.condition == condition)

    if min_price is not None:
        query = query.where(Publication.price >= min_price)

    if max_price is not None:
        query = query.where(Publication.price <= max_price)

    if brand and brand != "Todas":
        query = query.where(Publication.brand.ilike(brand.strip()))

    if min_ram is not None:
        query = query.where(Publication.ram_gb >= min_ram)

    if min_storage is not None:
        query = query.where(Publication.storage_gb >= min_storage)

    if storage_type and storage_type != "Todos":
        query = query.where(Publication.storage_type == storage_type)

    if gpu_type in ("dedicada", "integrada"):
        is_integrated = or_(
            Publication.gpu.is_(None),
            *[Publication.gpu.ilike(f"%{term}%") for term in GPU_INTEGRADA_TERMS],
        )
        query = query.where(is_integrated if gpu_type == "integrada" else not_(is_integrated))

    if ipn_sellers_only:
        query = query.join(User, User.id == Publication.seller_id).where(User.es_institucional.is_(True))

    if search:
        st = f"%{search.strip().lower()}%"
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

    if only_compatible:
        # RN-05: Filtrar y priorizar aquellas con alta compatibilidad (>=80%)
        results = [r for r in results if (r.compatibility_score or 0) >= 80]
        results.sort(key=lambda x: (x.compatibility_score or 0), reverse=True)
    elif sort_by == "compatibilidad":
        results.sort(key=lambda x: (x.compatibility_score or 0), reverse=True)

    return results


# CU: Ver Detalle de Publicación de Oferta (Pág. 13 y 28)
@app.get("/api/publications/{publication_id}", response_model=PublicationResponse)
def get_publication(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return to_pub_response(pub, user, db)


# CU: Ver Datos de Contacto (Pág. 32 - RN-06, RN-07, RN-10)
@app.get("/api/publications/{publication_id}/contact")
def get_contact_info(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    pub = db.scalar(select(Publication).where(Publication.id == publication_id))
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    # RN-10: El sistema no muestra datos de contacto si el usuario es el propio ofertante
    if pub.seller_id == user.id:
        raise HTTPException(status_code=400, detail="Eres el vendedor de esta publicación.")

    contact = pub.contact_phone or pub.seller.phone or pub.seller.email
    return {
        "seller_name": pub.seller.name,
        "seller_role": pub.seller.role,
        "seller_career": pub.seller.career,
        "contact": contact,
    }


# CU: Crear Publicación de Oferta (Pág. 9 - RN-04, RN-08, RN-09)
@app.post("/api/publications", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
def create_publication(
    payload: PublicationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)

    # RN-09: Detección de duplicados contra publicaciones propias (activas u obsoletas)
    existing_duplicate = db.scalar(
        select(Publication).where(
            Publication.seller_id == user.id,
            Publication.brand.ilike(payload.brand.strip()),
            Publication.model.ilike(payload.model.strip()),
            Publication.processor.ilike(payload.processor.strip()),
            Publication.ram_gb == payload.ram_gb,
            Publication.storage_gb == payload.storage_gb,
        )
    )

    if existing_duplicate:
        # Coincidencia de especificaciones y observaciones/descripción: incrementa stock de la existente
        if existing_duplicate.description.strip().lower() == payload.description.strip().lower():
            existing_duplicate.stock += (payload.stock or 1)
            existing_duplicate.status = "Activa"
            existing_duplicate.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_duplicate)
            return to_pub_response(existing_duplicate, user, db)

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
        ram_gb=payload.ram_gb,
        storage_gb=payload.storage_gb,
        storage_type=payload.storage_type,
        gpu=payload.gpu.strip() if payload.gpu else "Integrada",
        screen_size=payload.screen_size or '15.6"',
        battery_condition=payload.battery_condition or "Buena",
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


# CU: Editar Publicación de Oferta (Pág. 10)
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
    pub.ram_gb = payload.ram_gb
    pub.storage_gb = payload.storage_gb
    pub.storage_type = payload.storage_type
    pub.gpu = payload.gpu.strip() if payload.gpu else "Integrada"
    pub.screen_size = payload.screen_size or pub.screen_size
    pub.battery_condition = payload.battery_condition or pub.battery_condition
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


# CU: Actualizar Estado de Publicación de Oferta (Pág. 14)
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

    # Paso 4: Si el nuevo estado es "Vendida": cantidad_disponible = 0
    invite_rating = False
    if payload.status == "Vendida":
        pub.stock = 0
        # Paso 5: Si el stock era 1 antes del cambio a "Vendida", ofrece invitar a valorar («extend»)
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
        "message": "Estado de la publicación actualizado.",
    }


# CU: Eliminar Publicación de Oferta (Pág. 11)
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

    db.delete(pub)
    db.commit()


# CU: Consultar Publicaciones de Ofertas Creadas (Pág. 12 - "Mis publicaciones")
@app.get("/api/my-publications", response_model=List[PublicationResponse])
def get_my_publications(
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    publications = db.scalars(
        select(Publication)
        .where(Publication.seller_id == user.id)
        .order_by(Publication.created_at.desc())
    ).all()
    return [to_pub_response(pub, user, db) for pub in publications]


# ----------------------------------------------------
# FAVORITOS (Pág. 42, 43, 44)
# ----------------------------------------------------
@app.get("/api/favorites", response_model=List[PublicationResponse])
def get_favorites(
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    favs = db.scalars(
        select(Publication)
        .join(Favorite, Favorite.publication_id == Publication.id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    ).all()
    return [to_pub_response(pub, user, db) for pub in favs]


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
        db.add(Favorite(user_id=user.id, publication_id=publication_id))
        db.commit()
    return {"message": "Publicación agregada a favoritos"}


@app.delete("/api/favorites/{publication_id}")
def remove_favorite(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    fav = db.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.publication_id == publication_id)
    )
    if fav:
        db.delete(fav)
        db.commit()
    return {"message": "Publicación removida de favoritos"}