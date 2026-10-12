import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { marked } from 'marked'
import puppeteer from 'puppeteer-core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '../..')

// Chrome executable candidates
const CHROME_PATHS = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean)

function findChrome() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) return p
  }
  throw new Error('No se encontró Google Chrome ni Microsoft Edge en las rutas estándar.')
}

const docs = [
  {
    input: path.join(rootDir, 'DOCUMENTACION_CASOS_DE_USO.md'),
    output: path.join(rootDir, 'docs', 'pdf', 'DOCUMENTACION_CASOS_DE_USO.pdf'),
    title: 'Casos de Uso · TT 2027-A196 (ESCOM - IPN)',
  },
  {
    input: path.join(rootDir, 'docs', 'DOCUMENTACION_TECNICA.md'),
    output: path.join(rootDir, 'docs', 'pdf', 'DOCUMENTACION_TECNICA.pdf'),
    title: 'Documentación Técnica · TT 2027-A196 (ESCOM - IPN)',
  },
  {
    input: path.join(rootDir, 'docs', 'base_de_datos', 'DOCUMENTACION_BASE_DE_DATOS.md'),
    output: path.join(rootDir, 'docs', 'pdf', 'DOCUMENTACION_BASE_DE_DATOS.pdf'),
    title: 'Base de Datos · TT 2027-A196 (ESCOM - IPN)',
  },
]

function renderHtml(markdownText, title) {
  // Replace ```mermaid ... ``` code blocks with <div class="mermaid">...</div>
  const renderer = new marked.Renderer()
  const originalCode = renderer.code.bind(renderer)

  renderer.code = function ({ text, lang }) {
    if (lang === 'mermaid') {
      return `<div class="mermaid-wrapper"><pre class="mermaid">${text}</pre></div>`
    }
    return originalCode({ text, lang })
  }

  const htmlContent = marked.parse(markdownText, { renderer, gfm: true, breaks: false })

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
  <style>
    @page {
      size: A4;
      margin: 20mm 15mm 20mm 15mm;
      @bottom-right {
        content: counter(page);
      }
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1e293b;
      background: #ffffff;
      line-height: 1.6;
      font-size: 11pt;
      margin: 0;
      padding: 0;
    }
    h1, h2, h3, h4, h5 {
      color: #0f172a;
      font-weight: 700;
      page-break-after: avoid;
      break-after: avoid;
    }
    h1 {
      font-size: 20pt;
      border-bottom: 2px solid #881337;
      padding-bottom: 6px;
      margin-top: 0;
      color: #881337;
    }
    h2 {
      font-size: 15pt;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
      margin-top: 24pt;
      color: #1e293b;
    }
    h3 {
      font-size: 12.5pt;
      margin-top: 18pt;
      color: #334155;
    }
    h4 {
      font-size: 11pt;
      margin-top: 14pt;
    }
    p, li {
      color: #334155;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 14pt 0;
      font-size: 9.5pt;
      page-break-inside: avoid;
      break-inside: avoid;
    }
    th, td {
      border: 1px solid #cbd5e1;
      padding: 6pt 8pt;
      text-align: left;
      vertical-align: top;
    }
    th {
      background-color: #f1f5f9;
      font-weight: 600;
      color: #0f172a;
    }
    tr:nth-child(even) td {
      background-color: #f8fafc;
    }
    pre, code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 9pt;
    }
    code:not(pre code) {
      background-color: #f1f5f9;
      color: #881337;
      padding: 2pt 4pt;
      border-radius: 3pt;
      border: 1px solid #e2e8f0;
    }
    pre {
      background-color: #0f172a;
      color: #f8fafc;
      padding: 10pt;
      border-radius: 4pt;
      overflow-x: auto;
      page-break-inside: avoid;
      break-inside: avoid;
    }
    pre code {
      color: #f8fafc;
      background: transparent;
      padding: 0;
      border: none;
    }
    blockquote {
      border-left: 4px solid #881337;
      margin: 12pt 0;
      padding: 6pt 12pt;
      background-color: #fdf2f4;
      color: #475569;
      font-size: 10pt;
      page-break-inside: avoid;
    }
    .mermaid-wrapper {
      margin: 18pt 0;
      text-align: center;
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .mermaid {
      background: #ffffff;
      padding: 10pt;
      border: 1px solid #e2e8f0;
      border-radius: 6pt;
      display: inline-block;
      max-width: 100%;
    }
    .mermaid svg {
      max-width: 100% !important;
      height: auto !important;
    }
    hr {
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 20pt 0;
    }
    .badge {
      display: inline-block;
      padding: 2pt 6pt;
      font-size: 8pt;
      font-weight: 700;
      color: #fff;
      background: #881337;
      border-radius: 3pt;
    }
  </style>
</head>
<body>
  ${htmlContent}
  <script>
    mermaid.initialize({
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: { htmlLabels: true, curve: 'basis' },
      themeVariables: {
        primaryColor: '#f1f5f9',
        primaryTextColor: '#0f172a',
        primaryBorderColor: '#881337',
        lineColor: '#475569',
        secondaryColor: '#fdf2f4',
        tertiaryColor: '#f8fafc'
      }
    });
  </script>
</body>
</html>`
}

async function main() {
  const chromePath = findChrome()
  console.log(`Usando navegador: ${chromePath}`)

  const outDir = path.join(rootDir, 'docs', 'pdf')
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true })
  }

  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security'],
  })

  try {
    for (const doc of docs) {
      if (!fs.existsSync(doc.input)) {
        console.warn(`Archivo no encontrado: ${doc.input}`)
        continue
      }
      console.log(`Generando PDF: ${path.basename(doc.output)}...`)
      const markdown = fs.readFileSync(doc.input, 'utf-8')
      const html = renderHtml(markdown, doc.title)

      const page = await browser.newPage()
      await page.setContent(html, { waitUntil: ['load', 'networkidle0'] })

      // Wait for mermaid diagrams to finish rendering
      try {
        await page.waitForFunction(
          () => {
            const wrappers = document.querySelectorAll('.mermaid-wrapper')
            if (wrappers.length === 0) return true
            return Array.from(wrappers).every((w) => w.querySelector('svg') !== null)
          },
          { timeout: 15000 }
        )
      } catch {
        console.warn('Timeout esperando renderizado completo de Mermaid, continuando...')
      }

      // Small pause to let fonts and SVGs settle
      await new Promise((r) => setTimeout(r, 800))

      await page.pdf({
        path: doc.output,
        format: 'A4',
        printBackground: true,
        margin: {
          top: '20mm',
          right: '15mm',
          bottom: '20mm',
          left: '15mm',
        },
      })
      await page.close()
      console.log(`✓ Guardado: ${doc.output} (${(fs.statSync(doc.output).size / 1024).toFixed(1)} KB)`)
    }
  } finally {
    await browser.close()
  }
  console.log('Todos los documentos PDF fueron generados exitosamente.')
}

main().catch((err) => {
  console.error('Error generando PDFs:', err)
  process.exit(1)
})
