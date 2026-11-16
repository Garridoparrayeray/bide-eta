# Plan de publicación en Zenodo (artículo 2)

El orden importa: cada paso da un DOI que el siguiente cita.

## 1. Artículo 1 (método) en Zenodo

El artículo 2 se apoya en él (Garrido 2026b): la especificación del método y la regla de ±2 min fijada de antemano.
Ahora solo tiene la URL del repositorio, y los revisores piden un DOI.

- Tipo: *Publication → Preprint*.
- Licencia: CC BY 4.0.
- Relación: «is supplemented by» el repositorio de GitHub; «references» la memoria (10.5281/zenodo.24041572).
- Con el DOI, cambiar en `referencias.bib` la entrada `garrido2026metodo` (añadir `doi = {…}`).

## 2. Artículo 2: preprint, código y datos derivados (un registro)

- **Reservar el DOI antes de subir nada** (botón *Reserve DOI* de Zenodo).
  - Escribirlo en `articulo.tex` y en `articulo-lectura.tex`: `\newcommand{\doidatos}{doi:10.5281/zenodo.…}`.
  - Volver a compilar los dos PDF.
- Ficheros:
  - `articulo.pdf` (versión de revista);
  - `articulo-lectura.pdf` (versión para leer);
  - un `.zip` de la carpeta `articulo-comparacion` (código, tablas, datos de las figuras, `captura/`);
  - `datos/horario/bizkaibus.sqlite.xz`;
  - las tablas aprendidas del 7 de noviembre (`datos/tablas`).
- Tipo: *Publication → Preprint*.
- Versión: v1. Licencias: CC BY 4.0 para el texto y los datos derivados, MIT para el código; las dos se indican en la
  descripción.
- Palabras clave: las 7 del artículo.
- Relaciones:
  - «references» el artículo 1 y la memoria;
  - «is supplemented by» el registro 3 y el repositorio de GitHub.
- Descripción: el resumen del artículo y «Not peer reviewed».

## 3. Respuestas oficiales y capturas en bruto (registro aparte)

Las respuestas del servicio oficial no son nuestras: no pueden ir bajo CC BY. Hay que elegir una de dos opciones:

- **(a) Acceso restringido.** Se da acceso a quien lo pida para investigación. Licencia «Other (see description)», con
  el texto de *Data collection and terms of use*.
- **(b) No subirlas a Zenodo.** Se dejan en la release `comparacion-2026-11` de GitHub y el registro 2 las enlaza.

Con el DOI (o el enlace) de este registro se rellena `\doibrutos`.

## 4. Antes de subir

- Hecho: la declaración de conflicto de intereses dice que la app es gratuita y acepta donaciones para pagar el
  servidor, sin más ingresos.
- El preprint lleva tu correo (campo `\ead` de elsarticle) en la primera página. Quitarlo si no quieres que sea público.
- Después de subirlo:
  - añadir la línea «Cite as: Garrido, Y. (2026)… Zenodo. doi:…» en la portada de la versión para leer;
  - cuando una revista lo acepte, actualizar el registro con el DOI de la revista. Elsevier permite el preprint.

## 5. Revista

Los revisores ven más encaje en *Journal of Public Transportation* o *Public Transport* que en *Transportation
Research Part C*, que busca aportaciones metodológicas. *Transportation Research Record* limita a 7.500 palabras: el
artículo tendría que recortar unas 700, con estos cambios:

- pasar San Juan al apéndice;
- acortar la sección 4.3 (días);
- juntar el día de huelga con la sección de días;
- pasar la tabla 5 al apéndice.

Los highlights (`highlights.tex`) se envían como fichero aparte; ya no van en el preprint.
