# bide-eta

**Predicción de llegadas de autobús con feeds que solo dan la posición y horarios interpolados.**
Implementación de referencia, vectores de prueba, evaluador público y datos del método de la aplicación
[Bizkaibus+](https://www.bideplus.eus) (Bide+). *English version: [README.md](README.md).*

Bizkaibus, la red de autobuses interurbanos de Bizkaia, publica la posición GPS de cada vehículo y su próxima parada,
pero no su retraso, y las horas intermedias de su horario oficial están interpoladas a velocidad constante. El método
trabaja con diferencias de horario en lugar de horas absolutas, aprende el tiempo real de cada tramo entre paradas por
franja horaria con medianas contraídas hacia la mediana de todo el día, y predice en tres capas con reglas para
abstenerse: la posición proyectada sobre el recorrido, la última parada registrada por el feed y el horario corregido
viaje a viaje.

## Publicaciones

El trabajo se publica en tres partes, cada una en su carpeta:

| | Carpeta | Qué es | Estado |
|---|---|---|---|
| 1 | [`memoria/`](memoria/) | **Memoria técnica** (en castellano, APA 7): el método completo, las mediciones que hay detrás de cada constante, la evaluación entera y la implementación de referencia. Fuentes LaTeX y PDF. | Se publica primero |
| 2 | [`articulo-metodo/`](articulo-metodo/) | **Artículo 1** (en inglés): el método reproducible, su evaluación en 23 días y la comparación con otros métodos. | Borrador |
| 3 | [`articulo-comparacion/`](articulo-comparacion/) | **Artículo 2** (en inglés): el método frente a los tiempos de espera que muestra el propio Bizkaibus, en los mismos autobuses y paradas. La captura de una semana está en [`captura/`](articulo-comparacion/captura/). | Capturando datos |

Comunes a las tres:

| Carpeta | Contenido |
|---|---|
| [`referencia/`](referencia/) | `referencia.py`, el método escrito solo a partir de la memoria; `vectores.json`, 407 comprobaciones sacadas del motor de producción; `comprobar.py`, que compara uno con otro; `evaluar.py`, el evaluador público |
| [`datos/`](datos/) | Las tablas aprendidas (tiempos por tramo, factores de ritmo y correcciones por viaje), los datos de evaluación de las tablas de los artículos y la ficha de los datos |

## Para empezar

Python 3.9 o posterior, solo la biblioteca estándar.

```bash
python3 referencia/comprobar.py
```

Escribe `407 de 407 comprobaciones coinciden con el código de producción` si la implementación de referencia da
exactamente lo mismo que el motor de producción.

Para evaluar con capturas del feed en directo (ficheros SIRI Vehicle Monitoring `vm_*.xml`) y la base del horario
construida a partir del GTFS:

```bash
python3 referencia/evaluar.py --capturas <carpeta con vm_*.xml> --base <bizkaibus.sqlite> --tablas datos/tablas
```

Escribe el porcentaje de llegadas dentro de ±1, ±2 y ±3 minutos por horizonte, del método y del horario publicado, y
puede guardar histogramas del error de 15 s (`--jsonl`). Con 40 minutos del feed del 7 de noviembre de 2026 (92.686
predicciones) sus histogramas son idénticos, barra a barra, a los del evaluador de producción, en los tres modos
(`normal`, `sin-gps`, `sin-feed`).

## Resultados hasta ahora

En 2,37 millones de predicciones de 17 días (del 15 al 31 de octubre de 2026) contrastadas con el paso real, la
llegada mostrada cae dentro de ±2 minutos en el 96 % de los casos a menos de tres minutos y en el 67 % entre diez y
veinte minutos, frente al 24 % y el 25 % del horario publicado.

## Para TFG, TFM e investigación

Todo se puede usar y modificar citando la fuente. El método se cita por la memoria técnica, que tiene su propio DOI:

> Garrido, Y. (2026). *Predicción de llegadas de autobuses con posiciones en tiempo real y horarios interpolados*
> (Versión 2.1) [Informe técnico]. Zenodo. https://doi.org/10.5281/zenodo.24041572

Cómo citar el código y los datos, y la licencia, en el [README en inglés](README.md#how-to-cite).
Autor: Yeray Garrido, [ORCID 0009-0008-0459-0294](https://orcid.org/0009-0008-0459-0294).

## Licencia

- Código: [MIT](LICENSE).
- Textos y datos producidos aquí (documentación, tablas aprendidas, resultados de la evaluación): [CC BY 4.0](LICENSE-CC-BY-4.0.txt).
- Horario y feed en directo: datos abiertos de quien los publica, reutilizados citando la fuente (en
  [`datos/README.md`](datos/README.md)).

El motor de producción de la aplicación no está en este repositorio y no es público. Bizkaibus+ es una aplicación
independiente, sin relación con Bizkaibus, la Diputación Foral de Bizkaia ni los operadores del servicio.
