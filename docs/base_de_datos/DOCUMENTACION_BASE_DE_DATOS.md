# Documentación de Análisis y Diseño de la Base de Datos

**Proyecto:** Trabajo Terminal No. 2027-A196 – ESCOM, IPN  
**Motor:** PostgreSQL (contenedor `escom_db`)  
**Base de datos:** `hardware_match_db`  
**ORM:** SQLAlchemy 2.x (modelos y despliegue DDL en [`backend/main.py`](../../backend/main.py))  
**Esquema Físico (13 Entidades en 3FN):** [`schema.sql`](schema.sql)  

---

## 1. Justificación del Paradigma Relacional y del Diagrama Relacional

El dominio del sistema exige integridad referencial estricta entre entidades fuertemente acopladas (usuarios, sesiones, códigos de verificación/recuperación, perfiles académicos, reglas curriculares, publicaciones, especificaciones técnicas, favoritos, comentarios, votos, valoraciones e invitaciones de comprador verificado), así como transacciones ACID:
* **Por qué se eligió una base de datos relacional frente a alternativas NoSQL/documentales:** En un modelo documental (ej. MongoDB), incrustar los datos del vendedor o las calificaciones dentro del documento de cada publicación ocasionaría anomalías de actualización cada vez que el ofertante confirma su correo institucional (`RN-02`), actualiza su teléfono o recibe una reseña, obligando a reescribir múltiples documentos o a emular uniones costosas en la capa de aplicación sin soporte nativo de claves foráneas. De igual modo, almacenar las especificaciones de hardware como un bloque JSON libre impediría imponer restricciones declarativas `NOT NULL` y `CHECK` (`RN-04`) sobre los 14 atributos obligatorios y degradaría el desempeño de los 13 filtros técnicos (`CU20`).
* **Por qué se eligió un Diagrama Relacional (notación Crow's Foot / Pata de Gallo):** A diferencia de un diagrama conceptual de Chen aislado, el Diagrama Relacional permite representar en un solo artefacto las 13 tablas, sus llaves primarias (`PK`), llaves foráneas (`FK`), tipos de datos nativos de PostgreSQL y cardinalidades exactas (`1:1` y `1:N`), facilitando la trazabilidad directa hacia el diccionario de datos y el script [`schema.sql`](schema.sql).

---

## 2. Evolución del Diseño: Conceptual, Lógico y Físico

1. **Diseño Conceptual:** Se partió de las 13 reglas de negocio (`RN-01` a `RN-13`) y de los 46 casos de uso (`CU01` a `CU46`), identificando cinco subdominios:
   * *Identidad y Seguridad:* `Usuario`, `Token de Verificación`, `Sesión`.
   * *Perfil y Reglas Curriculares:* `Perfil Académico`, `Requerimiento de Unidad de Aprendizaje`.
   * *Catálogo Comercial y Técnico:* `Publicación`, `Especificación Técnica`.
   * *Seguimiento:* `Favorito`.
   * *Confianza Comunitaria:* `Comentario en Publicación`, `Comentario en Perfil`, `Voto de Comentario`, `Valoración de Perfil` e `Invitación de Valoración`.
   Las relaciones muchos-a-muchos (`N:M`) entre usuarios y publicaciones (guardar favoritos, votar comentarios, calificar perfiles o invitar compradores) se resolvieron mediante entidades asociativas con restricciones de unicidad compuesta.
2. **Diseño Lógico:** Se transformaron las entidades en esquemas de relación $R(A_1, A_2, \dots, A_n)$, definiendo llaves primarias (`PK`), llaves foráneas (`FK`) y reglas de integridad referencial (`ON DELETE CASCADE` para dependientes directos y `ON DELETE SET NULL` en `favorito` para conservar la tarjeta gris `«[Esta publicación ya no está disponible]»` conforme a `RN-12`). Se separó en relación `1:1` a `usuario` respecto de `perfil_academico`, y a `publicacion` respecto de `especificacion_tecnica`, desacoplando los atributos de autenticación/estado comercial respecto de los vectores técnicos consultados por el motor CBF.
3. **Diseño Físico:** Se implementó en PostgreSQL con tipos exactos (`SERIAL`/`INTEGER`, `NUMERIC(10,2)` para precios sin error de punto flotante, `TIMESTAMPTZ` en UTC para caducidades de 24 horas en `RN-01` y 30 días en `RN-08`, y `VARCHAR(64)` para resúmenes `SHA-256`), restricciones `CHECK` de dominio y 11 índices especializados (`B-Tree` para búsquedas por rango/igualdad y `GIN` sobre arreglos `TEXT[]` de unidades de aprendizaje e intereses).

---

## 3. Normalización del Esquema (Tercera Forma Normal – 3FN)

* **Primera Forma Normal (1FN):** Todos los atributos contienen valores atómicos y se eliminaron grupos repetitivos. Las características del equipo no se guardan como texto libre concatenado (causa del problema `P4`), sino desglosadas en columnas atómicas (`categoria`, `marca`, `modelo`, `procesador_marca`, `generacion_cpu`, `nucleos_cpu`, `ram_gb`, `tipo_ram`, `almacenamiento_gb`, `tipo_almacenamiento`, `tiene_gpu_dedicada`, `pantalla`, `bateria`, `condicion_fisica`).
* **Segunda Forma Normal (2FN):** Cumple 1FN y ningún atributo no primo presenta dependencia funcional parcial respecto de una llave candidata compuesta. En las tablas asociativas (`favorito`, `voto_comentario`, `valoracion_perfil`, `invitacion_valoracion`), cada atributo propio (`fecha_agregado`, `valor`, `estrellas`, `estado_invitacion`) depende de la combinación completa de sus claves foráneas, mientras que los datos descriptivos del usuario o del equipo residen únicamente en `usuario` y `publicacion`.
* **Tercera Forma Normal (3FN):** Cumple 2FN y carece de dependencias transitivas ($PK \to X \to Y$):
  1. En `publicacion` solo se registra `id_ofertante` (`FK`); el nombre, correo e insignia institucional del vendedor no se duplican en cada oferta, sino que se obtienen de `usuario`.
  2. Los requisitos de hardware por asignatura (`ram_recomendada_gb`, `ssd_recomendado_gb`, `nucleos_min`, `requiere_gpu` y pesos $w_k$) residen en el catálogo independiente `requerimiento_unidad` y no se repiten dentro del perfil de cada alumno.
  3. Las calificaciones promedio de perfiles y publicaciones se calculan mediante funciones de agregación sobre `valoracion_perfil` e `invitacion_valoracion`.
