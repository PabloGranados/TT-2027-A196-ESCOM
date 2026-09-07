# TT 2027-A196: Prototipo de aplicación web para la recomendación de publicaciones de ofertas de laptops y tabletas entre la comunidad de la ESCOM

## Equipo de Desarrollo
* **Alumnos:**
  * Granados Martínez Pablo Daniel
  * López Hernández Alan
* **Directora:** M. en C. Galiñanes Rodríguez María Gabriela

## Descripción del Proyecto
Este proyecto es un Trabajo Terminal desarrollado para la Escuela Superior de Cómputo (ESCOM) del IPN. Su objetivo principal es implementar una aplicación web que centralice la publicación de ofertas de laptops y tabletas, nuevas o de segunda mano, enfocada a la comunidad de la ESCOM. 

La innovación principal radica en la integración de un **módulo de filtrado por compatibilidad de perfil**. Mediante un algoritmo de filtrado basado en contenido (CBF), el sistema evalúa y etiqueta automáticamente las publicaciones contrastando las especificaciones de los equipos ofertados contra los requerimientos académicos del plan de estudios 2020 y los intereses declarados por el usuario.

## Arquitectura y Tecnologías (Stack)
El sistema está diseñado bajo una **Arquitectura de Tres Niveles**, garantizando independencia entre componentes e impulsando la escalabilidad futura:
* **Capa de Presentación (Frontend):** Interfaz de Usuario Responsiva desarrollada con React.js (Vite) + HTML/CSS/JavaScript.
* **Capa de Lógica de Negocio (Backend):** Procesamiento de reglas de negocio y motor de recomendaciones académicas desarrollado con Python (FastAPI).
* **Capa de Datos:** Almacenamiento persistente y gestión de integridad mediante base de datos relacional (PostgreSQL).
* **Despliegue y Entorno:** Orquestado en contenedores mediante Docker y Docker Compose.

## Configuración y Despliegue Local
El Sprint 1 contempla la configuración del entorno base de desarrollo. Para levantar el entorno en tu máquina local, sigue estos pasos:

### Prerrequisitos
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y en ejecución.
* Git.

### Pasos para ejecutar
1. Clona este repositorio:
   ```bash
   git clone [https://github.com/PabloGranados/TT-2027-A196-ESCOM](https://github.com/PabloGranados/TT-2027-A196-ESCOM)
   cd TT-2027-A196-ESCOM