# Visual Paradigm · TT 2027-A196

**Proyectos de modelado UML del prototipo ESCOM Hardware Match**

Trabajo Terminal No. 2027-A196 · Escuela Superior de Cómputo (ESCOM) · Instituto Politécnico Nacional

| | |
|---|---|
| **Alumnos** | Granados Martínez Pablo Daniel · López Hernández Alan |
| **Directora** | M. en C. Galiñanes Rodríguez María Gabriela |

## Descripción

Esta carpeta contiene los archivos fuente de Visual Paradigm (`.vpp`) con los diagramas del análisis y diseño del sistema, junto con sus exportaciones en imagen (`.png`) para consultarlos sin abrir la herramienta. Los diagramas corresponden a los que aparecen en el Reporte Técnico de TT I.

## Contenido

| Diagrama | Archivo fuente | Exportación | Qué modela |
|---|---|---|---|
| **Arquitectura** | [`Diagrama de arquitectura TT.vpp`](<Diagrama de arquitectura TT.vpp>) | [`Diagrama de arquitectura TT.png`](<Diagrama de arquitectura TT.png>) | Componentes del sistema y su comunicación: SPA en HTML5, CSS3 y JavaScript; Nginx como servidor de estáticos y proxy inverso; API en Node.js con Express; PostgreSQL 16; todo desplegado con Docker Compose. |
| **Casos de uso** | [`Diagrama de Casos de Uso TT.vpp`](<Diagrama de Casos de Uso TT.vpp>) | [`Diagrama de Casos de Uso TT.png`](<Diagrama de Casos de Uso TT.png>) | 46 casos de uso (CU01 a CU46) con los actores **Visitante** e **Interesado/Ofertante**, y sus relaciones `«include»` y `«extend»`. |
| **Entidad-relación** | [`Diagrama Entidad Relacion TT.vpp`](<Diagrama Entidad Relacion TT.vpp>) | [`Diagrama Entidad Relacion TT.png`](<Diagrama Entidad Relacion TT.png>) | Modelo relacional en 3FN de 13 tablas de PostgreSQL 16, con claves primarias, foráneas y cardinalidades. |
| **Mapa de navegación** | [`Mapa de Navegacion TT.vpp`](<Mapa de Navegacion TT.vpp>) | [`Mapa de Navegacion TT.png`](<Mapa de Navegacion TT.png>) | Pantallas de la interfaz y las transiciones entre ellas, para el Visitante y para el Interesado/Ofertante. |

## Vista previa

### Diagrama de arquitectura

![Diagrama de arquitectura](<Diagrama de arquitectura TT.png>)

### Diagrama de casos de uso

![Diagrama de casos de uso](<Diagrama de Casos de Uso TT.png>)

### Diagrama entidad-relación

![Diagrama entidad-relación](<Diagrama Entidad Relacion TT.png>)

### Mapa de navegación

![Mapa de navegación](<Mapa de Navegacion TT.png>)

## Cómo abrir los diagramas

1. Instalar Visual Paradigm (la edición Community es suficiente para consultar los diagramas).
2. Abrir el archivo con **Project → Open** y seleccionar el `.vpp`.
3. Para solo ver el diagrama, consultar la sección **Vista previa** o abrir el `.png` en GitHub.


## Relación con la documentación

- Fichas de especificación de casos de uso: [`DOCUMENTACION_CASOS_DE_USO.md`](../../DOCUMENTACION_CASOS_DE_USO.md)
- Documentación técnica: [`docs/DOCUMENTACION_TECNICA.md`](../DOCUMENTACION_TECNICA.md)
- Base de datos: [`docs/base_de_datos/`](../base_de_datos/)
