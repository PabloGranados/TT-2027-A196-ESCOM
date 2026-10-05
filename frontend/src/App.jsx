import { useEffect, useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const CAREERS = [
  'Ingeniería en Sistemas Computacionales',
  'Ingeniería en Inteligencia Artificial',
  'Licenciatura en Ciencia de Datos',
  'Ingeniería en Sistemas Automotrices',
]

const SEMESTERS = [
  '1° semestre',
  '2° semestre',
  '3° semestre',
  '4° semestre',
  '5° semestre',
  '6° semestre',
  '7° semestre',
  '8° semestre',
]

const PREDEFINED_INTERESTS = [
  'Desarrollo de Software & Web',
  'Inteligencia Artificial & Deep Learning',
  'Ciencia de Datos & Big Data',
  'Sistemas Embebidos & Robótica',
  'Ciberseguridad & Redes',
  'Modelado 3D & CAD',
  'Programación Competitiva',
  'Gaming & Simulación Gráfica',
  'Ofimática, Apuntes & Productividad',
]

async function apiRequest(path, options = {}) {
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || 'Ocurrió un error en el servidor.')
    }
    return response.status === 204 ? null : response.json()
  } catch (err) {
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(
        'No fue posible conectar con el servidor backend en http://localhost:8000. Por favor verifica que el backend o Docker Compose estén corriendo (docker compose up).'
      )
    }
    throw err
  }
}

// ==========================================
// COMPONENTE: LOGIN & REGISTRO (Pág. 1, 2, 3)
// ==========================================
function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    role: 'Alumno',
    career: 'Ingeniería en Sistemas Computacionales',
    semester: '1° semestre',
    interests: [],
    phone: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [registeredUser, setRegisteredUser] = useState(null)

  const toggleInterest = (interest) => {
    setForm((prev) => {
      const exists = prev.interests.includes(interest)
      return {
        ...prev,
        interests: exists
          ? prev.interests.filter((i) => i !== interest)
          : [...prev.interests, interest],
      }
    })
  }

  const fillDemo = () => {
    setForm((prev) => ({
      ...prev,
      email: 'demo.escom@ipn.mx',
      password: 'Escom2027*',
    }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        const data = await apiRequest('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email: form.email, password: form.password }),
        })
        onAuthenticated(data)
      } else {
        const payload = {
          name: form.name,
          email: form.email,
          password: form.password,
          role: form.role,
          career: form.role === 'Alumno' ? form.career : null,
          semester: form.role === 'Alumno' ? form.semester : null,
          interests: form.interests.join(', '),
          phone: form.phone || null,
        }
        const data = await apiRequest('/auth/register', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setRegisteredUser(data)
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyNow = async (token) => {
    setLoading(true)
    try {
      const verified = await apiRequest(`/auth/verify-email?token=${token}`, { method: 'POST' })
      onAuthenticated(verified)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Vista de confirmación de correo (RN-01) tras registrarse
  if (registeredUser) {
    return (
      <main className="auth-shell">
        <section className="auth-panel panel verification-card">
          <span className="badge-school">IPN · ESCOM</span>
          <p className="eyebrow accent">RN-01 · Mandar Correo de Verificación</p>
          <h2>¡Cuenta creada exitosamente!</h2>
          <p className="auth-description">
            Se ha generado la cuenta y simulado el envío del correo de verificación a <strong>{registeredUser.email}</strong>.
          </p>

          <div className="verify-action-box">
            <p className="field-hint">
              Enlace de verificación generado (token: <code>{registeredUser.verification_token}</code>):
            </p>
            <button
              type="button"
              className="primary"
              onClick={() => handleVerifyNow(registeredUser.verification_token)}
              disabled={loading}
            >
              {loading ? 'Confirmando…' : '✔ Confirmar Correo de Verificación y Asignar Insignia'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => onAuthenticated(registeredUser)}
            >
              Continuar al sistema
            </button>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel panel">
        <div className="auth-header">
          <span className="badge-school">IPN · ESCOM</span>
          <p className="eyebrow accent">Trabajo Terminal 2027-A196</p>
          <h1>{mode === 'login' ? 'Iniciar Sesión' : 'Crear Nueva Cuenta'}</h1>
          <p className="auth-description">
            {mode === 'login'
              ? 'Accede para consultar ofertas o publicar tus laptops y tabletas en ESCOM.'
              : 'Regístrate para vincular tu carrera y recibir sugerencias adaptadas a tus materias.'}
          </p>
        </div>

        {mode === 'login' && (
          <div className="demo-credentials-banner">
            <div>
              <strong>Usuario Demo Institucional:</strong>
              <p>demo.escom@ipn.mx | Pass: Escom2027*</p>
            </div>
            <button type="button" className="ghost-btn" onClick={fillDemo}>
              Rellenar
            </button>
          </div>
        )}

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && (
            <>
              <label>
                Nombre completo
                <input
                  required
                  placeholder="Ej. Pablo Granados / Alan López"
                  maxLength="120"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>

              <div className="form-row">
                <label>
                  Rol en la institución
                  <select
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                  >
                    <option value="Alumno">Alumno</option>
                    <option value="Docente">Docente</option>
                    <option value="PAAE">PAAE (Personal de Apoyo)</option>
                    <option value="Externo">Comunidad Externa</option>
                  </select>
                </label>

                <label>
                  Teléfono / WhatsApp (Opcional)
                  <input
                    type="tel"
                    placeholder="Ej. 5548178950"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </label>
              </div>

              {form.role === 'Alumno' && (
                <div className="form-row">
                  <label>
                    Carrera (ESCOM)
                    <select
                      value={form.career}
                      onChange={(e) => setForm({ ...form, career: e.target.value })}
                    >
                      {CAREERS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Semestre
                    <select
                      value={form.semester}
                      onChange={(e) => setForm({ ...form, semester: e.target.value })}
                    >
                      {SEMESTERS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              <div className="interests-section">
                <span className="field-hint">Catálogo de intereses académicos:</span>
                <div className="chips-container">
                  {PREDEFINED_INTERESTS.map((interest) => {
                    const selected = form.interests.includes(interest)
                    return (
                      <button
                        type="button"
                        key={interest}
                        className={`chip ${selected ? 'chip-active' : ''}`}
                        onClick={() => toggleInterest(interest)}
                      >
                        {interest}
                      </button>
                    )
                  })}
                </div>
              </div>
            </>
          )}

          <label>
            Correo electrónico
            <input
              required
              type="email"
              placeholder="correo@ipn.mx o correo personal"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>

          <label>
            Contraseña
            <input
              required
              type="password"
              placeholder="Mínimo 8 caracteres"
              minLength="8"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <button className="primary auth-submit" type="submit" disabled={loading}>
            {loading ? 'Procesando…' : mode === 'login' ? 'Iniciar Sesión' : 'Crear Cuenta'}
          </button>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError('')
          }}
        >
          {mode === 'login' ? '¿No tienes cuenta? Crear Nueva Cuenta' : '¿Ya tienes una cuenta? Iniciar Sesión'}
        </button>
      </section>
    </main>
  )
}

// =========================================================================
// COMPONENTE: DETALLE DE PUBLICACIÓN (Ofertante / Interesado) (Pág. 13 & 28)
// =========================================================================
function PublicationModal({
  publication,
  currentUser,
  onClose,
  onStatusChange,
  onDelete,
  onToggleFavorite,
}) {
  const [contactData, setContactData] = useState(null)
  const [contactError, setContactError] = useState('')
  const [copiedLink, setCopiedLink] = useState(false)

  if (!publication) return null

  const isOwner = currentUser && currentUser.id === publication.seller_id

  const loadContact = async () => {
    setContactError('')
    try {
      const data = await apiRequest(`/api/publications/${publication.id}/contact`)
      setContactData(data)
    } catch (err) {
      setContactError(err.message)
    }
  }

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.origin + `#pub-${publication.id}`)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2500)
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-content panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={onClose} aria-label="Cerrar modal">
          ✕
        </button>

        <div className="modal-body-grid">
          <div className="modal-media">
            <img
              src={
                publication.image_url ||
                'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80'
              }
              alt={publication.title}
              className="modal-image"
            />
            <div className="modal-price-box">
              <span className="price-label">Precio Ofertado</span>
              <strong className="modal-price">MXN ${publication.price.toLocaleString()}</strong>
              <div className="stock-condition-row">
                <span className="condition-tag">{publication.condition}</span>
                <span className="stock-tag">Stock: {publication.stock} disp.</span>
                <span className={`status-pill status-${publication.status.toLowerCase()}`}>
                  {publication.status}
                </span>
              </div>
            </div>

            {/* Acciones del caso de uso */}
            <div className="modal-action-bar">
              <button type="button" className="ghost-btn" onClick={copyLink}>
                {copiedLink ? '✔ Enlace Copiado' : '🔗 Compartir Publicación'}
              </button>

              {!isOwner && (
                <button
                  type="button"
                  className={`ghost-btn ${publication.is_favorite ? 'fav-active' : ''}`}
                  onClick={() => onToggleFavorite(publication)}
                >
                  {publication.is_favorite ? '★ En Favoritos' : '☆ Guardar en Favoritos'}
                </button>
              )}
            </div>
          </div>

          <div className="modal-info">
            <div className="modal-header-badges">
              <span className="type-pill">{publication.device_type}</span>
              {publication.compatibility_score && (
                <span className="score-pill">
                  {publication.compatibility_score}% compatibilidad
                </span>
              )}
            </div>

            <h2>{publication.title}</h2>
            <p className="device-brand-model">
              <strong>{publication.brand}</strong> · {publication.model}
            </p>

            {publication.compatibility_badge && (
              <div className="compat-banner">
                <strong>{publication.compatibility_badge}</strong>
                <p>{publication.compatibility_detail}</p>
              </div>
            )}

            <h3>Ficha Técnica Estandarizada</h3>
            <div className="specs-table">
              <div className="spec-row">
                <span className="spec-key">Procesador (CPU)</span>
                <span className="spec-val">{publication.processor}</span>
              </div>
              <div className="spec-row">
                <span className="spec-key">Memoria RAM</span>
                <span className="spec-val">{publication.ram_gb} GB</span>
              </div>
              <div className="spec-row">
                <span className="spec-key">Almacenamiento</span>
                <span className="spec-val">
                  {publication.storage_gb} GB ({publication.storage_type})
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-key">Tarjeta Gráfica</span>
                <span className="spec-val">{publication.gpu || 'Integrada'}</span>
              </div>
              <div className="spec-row">
                <span className="spec-key">Pantalla</span>
                <span className="spec-val">{publication.screen_size || '15.6"'}</span>
              </div>
              <div className="spec-row">
                <span className="spec-key">Estado de Batería</span>
                <span className="spec-val">{publication.battery_condition || 'Buena'}</span>
              </div>
            </div>

            <h3>Descripción & Observaciones</h3>
            <p className="modal-desc">{publication.description}</p>

            {/* Bloque para Dueño (Pág. 13) vs Interesado (Pág. 28, 32) */}
            {isOwner ? (
              <div className="owner-controls-box">
                <h4>Gestión de Ofertante (Dueño de la Publicación)</h4>
                <div className="owner-btn-row">
                  {publication.status === 'Activa' && (
                    <button
                      type="button"
                      className="primary-small"
                      onClick={() => onStatusChange(publication.id, 'Vendida')}
                    >
                      Marcar como Vendida (Stock → 0)
                    </button>
                  )}
                  {publication.status === 'Vendida' && (
                    <button
                      type="button"
                      className="secondary-small"
                      onClick={() => onStatusChange(publication.id, 'Activa')}
                    >
                      Reactivar Publicación
                    </button>
                  )}
                  <button
                    type="button"
                    className="danger-btn"
                    onClick={() => onDelete(publication.id)}
                  >
                    Eliminar Publicación
                  </button>
                </div>
              </div>
            ) : (
              <div className="seller-box">
                <div className="seller-details">
                  <p className="seller-title">Publicado por:</p>
                  <strong>{publication.seller_name}</strong>
                  <span className="seller-meta">
                    {publication.seller_role} {publication.seller_career ? `· ${publication.seller_career}` : ''}
                    {publication.seller_es_institucional && (
                      <span className="badge-verified-inline">✔ Cuenta IPN</span>
                    )}
                  </span>
                </div>

                {!contactData ? (
                  <button type="button" className="primary" onClick={loadContact}>
                    Ver Datos de Contacto (RN-06, RN-07)
                  </button>
                ) : (
                  <div className="contact-revealed-box">
                    <p>
                      <strong>Contacto directo:</strong> {contactData.contact}
                    </p>
                    <a
                      href={`https://wa.me/52${contactData.contact.replace(/\D/g, '')}?text=Hola,%20me%20interesa%20tu%20equipo%20en%20ESCOM%20Hardware%20Match:%20${encodeURIComponent(publication.title)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="whatsapp-btn"
                    >
                      Abrir conversación en WhatsApp
                    </a>
                  </div>
                )}
                {contactError && <p className="form-error">{contactError}</p>}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// =========================================================================
// COMPONENTE: FORMULARIO CREAR PUBLICACIÓN DE OFERTA (Pág. 9 - RN-04, RN-09)
// =========================================================================
function CreatePublicationView({ onPublished, onCancel }) {
  const [form, setForm] = useState({
    title: '',
    device_type: 'Laptop',
    brand: '',
    model: '',
    condition: 'Usado - Como nuevo',
    processor: '',
    ram_gb: 16,
    storage_gb: 512,
    storage_type: 'SSD NVMe',
    gpu: 'Integrada',
    screen_size: '15.6"',
    battery_condition: 'Excelente (85%+ vida útil)',
    price: '',
    stock: 1,
    description: '',
    contact_phone: '',
    image_url: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError('')
    setSubmitting(true)

    try {
      const payload = {
        ...form,
        ram_gb: Number(form.ram_gb),
        storage_gb: Number(form.storage_gb),
        price: Number(form.price),
        stock: Number(form.stock || 1),
        image_url: form.image_url.trim() || null,
        contact_phone: form.contact_phone.trim() || null,
      }

      const created = await apiRequest('/api/publications', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onPublished(created)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="panel create-pub-panel">
      <div className="section-heading">
        <span className="badge-school">CU-03 · ESCOM</span>
        <p className="eyebrow accent">Ficha Técnica Estandarizada</p>
        <h2>Crear Publicación de Oferta de Laptop o Tableta</h2>
        <p className="subtitle">
          Completa los datos de hardware. El sistema ejecutará detección de duplicados (RN-09) y validará especificaciones (RN-04).
        </p>
      </div>

      {formError && <p className="form-error" role="alert">{formError}</p>}

      <form className="publication-form" onSubmit={handleSubmit}>
        <div className="form-group-card">
          <h3>1. Información General del Equipo</h3>
          <div className="form-grid-2">
            <label>
              Tipo de Dispositivo
              <select
                value={form.device_type}
                onChange={(e) => setForm({ ...form, device_type: e.target.value })}
              >
                <option value="Laptop">Laptop</option>
                <option value="Tableta">Tableta</option>
              </select>
            </label>

            <label>
              Condición del Equipo
              <select
                value={form.condition}
                onChange={(e) => setForm({ ...form, condition: e.target.value })}
              >
                <option value="Nuevo">Nuevo (Sellado)</option>
                <option value="Usado - Como nuevo">Usado - Como nuevo (Impecable)</option>
                <option value="Usado - Buen estado">Usado - Buen estado (Detalles leves de uso)</option>
                <option value="Usado - Con detalles">Usado - Con detalles de batería o estéticos</option>
              </select>
            </label>
          </div>

          <label>
            Título de la Publicación
            <input
              required
              placeholder="Ej. Dell Latitude 5420 - Core i5 / 16GB RAM / SSD 512GB"
              maxLength="200"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </label>

          <div className="form-grid-2">
            <label>
              Marca
              <input
                required
                placeholder="Ej. Dell, Lenovo, Apple, HP, Asus, Acer"
                maxLength="100"
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              />
            </label>

            <label>
              Modelo Exacto
              <input
                required
                placeholder="Ej. Latitude 5420 o Legion 5 15ACH6H"
                maxLength="150"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="form-group-card">
          <h3>2. Especificaciones Técnicas (Requerimientos CBF)</h3>
          <div className="form-grid-2">
            <label>
              Procesador (CPU)
              <input
                required
                placeholder="Ej. Intel Core i7-12700H, AMD Ryzen 7 5800H, Apple M2"
                maxLength="150"
                value={form.processor}
                onChange={(e) => setForm({ ...form, processor: e.target.value })}
              />
            </label>

            <label>
              Memoria RAM (GB)
              <select
                value={form.ram_gb}
                onChange={(e) => setForm({ ...form, ram_gb: Number(e.target.value) })}
              >
                <option value="4">4 GB</option>
                <option value="8">8 GB</option>
                <option value="12">12 GB</option>
                <option value="16">16 GB (Recomendado ESCOM)</option>
                <option value="24">24 GB</option>
                <option value="32">32 GB (Recomendado IIA / Big Data)</option>
                <option value="64">64 GB</option>
              </select>
            </label>
          </div>

          <div className="form-grid-2">
            <label>
              Almacenamiento (GB)
              <select
                value={form.storage_gb}
                onChange={(e) => setForm({ ...form, storage_gb: Number(e.target.value) })}
              >
                <option value="128">128 GB</option>
                <option value="256">256 GB</option>
                <option value="512">512 GB (Recomendado)</option>
                <option value="1024">1 TB (1024 GB)</option>
                <option value="2048">2 TB (2048 GB)</option>
              </select>
            </label>

            <label>
              Tecnología de Almacenamiento
              <select
                value={form.storage_type}
                onChange={(e) => setForm({ ...form, storage_type: e.target.value })}
              >
                <option value="SSD NVMe">SSD NVMe (Alto Rendimiento)</option>
                <option value="SSD SATA">SSD SATA</option>
                <option value="HDD">Disco Mecánico HDD</option>
                <option value="eMMC">Memoria Flash eMMC</option>
              </select>
            </label>
          </div>

          <div className="form-grid-3">
            <label>
              Tarjeta Gráfica (GPU)
              <input
                placeholder="Ej. NVIDIA RTX 3060, Apple M2 GPU, o Integrada"
                value={form.gpu}
                onChange={(e) => setForm({ ...form, gpu: e.target.value })}
              />
            </label>

            <label>
              Pantalla (Pulgadas / Panel)
              <input
                placeholder='Ej. 15.6" FHD 144Hz, 14" IPS Mate'
                value={form.screen_size}
                onChange={(e) => setForm({ ...form, screen_size: e.target.value })}
              />
            </label>

            <label>
              Estado de la Batería
              <input
                placeholder="Ej. 92% salud, 5 hrs continuas"
                value={form.battery_condition}
                onChange={(e) => setForm({ ...form, battery_condition: e.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="form-group-card">
          <h3>3. Aspectos Comerciales y Contacto</h3>
          <div className="form-grid-3">
            <label>
              Precio de Venta (MXN)
              <input
                required
                type="number"
                min="500"
                step="50"
                placeholder="Ej. 12500"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
              />
            </label>

            <label>
              Cantidad Disponible (Stock)
              <input
                required
                type="number"
                min="1"
                value={form.stock}
                onChange={(e) => setForm({ ...form, stock: e.target.value })}
              />
            </label>

            <label>
              WhatsApp / Teléfono
              <input
                type="tel"
                placeholder="Ej. 5548178950"
                value={form.contact_phone}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              />
            </label>
          </div>

          <label>
            URL de Fotografía del Equipo
            <input
              type="url"
              placeholder="https://ejemplo.com/laptop.jpg"
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
          </label>

          <label>
            Observaciones & Descripción
            <textarea
              required
              rows="4"
              placeholder="Indica detalles de uso, accesorios incluidos (cargador original, funda, caja) y disponibilidad para entrega en ESCOM."
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
        </div>

        <div className="cta-row-actions">
          <button type="submit" className="primary" disabled={submitting}>
            {submitting ? 'Publicando…' : 'Publicar Oferta en ESCOM'}
          </button>
          <button type="button" className="secondary" onClick={onCancel}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  )
}

// =========================================================================
// COMPONENTE: MIS PUBLICACIONES (Pág. 12)
// =========================================================================
function MyPublicationsView({ onSelectPub, onCreateNew, onDeletePub }) {
  const [myPubs, setMyPubs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = () => {
    setLoading(true)
    apiRequest('/api/my-publications')
      .then((data) => setMyPubs(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let ignore = false
    apiRequest('/api/my-publications')
      .then((data) => {
        if (!ignore) {
          setMyPubs(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message)
          setLoading(false)
        }
      })
    return () => {
      ignore = true
    }
  }, [])

  return (
    <section className="panel">
      <div className="section-heading-split">
        <div>
          <span className="badge-school">CU-04.5 · ESCOM</span>
          <p className="eyebrow accent">Gestión de Ofertas Propias</p>
          <h2>Mis Publicaciones Creadas</h2>
        </div>
        <button className="primary" onClick={onCreateNew}>
          + Crear Nueva Publicación
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}

      {loading ? (
        <p className="loading-message">Cargando tus publicaciones…</p>
      ) : myPubs.length === 0 ? (
        <div className="empty-state">
          <p>No tienes publicaciones de laptops o tabletas creadas actualmente.</p>
          <button className="primary" onClick={onCreateNew}>
            Crear mi primera publicación de oferta
          </button>
        </div>
      ) : (
        <div className="results-grid">
          {myPubs.map((pub) => (
            <article key={pub.id} className="offer-card">
              <div className="card-media-wrapper">
                <img
                  src={
                    pub.image_url ||
                    'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=600&q=80'
                  }
                  alt={pub.title}
                  className="card-thumb"
                />
                <span className={`type-pill-overlay status-${pub.status.toLowerCase()}`}>
                  {pub.status} (Stock: {pub.stock})
                </span>
              </div>

              <div className="card-content-body">
                <span className="brand-badge">{pub.brand} {pub.model}</span>
                <h4>{pub.title}</h4>

                <div className="tag-list">
                  <span className="tag">⚙️ {pub.processor}</span>
                  <span className="tag">🧠 {pub.ram_gb} GB RAM</span>
                  <span className="tag">💾 {pub.storage_gb} GB</span>
                </div>

                <div className="card-footer">
                  <div className="price-column">
                    <span className="currency-label">Precio</span>
                    <strong>MXN ${pub.price.toLocaleString()}</strong>
                  </div>
                  <div className="card-btn-group">
                    <button type="button" className="ghost-btn" onClick={() => onSelectPub(pub)}>
                      Ver Detalle
                    </button>
                    <button
                      type="button"
                      className="danger-btn"
                      onClick={async () => {
                        if (window.confirm('¿Deseas eliminar definitivamente esta publicación?')) {
                          await onDeletePub(pub.id)
                          loadData()
                        }
                      }}
                    >
                      Eliminar
                    </button>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

// =========================================================================
// COMPONENTE: FAVORITOS (Pág. 44)
// =========================================================================
function FavoritesView({ onSelectPub, onRemoveFav }) {
  const [favs, setFavs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let ignore = false
    apiRequest('/api/favorites')
      .then((data) => {
        if (!ignore) {
          setFavs(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [])

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="badge-school">Pág. 44</span>
        <p className="eyebrow accent">Tus Equipos Guardados</p>
        <h2>Consultar Favoritos</h2>
        <p className="subtitle">
          El listado refleja el estado en vivo y stock vigente de cada publicación guardada.
        </p>
      </div>

      {loading ? (
        <p className="loading-message">Cargando favoritos…</p>
      ) : favs.length === 0 ? (
        <div className="empty-state">
          <p>Aún no has agregado ninguna publicación a favoritos.</p>
        </div>
      ) : (
        <div className="results-grid">
          {favs.map((pub) => (
            <article key={pub.id} className="offer-card">
              <div className="card-content-body">
                <div className="card-header">
                  <span className="brand-badge">{pub.brand}</span>
                  <span className={`status-pill status-${pub.status.toLowerCase()}`}>
                    {pub.status}
                  </span>
                </div>
                <h4>{pub.title}</h4>
                <div className="tag-list">
                  <span className="tag">{pub.processor}</span>
                  <span className="tag">{pub.ram_gb} GB RAM</span>
                </div>
                <div className="card-footer">
                  <strong>MXN ${pub.price.toLocaleString()}</strong>
                  <div className="card-btn-group">
                    <button type="button" className="ghost-btn" onClick={() => onSelectPub(pub)}>
                      Ver
                    </button>
                    <button
                      type="button"
                      className="danger-btn"
                      onClick={async () => {
                        await onRemoveFav(pub)
                        setFavs(favs.filter((f) => f.id !== pub.id))
                      }}
                    >
                      Quitar
                    </button>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

// =========================================================================
// COMPONENTE: PERFIL DE USUARIO (Pág. 6, 7, 8)
// =========================================================================
function ProfileView({ user, onProfileUpdated }) {
  const [editing, setEditing] = useState(false)
  const [career, setCareer] = useState(user.career || 'Ingeniería en Sistemas Computacionales')
  const [semester, setSemester] = useState(user.semester || '1° semestre')
  const [interests, setInterests] = useState(user.interests || '')
  const [phone, setPhone] = useState(user.phone || '')
  const [msg, setMsg] = useState('')

  const saveProfile = async (e) => {
    e.preventDefault()
    try {
      const updated = await apiRequest('/auth/profile', {
        method: 'PUT',
        body: JSON.stringify({ career, semester, interests, phone }),
      })
      onProfileUpdated(updated)
      setEditing(false)
      setMsg('Perfil académico actualizado con éxito.')
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeleteAcademicProfile = async () => {
    if (
      window.confirm(
        '¿Deseas eliminar los datos de tu perfil académico? (RN-03: No podrás usar la búsqueda por compatibilidad hasta volver a completarlo).'
      )
    ) {
      try {
        const updated = await apiRequest('/auth/profile', { method: 'DELETE' })
        onProfileUpdated(updated)
        setMsg('Perfil académico eliminado.')
      } catch (err) {
        alert(err.message)
      }
    }
  }

  return (
    <section className="panel profile-panel">
      <div className="section-heading">
        <span className="badge-school">Pág. 6 & 7</span>
        <p className="eyebrow accent">Perfil Académico Institucional</p>
        <h2>{editing ? 'Editar Perfil Académico' : 'Ver Perfil Propio'}</h2>
      </div>

      {msg && <p className="success-banner">{msg}</p>}

      <div className="profile-grid">
        <div className="form-card">
          {!editing ? (
            <>
              <div className="profile-detail-row">
                <span className="spec-key">Nombre:</span>
                <strong>{user.name}</strong>
              </div>
              <div className="profile-detail-row">
                <span className="spec-key">Correo:</span>
                <strong>{user.email}</strong>
              </div>
              <div className="profile-detail-row">
                <span className="spec-key">Rol Institucional:</span>
                <strong>{user.role}</strong>
              </div>
              <div className="profile-detail-row">
                <span className="spec-key">Carrera:</span>
                <strong>{user.career || 'Sin especificar'}</strong>
              </div>
              <div className="profile-detail-row">
                <span className="spec-key">Semestre:</span>
                <strong>{user.semester || 'Sin especificar'}</strong>
              </div>
              <div className="profile-detail-row">
                <span className="spec-key">Intereses Académicos:</span>
                <p>{user.interests || 'Ninguno registrado'}</p>
              </div>

              <div className="profile-btn-row">
                <button type="button" className="primary" onClick={() => setEditing(true)}>
                  Editar Perfil Académico
                </button>
                {user.career && (
                  <button
                    type="button"
                    className="danger-btn"
                    onClick={handleDeleteAcademicProfile}
                  >
                    Eliminar Perfil Académico (Pág. 8)
                  </button>
                )}
              </div>
            </>
          ) : (
            <form onSubmit={saveProfile} className="auth-form">
              <label>
                Carrera
                <select value={career} onChange={(e) => setCareer(e.target.value)}>
                  {CAREERS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Semestre
                <select value={semester} onChange={(e) => setSemester(e.target.value)}>
                  {SEMESTERS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Teléfono / WhatsApp
                <input value={phone} onChange={(e) => setPhone(e.target.value)} />
              </label>

              <label>
                Intereses (Separados por coma)
                <input value={interests} onChange={(e) => setInterests(e.target.value)} />
              </label>

              <div className="profile-btn-row">
                <button type="submit" className="primary">
                  Guardar Cambios
                </button>
                <button type="button" className="secondary" onClick={() => setEditing(false)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>

        <aside className="summary-card">
          <h4>Insignias y Verificación</h4>
          <div className="insignia-badge-box">
            {user.es_institucional ? (
              <div className="verified-badge ipn-badge">
                ✔ Insignia de Cuenta Institucional IPN Asignada (RN-02)
              </div>
            ) : (
              <div className="unverified-badge">
                Cuenta sin dominio institucional oficial del IPN.
              </div>
            )}

            <div className="status-item">
              <span>Estado del perfil académico:</span>
              <strong>
                {user.has_complete_profile ? '✔ Completo (Apto para CBF)' : '⚠ Incompleto (RN-03)'}
              </strong>
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}

// =========================================================================
// COMPONENTE PRINCIPAL (APP)
// =========================================================================
function App() {
  const [activeView, setActiveView] = useState('inicio') // 'inicio', 'publicar', 'mis-publicaciones', 'favoritos', 'perfil'
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')

  // Catálogo de publicaciones
  const [publications, setPublications] = useState([])
  const [loadingPubs, setLoadingPubs] = useState(false)
  const [selectedPub, setSelectedPub] = useState(null)

  // Filtros (Pág. 16 a 20)
  const [filterSearch, setFilterSearch] = useState('')
  const [filterType, setFilterType] = useState('Todos')
  const [filterCondition, setFilterCondition] = useState('Todas')
  const [filterMaxPrice, setFilterMaxPrice] = useState(30000)
  const [onlyCompatible, setOnlyCompatible] = useState(false) // RN-05

  // Cargar usuario autenticado
  useEffect(() => {
    let ignore = false
    apiRequest('/auth/me')
      .then((u) => {
        if (!ignore) setUser(u)
      })
      .catch(() => {
        if (!ignore) setUser(null)
      })
      .finally(() => {
        if (!ignore) setAuthLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [])

  // Cargar publicaciones
  const fetchPublications = (compatFilter = onlyCompatible) => {
    setLoadingPubs(true)
    let url = `/api/publications?only_compatible=${compatFilter}`
    if (filterType !== 'Todos') url += `&device_type=${filterType}`
    if (filterCondition !== 'Todas') url += `&condition=${filterCondition}`
    if (filterMaxPrice) url += `&max_price=${filterMaxPrice}`
    if (filterSearch.trim()) url += `&search=${encodeURIComponent(filterSearch.trim())}`

    apiRequest(url)
      .then((data) => setPublications(data))
      .catch((err) => alert(err.message))
      .finally(() => setLoadingPubs(false))
  }

  useEffect(() => {
    if (!user) return
    let ignore = false
    let url = `/api/publications?only_compatible=${onlyCompatible}`
    if (filterType !== 'Todos') url += `&device_type=${filterType}`
    if (filterCondition !== 'Todas') url += `&condition=${filterCondition}`
    if (filterMaxPrice) url += `&max_price=${filterMaxPrice}`
    if (filterSearch.trim()) url += `&search=${encodeURIComponent(filterSearch.trim())}`

    apiRequest(url)
      .then((data) => {
        if (!ignore) setPublications(data)
      })
      .catch(() => {})
    return () => {
      ignore = true
    }
  }, [user, filterType, filterCondition, filterMaxPrice, filterSearch, onlyCompatible])

  // Desactivar / Eliminar filtros (Pág. 18)
  const resetFilters = () => {
    setFilterSearch('')
    setFilterType('Todos')
    setFilterCondition('Todas')
    setFilterMaxPrice(30000)
    setOnlyCompatible(false)
  }

  // Activar / Desactivar Compatibilidad (Pág. 19 & 20)
  const toggleCompatibility = () => {
    if (!onlyCompatible && user && !user.has_complete_profile) {
      alert(
        'Perfil académico incompleto (RN-03). Por favor accede a "Mi Perfil" y registra tu carrera y semestre antes de activar este filtro.'
      )
      return
    }
    const nextVal = !onlyCompatible
    setOnlyCompatible(nextVal)
    fetchPublications(nextVal)
  }

  const logout = async () => {
    setSessionError('')
    try {
      await apiRequest('/auth/logout', { method: 'POST' })
      setUser(null)
    } catch {
      setSessionError('No fue posible cerrar la sesión.')
    }
  }

  const handleStatusChange = async (pubId, nextStatus) => {
    try {
      const res = await apiRequest(`/api/publications/${pubId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      alert(res.message + (res.invite_rating ? ' (Stock era 1: Invita al comprador a valorar).' : ''))
      fetchPublications()
      setSelectedPub(null)
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeletePub = async (pubId) => {
    try {
      await apiRequest(`/api/publications/${pubId}`, { method: 'DELETE' })
      fetchPublications()
      setSelectedPub(null)
    } catch (err) {
      alert(err.message)
    }
  }

  const handleToggleFavorite = async (pub) => {
    try {
      if (pub.is_favorite) {
        await apiRequest(`/api/favorites/${pub.id}`, { method: 'DELETE' })
      } else {
        await apiRequest(`/api/favorites/${pub.id}`, { method: 'POST' })
      }
      fetchPublications()
      setSelectedPub(null)
    } catch (err) {
      alert(err.message)
    }
  }

  if (authLoading) {
    return (
      <main className="auth-shell">
        <p className="loading-message">Restaurando sesión institucional…</p>
      </main>
    )
  }

  if (!user) {
    return (
      <AuthScreen
        onAuthenticated={(u) => {
          setUser(u)
          fetchPublications(false)
        }}
      />
    )
  }

  return (
    <div className="app-shell">
      {/* BARRA SUPERIOR DE NAVEGACIÓN */}
      <header className="topbar">
        <div className="branding-container">
          <div className="ipn-logo-box">
            <span className="ipn-title">ESCOM · IPN</span>
          </div>
          <div>
            <h2 className="app-title">Hardware Match</h2>
            <p className="eyebrow accent">Mercado Académico de Laptops y Tabletas</p>
          </div>
        </div>

        <nav className="nav-tabs" aria-label="Navegación principal">
          {[
            { key: 'inicio', label: 'Explorar Ofertas' },
            { key: 'publicar', label: '+ Publicar Oferta' },
            { key: 'mis-publicaciones', label: 'Mis Publicaciones' },
            { key: 'favoritos', label: 'Favoritos' },
            { key: 'perfil', label: 'Mi Perfil' },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeView === tab.key ? 'tab active' : 'tab'}
              onClick={() => setActiveView(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="account-actions">
          <div className="user-info-chip">
            <span className="user-name">{user.name}</span>
            <span className="user-role-badge">
              {user.role} {user.career ? `· ${user.career.split(' ')[2] || user.career}` : ''}
              {user.es_institucional && ' 🎓'}
            </span>
          </div>
          <button type="button" className="tab logout-btn" onClick={logout}>
            Cerrar sesión
          </button>
        </div>
      </header>

      {sessionError && <p className="form-error session-error">{sessionError}</p>}

      <main className="content">
        {/* VISTA 1: INICIO / MARKETPLACE (Pág. 16 a 20) */}
        {activeView === 'inicio' && (
          <>
            <section className="hero-panel panel">
              <div className="hero-copy">
                <span className="hero-badge">Plan de Estudios 2020 · ESCOM</span>
                <h1>Equipos contrastados contra tus materias y proyectos.</h1>
                <p className="lead">
                  Compara especificaciones técnicas de laptops y tabletas ofertadas por la comunidad.
                  El sistema evalúa el procesador, RAM y tarjeta gráfica con base en los planes de estudio.
                </p>

                <div className="cta-row">
                  <button type="button" className="primary" onClick={() => setActiveView('publicar')}>
                    + Publicar Laptop o Tableta
                  </button>
                  <button
                    type="button"
                    className={`secondary ${onlyCompatible ? 'filter-active-btn' : ''}`}
                    onClick={toggleCompatibility}
                  >
                    {onlyCompatible
                      ? 'Desactivar Búsqueda por Compatibilidad (Pág. 20)'
                      : '⭐ Activar Búsqueda por Compatibilidad (RN-05)'}
                  </button>
                </div>
              </div>

              <div className="hero-profile-summary">
                <h4>Tu Perfil Académico</h4>
                <div className="profile-pill-item">
                  <span>Carrera:</span>
                  <strong>{user.career || 'Comunidad General'}</strong>
                </div>
                <div className="profile-pill-item">
                  <span>Semestre:</span>
                  <strong>{user.semester || 'N/A'}</strong>
                </div>
                <div className="profile-pill-item">
                  <span>Insignia:</span>
                  <strong>{user.es_institucional ? '✔ Alumno IPN' : 'General'}</strong>
                </div>
              </div>
            </section>

            {/* BARRA DE BÚSQUEDA Y FILTROS (Pág. 16, 17, 18) */}
            <section className="filters-panel panel">
              <div className="filters-grid">
                <div className="filter-item search-grow">
                  <label>
                    Buscar por modelo, marca o CPU:
                    <input
                      type="search"
                      placeholder="Ej. Ryzen 7, MacBook, ThinkPad, RTX 3060..."
                      value={filterSearch}
                      onChange={(e) => setFilterSearch(e.target.value)}
                    />
                  </label>
                </div>

                <div className="filter-item">
                  <label>
                    Categoría:
                    <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                      <option value="Todos">Todos</option>
                      <option value="Laptop">Laptops</option>
                      <option value="Tableta">Tabletas</option>
                    </select>
                  </label>
                </div>

                <div className="filter-item">
                  <label>
                    Condición:
                    <select
                      value={filterCondition}
                      onChange={(e) => setFilterCondition(e.target.value)}
                    >
                      <option value="Todas">Todas</option>
                      <option value="Nuevo">Nuevo</option>
                      <option value="Usado - Como nuevo">Como nuevo</option>
                      <option value="Usado - Buen estado">Buen estado</option>
                      <option value="Usado - Con detalles">Con detalles</option>
                    </select>
                  </label>
                </div>

                <div className="filter-item range-item">
                  <label>
                    Presupuesto Máximo:
                    <div className="range-with-value">
                      <input
                        type="range"
                        min="5000"
                        max="40000"
                        step="1000"
                        value={filterMaxPrice}
                        onChange={(e) => setFilterMaxPrice(Number(e.target.value))}
                      />
                      <span className="budget-value">MXN ${filterMaxPrice.toLocaleString()}</span>
                    </div>
                  </label>
                </div>

                <div className="filter-reset-col">
                  <button type="button" className="ghost-btn" onClick={resetFilters}>
                    Eliminar Filtros (Pág. 18)
                  </button>
                </div>
              </div>
            </section>

            {/* LISTADO DE PUBLICACIONES */}
            <section className="panel results-panel">
              <div className="section-heading-split">
                <div>
                  <p className="eyebrow accent">Catálogo de Ofertas</p>
                  <h3>
                    {publications.length} ofertas disponibles
                    {onlyCompatible && ' (Filtradas por compatibilidad)'}
                  </h3>
                </div>
                {loadingPubs && <span className="loading-tag">Actualizando catálogo…</span>}
              </div>

              {publications.length === 0 ? (
                <div className="empty-state">
                  <p>No se encontraron publicaciones que coincidan con los filtros de búsqueda.</p>
                  <button className="secondary" onClick={resetFilters}>
                    Eliminar Filtros de Búsqueda
                  </button>
                </div>
              ) : (
                <div className="results-grid">
                  {publications.map((pub) => (
                    <article key={pub.id} className="offer-card">
                      <div className="card-media-wrapper">
                        <img
                          src={
                            pub.image_url ||
                            'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=600&q=80'
                          }
                          alt={pub.title}
                          className="card-thumb"
                          loading="lazy"
                        />
                        <span className="type-pill-overlay">{pub.device_type}</span>
                        <span className={`status-pill-badge status-${pub.status.toLowerCase()}`}>
                          {pub.status}
                        </span>
                      </div>

                      <div className="card-content-body">
                        <div className="card-header">
                          <span className="brand-badge">{pub.brand}</span>
                          {pub.compatibility_score && (
                            <span
                              className={`score-pill ${
                                pub.compatibility_score >= 90 ? 'score-high' : ''
                              }`}
                            >
                              {pub.compatibility_score}% match
                            </span>
                          )}
                        </div>

                        <h4>{pub.title}</h4>

                        {pub.compatibility_badge && (
                          <p className="offer-badge">{pub.compatibility_badge}</p>
                        )}

                        <div className="tag-list">
                          <span className="tag">⚙️ {pub.processor}</span>
                          <span className="tag">🧠 {pub.ram_gb} GB RAM</span>
                          <span className="tag">💾 {pub.storage_gb} GB {pub.storage_type}</span>
                          {pub.gpu && pub.gpu !== 'Integrada' && (
                            <span className="tag tag-gpu">🎮 {pub.gpu}</span>
                          )}
                        </div>

                        <p className="offer-condition-hint">
                          Condición: <strong>{pub.condition}</strong> (Stock: {pub.stock})
                        </p>

                        <div className="card-footer">
                          <div className="price-column">
                            <span className="currency-label">Precio</span>
                            <strong>MXN ${pub.price.toLocaleString()}</strong>
                          </div>
                          <button
                            type="button"
                            className="primary-small"
                            onClick={() => setSelectedPub(pub)}
                          >
                            Entrar a la Oferta
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        {/* VISTA 2: PUBLICAR OFERTA (Pág. 9) */}
        {activeView === 'publicar' && (
          <CreatePublicationView
            onPublished={(newPub) => {
              fetchPublications()
              setSelectedPub(newPub) // «include» Ver Detalle de Publicación de Oferta (Pág. 9, paso 8)
              setActiveView('inicio')
            }}
            onCancel={() => setActiveView('inicio')}
          />
        )}

        {/* VISTA 3: MIS PUBLICACIONES (Pág. 12) */}
        {activeView === 'mis-publicaciones' && (
          <MyPublicationsView
            onSelectPub={(pub) => setSelectedPub(pub)}
            onCreateNew={() => setActiveView('publicar')}
            onDeletePub={handleDeletePub}
          />
        )}

        {/* VISTA 4: FAVORITOS (Pág. 44) */}
        {activeView === 'favoritos' && (
          <FavoritesView
            onSelectPub={(pub) => setSelectedPub(pub)}
            onRemoveFav={handleToggleFavorite}
          />
        )}

        {/* VISTA 5: MI PERFIL (Pág. 6, 7, 8) */}
        {activeView === 'perfil' && (
          <ProfileView user={user} onProfileUpdated={(updated) => setUser(updated)} />
        )}
      </main>

      {/* MODAL DE PUBLICACIÓN (Ver Detalle Ofertante / Entrar Oferta Interesado) */}
      {selectedPub && (
        <PublicationModal
          publication={selectedPub}
          currentUser={user}
          onClose={() => setSelectedPub(null)}
          onStatusChange={handleStatusChange}
          onDelete={handleDeletePub}
          onToggleFavorite={handleToggleFavorite}
        />
      )}
    </div>
  )
}

export default App
