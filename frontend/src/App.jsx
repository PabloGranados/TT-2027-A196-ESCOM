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
  'Desarrollo de Software',
  'Inteligencia Artificial',
  'Ciencia de Datos',
  'Sistemas Embebidos',
  'Ciberseguridad',
  'Modelado 3D / CAD',
  'Programación Competitiva',
  'Videojuegos y Gráficos',
  'Ofimática y Estudio',
]

const EMPTY_FILTERS = {
  search: '',
  device_type: '',
  sort_by: 'recientes',
  brand: '',
  condition: '',
  min_ram: '',
  min_storage: '',
  storage_type: '',
  gpu_type: '',
  min_price: '',
  max_price: '',
  ipn_sellers_only: false,
  only_compatible: false,
}

function buildPublicationsUrl(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value === '' || value === false || value === null) return
    params.set(key, typeof value === 'string' ? value.trim() : value)
  })
  return `/api/publications?${params.toString()}`
}

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
        'No se pudo conectar con el servidor (http://localhost:8000). Asegúrate de tener los servicios activos.'
      )
    }
    throw err
  }
}

// =========================================================================
// PANTALLA DE ACCESO (LOGIN & REGISTRO)
// =========================================================================
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
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password,
          role: form.role,
          career: form.role === 'Alumno' ? form.career : null,
          semester: form.role === 'Alumno' ? form.semester : null,
          interests: form.interests.join(', '),
          phone: form.phone.trim() || null,
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

  const handleVerifyEmail = async (token) => {
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

  // Notificación amigable tras el registro
  if (registeredUser) {
    return (
      <main className="auth-shell">
        <section className="auth-panel panel text-center">
          <div className="ipn-pill">ESCOM · IPN</div>
          <h2>¡Cuenta creada con éxito!</h2>
          <p className="auth-description">
            Se ha vinculado tu cuenta para <strong>{registeredUser.email}</strong>.
            Puedes confirmar tu correo ahora para habilitar la insignia institucional.
          </p>

          <div className="auth-actions-stacked">
            <button
              type="button"
              className="primary"
              onClick={() => handleVerifyEmail(registeredUser.verification_token)}
              disabled={loading}
            >
              {loading ? 'Confirmando…' : 'Confirmar correo y entrar'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => onAuthenticated(registeredUser)}
            >
              Continuar al catálogo
            </button>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel panel">
        <header className="auth-header">
          <div className="brand-logo">
            <span className="brand-badge-ipn">ESCOM</span>
            <span className="brand-name">Hardware Match</span>
          </div>
          <h1>{mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}</h1>
          <p className="auth-description">
            {mode === 'login'
              ? 'Encuentra laptops y tabletas adaptadas a las exigencias de tu carrera.'
              : 'Regístrate con tu perfil académico para consultar y publicar ofertas.'}
          </p>
        </header>

        {mode === 'login' && (
          <div className="demo-box">
            <div className="demo-info">
              <span className="demo-tag">Cuenta de prueba</span>
              <p className="demo-text">demo.escom@ipn.mx · Escom2027*</p>
            </div>
            <button type="button" className="ghost-btn-sm" onClick={fillDemo}>
              Autocompletar
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
                  placeholder="Tu nombre y apellidos"
                  maxLength="120"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>

              <div className="form-grid-2">
                <label>
                  Rol en la comunidad
                  <select
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                  >
                    <option value="Alumno">Estudiante</option>
                    <option value="Docente">Docente</option>
                    <option value="PAAE">Personal de Apoyo (PAAE)</option>
                    <option value="Externo">Externo</option>
                  </select>
                </label>

                <label>
                  Teléfono / WhatsApp (opcional)
                  <input
                    type="tel"
                    placeholder="Ej. 55 1234 5678"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </label>
              </div>

              {form.role === 'Alumno' && (
                <div className="form-grid-2">
                  <label>
                    Carrera
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

              <div className="interests-box">
                <span className="field-label">Áreas de interés académico:</span>
                <div className="chips-wrap">
                  {PREDEFINED_INTERESTS.map((interest) => {
                    const selected = form.interests.includes(interest)
                    return (
                      <button
                        type="button"
                        key={interest}
                        className={`chip-btn ${selected ? 'active' : ''}`}
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
              placeholder="tu.correo@ipn.mx o personal"
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

          <button className="primary submit-btn" type="submit" disabled={loading}>
            {loading ? 'Cargando…' : mode === 'login' ? 'Entrar' : 'Registrarme'}
          </button>
        </form>

        <footer className="auth-footer">
          <button
            className="link-btn"
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError('')
            }}
          >
            {mode === 'login'
              ? '¿No tienes cuenta? Regístrate aquí'
              : '¿Ya tienes cuenta? Inicia sesión'}
          </button>
        </footer>
      </section>
    </main>
  )
}

// =========================================================================
// MODAL DE DETALLE DE LA PUBLICACIÓN
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
    navigator.clipboard.writeText(window.location.origin + `#oferta-${publication.id}`)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2000)
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Cerrar">
          ✕
        </button>

        <div className="modal-grid">
          <div className="modal-gallery">
            <img
              src={
                publication.image_url ||
                'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80'
              }
              alt={publication.title}
              className="modal-photo"
            />
            <div className="modal-pricing-card">
              <span className="price-tag">${publication.price.toLocaleString()} MXN</span>
              <div className="modal-meta-row">
                <span className="meta-badge">{publication.condition}</span>
                <span className="meta-badge">Stock: {publication.stock}</span>
                <span className={`status-badge status-${publication.status.toLowerCase()}`}>
                  {publication.status}
                </span>
              </div>
            </div>

            <div className="modal-quick-actions">
              <button type="button" className="secondary-sm" onClick={copyLink}>
                {copiedLink ? 'Enlace copiado' : 'Compartir enlace'}
              </button>
              {!isOwner && (
                <button
                  type="button"
                  className={`secondary-sm ${publication.is_favorite ? 'btn-fav-active' : ''}`}
                  onClick={() => onToggleFavorite(publication)}
                >
                  {publication.is_favorite ? 'Guardado en favoritos' : 'Guardar en favoritos'}
                </button>
              )}
            </div>
          </div>

          <div className="modal-details">
            <div className="modal-top-meta">
              <span className="device-pill">{publication.device_type}</span>
              {publication.compatibility_score && (
                <span className="compat-score-pill">
                  {publication.compatibility_score}% compatible
                </span>
              )}
            </div>

            <h2 className="modal-heading">{publication.title}</h2>
            <p className="device-subtitle">
              {publication.brand} · {publication.model}
            </p>

            {publication.compatibility_badge && (
              <div className="compatibility-alert">
                <strong>{publication.compatibility_badge}</strong>
                <p>{publication.compatibility_detail}</p>
              </div>
            )}

            <h3 className="section-title">Especificaciones técnicas</h3>
            <div className="spec-list">
              <div className="spec-item">
                <span>Procesador</span>
                <strong>{publication.processor}</strong>
              </div>
              <div className="spec-item">
                <span>Memoria RAM</span>
                <strong>{publication.ram_gb} GB</strong>
              </div>
              <div className="spec-item">
                <span>Almacenamiento</span>
                <strong>
                  {publication.storage_gb} GB ({publication.storage_type})
                </strong>
              </div>
              <div className="spec-item">
                <span>Gráficos (GPU)</span>
                <strong>{publication.gpu || 'Integrada'}</strong>
              </div>
              <div className="spec-item">
                <span>Pantalla</span>
                <strong>{publication.screen_size || '15.6"'}</strong>
              </div>
              <div className="spec-item">
                <span>Batería</span>
                <strong>{publication.battery_condition || 'Normal'}</strong>
              </div>
            </div>

            <h3 className="section-title">Descripción del equipo</h3>
            <p className="modal-text">{publication.description}</p>

            {isOwner ? (
              <div className="owner-box">
                <span className="box-title">Opciones de publicación</span>
                <div className="owner-buttons">
                  {publication.status === 'Activa' && (
                    <button
                      type="button"
                      className="primary-sm"
                      onClick={() => onStatusChange(publication.id, 'Vendida')}
                    >
                      Marcar como vendida
                    </button>
                  )}
                  {publication.status === 'Vendida' && (
                    <button
                      type="button"
                      className="secondary-sm"
                      onClick={() => onStatusChange(publication.id, 'Activa')}
                    >
                      Reactivar oferta
                    </button>
                  )}
                  <button
                    type="button"
                    className="danger-sm"
                    onClick={() => onDelete(publication.id)}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            ) : (
              <div className="seller-box">
                <div className="seller-info">
                  <span className="seller-label">Vendedor</span>
                  <div className="seller-name-row">
                    <strong>{publication.seller_name}</strong>
                    {publication.seller_es_institucional && (
                      <span className="ipn-verify-tag">IPN</span>
                    )}
                  </div>
                  <span className="seller-role-text">
                    {publication.seller_role}
                    {publication.seller_career ? ` · ${publication.seller_career}` : ''}
                  </span>
                </div>

                {!contactData ? (
                  <button type="button" className="primary" onClick={loadContact}>
                    Contactar al vendedor
                  </button>
                ) : (
                  <div className="contact-revealed">
                    <p className="contact-number">
                      Teléfono: <strong>{contactData.contact}</strong>
                    </p>
                    <a
                      href={`https://wa.me/52${contactData.contact.replace(/\D/g, '')}?text=Hola,%20me%20interesa%20tu%20equipo%20en%20Hardware%20Match:%20${encodeURIComponent(publication.title)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="whatsapp-btn"
                    >
                      Enviar mensaje por WhatsApp
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
// FORMULARIO DE PUBLICACIÓN DE OFERTA
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
    battery_condition: 'Buen estado',
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
        title: form.title.trim(),
        brand: form.brand.trim(),
        model: form.model.trim(),
        processor: form.processor.trim(),
        ram_gb: Number(form.ram_gb),
        storage_gb: Number(form.storage_gb),
        price: Number(form.price),
        stock: Number(form.stock || 1),
        description: form.description.trim(),
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
    <section className="panel form-panel">
      <header className="panel-header">
        <h2>Publicar laptop o tableta</h2>
        <p className="panel-subtitle">
          Ingresa los detalles técnicos de tu equipo para que los compradores puedan evaluar su compatibilidad.
        </p>
      </header>

      {formError && <p className="form-error" role="alert">{formError}</p>}

      <form className="main-form" onSubmit={handleSubmit}>
        <div className="form-section">
          <span className="section-num">1. Datos generales</span>
          <div className="form-grid-2">
            <label>
              Tipo de equipo
              <select
                value={form.device_type}
                onChange={(e) => setForm({ ...form, device_type: e.target.value })}
              >
                <option value="Laptop">Laptop</option>
                <option value="Tableta">Tableta</option>
              </select>
            </label>

            <label>
              Condición
              <select
                value={form.condition}
                onChange={(e) => setForm({ ...form, condition: e.target.value })}
              >
                <option value="Nuevo">Nuevo (Sellado)</option>
                <option value="Usado - Como nuevo">Como nuevo (Sin detalles)</option>
                <option value="Usado - Buen estado">Buen estado (Uso normal)</option>
                <option value="Usado - Con detalles">Con detalles de uso</option>
              </select>
            </label>
          </div>

          <label>
            Título descriptivo
            <input
              required
              placeholder="Ej. Dell Latitude 5420 · Core i5 / 16GB RAM / 512GB SSD"
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
                placeholder="Ej. Dell, Lenovo, Apple, HP, Asus"
                maxLength="100"
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              />
            </label>

            <label>
              Modelo
              <input
                required
                placeholder="Ej. Latitude 5420 o MacBook Air M2"
                maxLength="150"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="form-section">
          <span className="section-num">2. Ficha técnica</span>
          <div className="form-grid-2">
            <label>
              Procesador (CPU)
              <input
                required
                placeholder="Ej. Intel Core i5-1135G7, AMD Ryzen 7 5800H, Apple M2"
                maxLength="150"
                value={form.processor}
                onChange={(e) => setForm({ ...form, processor: e.target.value })}
              />
            </label>

            <label>
              Memoria RAM
              <select
                value={form.ram_gb}
                onChange={(e) => setForm({ ...form, ram_gb: Number(e.target.value) })}
              >
                <option value="4">4 GB</option>
                <option value="8">8 GB</option>
                <option value="12">12 GB</option>
                <option value="16">16 GB</option>
                <option value="24">24 GB</option>
                <option value="32">32 GB</option>
                <option value="64">64 GB</option>
              </select>
            </label>
          </div>

          <div className="form-grid-2">
            <label>
              Capacidad de disco
              <select
                value={form.storage_gb}
                onChange={(e) => setForm({ ...form, storage_gb: Number(e.target.value) })}
              >
                <option value="128">128 GB</option>
                <option value="256">256 GB</option>
                <option value="512">512 GB</option>
                <option value="1024">1 TB (1024 GB)</option>
                <option value="2048">2 TB (2048 GB)</option>
              </select>
            </label>

            <label>
              Tipo de almacenamiento
              <select
                value={form.storage_type}
                onChange={(e) => setForm({ ...form, storage_type: e.target.value })}
              >
                <option value="SSD NVMe">SSD NVMe</option>
                <option value="SSD SATA">SSD SATA</option>
                <option value="HDD">Disco Mecánico (HDD)</option>
                <option value="eMMC">eMMC</option>
              </select>
            </label>
          </div>

          <div className="form-grid-3">
            <label>
              Tarjeta gráfica (GPU)
              <input
                placeholder="Ej. RTX 3050 o Integrada"
                value={form.gpu}
                onChange={(e) => setForm({ ...form, gpu: e.target.value })}
              />
            </label>

            <label>
              Tamaño de pantalla
              <input
                placeholder='Ej. 14", 15.6", 11"'
                value={form.screen_size}
                onChange={(e) => setForm({ ...form, screen_size: e.target.value })}
              />
            </label>

            <label>
              Estado de la batería
              <input
                placeholder="Ej. 90% salud, dura 5 hrs"
                value={form.battery_condition}
                onChange={(e) => setForm({ ...form, battery_condition: e.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="form-section">
          <span className="section-num">3. Precio y entrega</span>
          <div className="form-grid-3">
            <label>
              Precio (MXN)
              <input
                required
                type="number"
                min="500"
                step="50"
                placeholder="Ej. 11000"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
              />
            </label>

            <label>
              Piezas disponibles
              <input
                required
                type="number"
                min="1"
                value={form.stock}
                onChange={(e) => setForm({ ...form, stock: e.target.value })}
              />
            </label>

            <label>
              Teléfono de contacto
              <input
                type="tel"
                placeholder="Ej. 55 1234 5678"
                value={form.contact_phone}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              />
            </label>
          </div>

          <label>
            Enlace de foto (opcional)
            <input
              type="url"
              placeholder="https://servidor.com/foto.jpg"
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
          </label>

          <label>
            Descripción y detalles
            <textarea
              required
              rows="4"
              placeholder="Incluye accesorios incluidos (cargador original, funda), estado estético y horarios o lugar de entrega dentro de la escuela."
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
        </div>

        <div className="form-actions-bar">
          <button type="submit" className="primary" disabled={submitting}>
            {submitting ? 'Publicando…' : 'Publicar oferta'}
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
// MIS PUBLICACIONES
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
      <div className="section-head">
        <div>
          <h2>Mis publicaciones</h2>
          <p className="panel-subtitle">Equipos que tienes actualmente a la venta.</p>
        </div>
        <button className="primary-sm" onClick={onCreateNew}>
          + Nueva publicación
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}

      {loading ? (
        <p className="muted-text">Cargando publicaciones…</p>
      ) : myPubs.length === 0 ? (
        <div className="empty-box">
          <p>No tienes publicaciones activas.</p>
          <button className="primary" onClick={onCreateNew}>
            Crear publicación
          </button>
        </div>
      ) : (
        <div className="catalog-grid">
          {myPubs.map((pub) => (
            <article key={pub.id} className="card-item">
              <div className="card-media">
                <img
                  src={
                    pub.image_url ||
                    'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=600&q=80'
                  }
                  alt={pub.title}
                  className="card-img"
                />
                <span className={`card-badge-status status-${pub.status.toLowerCase()}`}>
                  {pub.status} (Stock: {pub.stock})
                </span>
              </div>

              <div className="card-body">
                <span className="card-brand">{pub.brand} {pub.model}</span>
                <h4 className="card-title">{pub.title}</h4>

                <div className="specs-chips">
                  <span>{pub.processor}</span>
                  <span>{pub.ram_gb} GB RAM</span>
                  <span>{pub.storage_gb} GB</span>
                </div>

                <div className="card-bottom">
                  <strong className="card-price">${pub.price.toLocaleString()} MXN</strong>
                  <div className="card-actions">
                    <button type="button" className="secondary-sm" onClick={() => onSelectPub(pub)}>
                      Detalles
                    </button>
                    <button
                      type="button"
                      className="danger-sm"
                      onClick={async () => {
                        if (window.confirm('¿Seguro que deseas eliminar esta publicación?')) {
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
// FAVORITOS
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
      <header className="panel-header">
        <h2>Favoritos</h2>
        <p className="panel-subtitle">Publicaciones que has guardado para consultar después.</p>
      </header>

      {loading ? (
        <p className="muted-text">Cargando favoritos…</p>
      ) : favs.length === 0 ? (
        <div className="empty-box">
          <p>Aún no has guardado ninguna publicación.</p>
        </div>
      ) : (
        <div className="catalog-grid">
          {favs.map((pub) => (
            <article key={pub.id} className="card-item">
              <div className="card-body">
                <span className="card-brand">{pub.brand}</span>
                <h4 className="card-title">{pub.title}</h4>
                <div className="specs-chips">
                  <span>{pub.processor}</span>
                  <span>{pub.ram_gb} GB RAM</span>
                </div>
                <div className="card-bottom">
                  <strong className="card-price">${pub.price.toLocaleString()} MXN</strong>
                  <div className="card-actions">
                    <button type="button" className="secondary-sm" onClick={() => onSelectPub(pub)}>
                      Ver
                    </button>
                    <button
                      type="button"
                      className="danger-sm"
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
// PERFIL DE USUARIO
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
      setMsg('Perfil actualizado con éxito.')
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeleteProfile = async () => {
    if (window.confirm('¿Deseas restablecer los datos de tu carrera y semestre?')) {
      try {
        const updated = await apiRequest('/auth/profile', { method: 'DELETE' })
        onProfileUpdated(updated)
        setMsg('Perfil académico restablecido.')
      } catch (err) {
        alert(err.message)
      }
    }
  }

  return (
    <section className="panel profile-section">
      <header className="panel-header">
        <h2>{editing ? 'Editar perfil académico' : 'Mi perfil'}</h2>
      </header>

      {msg && <p className="success-banner">{msg}</p>}

      <div className="profile-layout">
        <div className="profile-card">
          {!editing ? (
            <>
              <div className="info-row">
                <span className="info-label">Nombre</span>
                <strong>{user.name}</strong>
              </div>
              <div className="info-row">
                <span className="info-label">Correo</span>
                <strong>{user.email}</strong>
              </div>
              <div className="info-row">
                <span className="info-label">Rol</span>
                <strong>{user.role}</strong>
              </div>
              <div className="info-row">
                <span className="info-label">Carrera</span>
                <strong>{user.career || 'No asignada'}</strong>
              </div>
              <div className="info-row">
                <span className="info-label">Semestre</span>
                <strong>{user.semester || 'No asignado'}</strong>
              </div>
              <div className="info-row">
                <span className="info-label">Intereses</span>
                <p>{user.interests || 'Sin registrar'}</p>
              </div>

              <div className="btn-group-row">
                <button type="button" className="primary" onClick={() => setEditing(true)}>
                  Editar perfil
                </button>
                {user.career && (
                  <button type="button" className="danger-sm" onClick={handleDeleteProfile}>
                    Restablecer datos
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
                Teléfono
                <input value={phone} onChange={(e) => setPhone(e.target.value)} />
              </label>

              <label>
                Intereses (separados por coma)
                <input value={interests} onChange={(e) => setInterests(e.target.value)} />
              </label>

              <div className="btn-group-row">
                <button type="submit" className="primary">
                  Guardar cambios
                </button>
                <button type="button" className="secondary" onClick={() => setEditing(false)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>

        <aside className="badge-sidebar">
          <h3>Estado de la cuenta</h3>
          <div className="status-box">
            {user.es_institucional ? (
              <div className="badge-ipn-verified">
                Comunidad IPN Verificada
              </div>
            ) : (
              <div className="badge-standard">
                Cuenta estándar
              </div>
            )}
            <p className="sidebar-hint">
              {user.has_complete_profile
                ? 'Tu perfil está completo para calcular la compatibilidad de laptops con tus materias.'
                : 'Completa tu carrera y semestre para activar las sugerencias personalizadas.'}
            </p>
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

  // Catálogo
  const [publications, setPublications] = useState([])
  const [loadingPubs, setLoadingPubs] = useState(false)
  const [selectedPub, setSelectedPub] = useState(null)

  // Filtros
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [filterOptions, setFilterOptions] = useState({ brands: [] })

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

  const fetchPublications = (current = filters) => {
    setLoadingPubs(true)
    apiRequest(buildPublicationsUrl(current))
      .then((data) => setPublications(data))
      .catch((err) => alert(err.message))
      .finally(() => setLoadingPubs(false))
  }

  useEffect(() => {
    if (!user) return
    let ignore = false
    apiRequest(buildPublicationsUrl(filters))
      .then((data) => {
        if (!ignore) setPublications(data)
      })
      .catch(() => {})
    return () => {
      ignore = true
    }
  }, [user, filters])

  useEffect(() => {
    if (!user) return
    apiRequest('/api/filters/options')
      .then((data) => setFilterOptions(data))
      .catch(() => {})
  }, [user, publications.length])

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }))

  const activeFilterCount = Object.keys(EMPTY_FILTERS).filter(
    (key) => key !== 'search' && key !== 'sort_by' && key !== 'device_type' && filters[key] !== EMPTY_FILTERS[key]
  ).length

  const resetFilters = () => setFilters(EMPTY_FILTERS)

  const toggleCompatibility = () => {
    if (!filters.only_compatible && user && !user.has_complete_profile) {
      alert('Completa tu carrera y semestre en "Mi perfil" antes de activar este filtro.')
      return
    }
    setFilter('only_compatible', !filters.only_compatible)
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
      alert(res.message)
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
        <p className="muted-text">Cargando sesión…</p>
      </main>
    )
  }

  if (!user) {
    return (
      <AuthScreen
        onAuthenticated={(u) => {
          setUser(u)
          fetchPublications(EMPTY_FILTERS)
        }}
      />
    )
  }

  return (
    <div className="site-wrapper">
      {/* BARRA SUPERIOR */}
      <header className="navbar">
        <div className="navbar-brand" onClick={() => setActiveView('inicio')}>
          <span className="brand-badge-ipn">ESCOM</span>
          <span className="brand-logo-text">Hardware Match</span>
        </div>

        <nav className="nav-links">
          <button
            type="button"
            className={activeView === 'inicio' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('inicio')}
          >
            Explorar
          </button>
          <button
            type="button"
            className={activeView === 'publicar' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('publicar')}
          >
            Vender equipo
          </button>
          <button
            type="button"
            className={activeView === 'mis-publicaciones' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('mis-publicaciones')}
          >
            Mis publicaciones
          </button>
          <button
            type="button"
            className={activeView === 'favoritos' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('favoritos')}
          >
            Favoritos
          </button>
          <button
            type="button"
            className={activeView === 'perfil' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('perfil')}
          >
            Mi perfil
          </button>
        </nav>

        <div className="navbar-user">
          <span className="user-label">
            {user.name.split(' ')[0]}
            {user.es_institucional && <span className="verified-dot">✓</span>}
          </span>
          <button type="button" className="logout-btn" onClick={logout}>
            Salir
          </button>
        </div>
      </header>

      {sessionError && <p className="form-error">{sessionError}</p>}

      <main className="main-content">
        {/* VISTA 1: EXPLORAR / MARKETPLACE */}
        {activeView === 'inicio' && (
          <>
            <section className="hero-banner">
              <div className="hero-left">
                <h1>Laptops y tabletas verificadas para la comunidad ESCOM</h1>
                <p className="hero-sub">
                  Compara especificaciones técnicas contrastadas contra las exigencias reales de
                  software de tu plan de estudios.
                </p>

                <div className="hero-actions">
                  <button type="button" className="primary" onClick={() => setActiveView('publicar')}>
                    + Publicar equipo
                  </button>
                  <button
                    type="button"
                    className={`secondary ${filters.only_compatible ? 'active-filter' : ''}`}
                    onClick={toggleCompatibility}
                  >
                    {filters.only_compatible
                      ? 'Mostrando: Solo compatibles'
                      : 'Filtrar por compatibilidad de carrera'}
                  </button>
                </div>
              </div>

              <div className="hero-widget">
                <span className="widget-title">Tu perfil</span>
                <p className="widget-career">{user.career || 'Comunidad General'}</p>
                <span className="widget-meta">{user.semester || 'Sin semestre asignado'}</span>
              </div>
            </section>

            {/* BARRA DE FILTROS */}
            <section className="filter-bar panel">
              <div className="filter-row">
                <div className="filter-group grow">
                  <input
                    type="search"
                    placeholder="Buscar por marca, modelo o procesador…"
                    value={filters.search}
                    onChange={(e) => setFilter('search', e.target.value)}
                  />
                </div>

                <div className="filter-group">
                  <select value={filters.device_type} onChange={(e) => setFilter('device_type', e.target.value)}>
                    <option value="">Todos los tipos</option>
                    <option value="Laptop">Laptops</option>
                    <option value="Tableta">Tabletas</option>
                  </select>
                </div>

                <div className="filter-group">
                  <select value={filters.sort_by} onChange={(e) => setFilter('sort_by', e.target.value)}>
                    <option value="recientes">Más recientes</option>
                    <option value="precio_asc">Precio: menor a mayor</option>
                    <option value="precio_desc">Precio: mayor a menor</option>
                    <option value="compatibilidad">Mayor compatibilidad</option>
                  </select>
                </div>

                <button
                  type="button"
                  className={`secondary-sm ${showAdvanced ? 'active-filter' : ''}`}
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  Más filtros{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
                </button>

                {activeFilterCount > 0 && (
                  <button type="button" className="link-clear-btn" onClick={resetFilters}>
                    Limpiar
                  </button>
                )}
              </div>

              {showAdvanced && (
                <div className="advanced-filters">
                  <label>
                    Marca
                    <select value={filters.brand} onChange={(e) => setFilter('brand', e.target.value)}>
                      <option value="">Todas</option>
                      {filterOptions.brands.map((b) => (
                        <option key={b} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Condición
                    <select value={filters.condition} onChange={(e) => setFilter('condition', e.target.value)}>
                      <option value="">Cualquiera</option>
                      <option value="Nuevo">Nuevo</option>
                      <option value="Usado - Como nuevo">Como nuevo</option>
                      <option value="Usado - Buen estado">Buen estado</option>
                      <option value="Usado - Con detalles">Con detalles</option>
                    </select>
                  </label>

                  <label>
                    RAM mínima
                    <select value={filters.min_ram} onChange={(e) => setFilter('min_ram', e.target.value)}>
                      <option value="">Cualquiera</option>
                      {[4, 8, 12, 16, 24, 32].map((r) => (
                        <option key={r} value={r}>
                          {r} GB o más
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Almacenamiento mínimo
                    <select value={filters.min_storage} onChange={(e) => setFilter('min_storage', e.target.value)}>
                      <option value="">Cualquiera</option>
                      <option value="128">128 GB o más</option>
                      <option value="256">256 GB o más</option>
                      <option value="512">512 GB o más</option>
                      <option value="1024">1 TB o más</option>
                    </select>
                  </label>

                  <label>
                    Tipo de disco
                    <select value={filters.storage_type} onChange={(e) => setFilter('storage_type', e.target.value)}>
                      <option value="">Cualquiera</option>
                      <option value="SSD NVMe">SSD NVMe</option>
                      <option value="SSD SATA">SSD SATA</option>
                      <option value="HDD">HDD</option>
                      <option value="eMMC">eMMC</option>
                    </select>
                  </label>

                  <label>
                    Tarjeta gráfica
                    <select value={filters.gpu_type} onChange={(e) => setFilter('gpu_type', e.target.value)}>
                      <option value="">Cualquiera</option>
                      <option value="dedicada">Dedicada</option>
                      <option value="integrada">Integrada</option>
                    </select>
                  </label>

                  <label>
                    Precio mínimo (MXN)
                    <input
                      type="number"
                      min="0"
                      step="500"
                      placeholder="0"
                      value={filters.min_price}
                      onChange={(e) => setFilter('min_price', e.target.value)}
                    />
                  </label>

                  <label>
                    Precio máximo (MXN)
                    <input
                      type="number"
                      min="0"
                      step="500"
                      placeholder="Sin límite"
                      value={filters.max_price}
                      onChange={(e) => setFilter('max_price', e.target.value)}
                    />
                  </label>

                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={filters.ipn_sellers_only}
                      onChange={(e) => setFilter('ipn_sellers_only', e.target.checked)}
                    />
                    Solo vendedores con correo IPN
                  </label>
                </div>
              )}
            </section>

            {/* CATÁLOGO DE PUBLICACIONES */}
            <section className="catalog-section">
              <div className="catalog-header">
                <h3>
                  {publications.length} {publications.length === 1 ? 'oferta' : 'ofertas'} disponibles
                  {filters.only_compatible && ' · Compatibilidad con tu carrera'}
                </h3>
                {loadingPubs && <span className="updating-tag">Actualizando…</span>}
              </div>

              {publications.length === 0 ? (
                <div className="empty-box">
                  <p>No se encontraron publicaciones con los filtros aplicados.</p>
                  <button className="secondary" onClick={resetFilters}>
                    Ver todas las ofertas
                  </button>
                </div>
              ) : (
                <div className="catalog-grid">
                  {publications.map((pub) => (
                    <article key={pub.id} className="card-item" onClick={() => setSelectedPub(pub)}>
                      <div className="card-media">
                        <img
                          src={
                            pub.image_url ||
                            'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=600&q=80'
                          }
                          alt={pub.title}
                          className="card-img"
                          loading="lazy"
                        />
                        <span className="card-tag-device">{pub.device_type}</span>
                        {pub.compatibility_score && (
                          <span
                            className={`card-tag-score ${
                              pub.compatibility_score >= 90 ? 'high' : ''
                            }`}
                          >
                            {pub.compatibility_score}% match
                          </span>
                        )}
                      </div>

                      <div className="card-body">
                        <span className="card-brand">{pub.brand} · {pub.model}</span>
                        <h4 className="card-title">{pub.title}</h4>

                        {pub.compatibility_badge && (
                          <p className="card-compat-hint">{pub.compatibility_badge}</p>
                        )}

                        <div className="specs-chips">
                          <span>{pub.processor}</span>
                          <span>{pub.ram_gb} GB</span>
                          <span>{pub.storage_gb} GB {pub.storage_type}</span>
                        </div>

                        <div className="card-bottom">
                          <strong className="card-price">${pub.price.toLocaleString()} MXN</strong>
                          <button
                            type="button"
                            className="secondary-sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedPub(pub)
                            }}
                          >
                            Ver detalle
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

        {/* VISTA 2: PUBLICAR OFERTA */}
        {activeView === 'publicar' && (
          <CreatePublicationView
            onPublished={(newPub) => {
              fetchPublications()
              setSelectedPub(newPub)
              setActiveView('inicio')
            }}
            onCancel={() => setActiveView('inicio')}
          />
        )}

        {/* VISTA 3: MIS PUBLICACIONES */}
        {activeView === 'mis-publicaciones' && (
          <MyPublicationsView
            onSelectPub={(pub) => setSelectedPub(pub)}
            onCreateNew={() => setActiveView('publicar')}
            onDeletePub={handleDeletePub}
          />
        )}

        {/* VISTA 4: FAVORITOS */}
        {activeView === 'favoritos' && (
          <FavoritesView
            onSelectPub={(pub) => setSelectedPub(pub)}
            onRemoveFav={handleToggleFavorite}
          />
        )}

        {/* VISTA 5: MI PERFIL */}
        {activeView === 'perfil' && (
          <ProfileView user={user} onProfileUpdated={(updated) => setUser(updated)} />
        )}
      </main>

      {/* MODAL DETALLE */}
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
