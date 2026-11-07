# memoria/ — Technical report

**Predicción de llegadas de autobuses con posiciones en tiempo real y horarios interpolados** (in Spanish, APA 7).

The complete description of the method: the data and their problems, localisation on the route, the segment
travel-time model, the three prediction layers, the daily learning and recalibration, the full evaluation, the
measurement behind every constant, the test vectors and the reference implementation (Appendix E, the same
[`referencia/referencia.py`](../referencia/referencia.py) of this repository). Papers 1 and 2 summarise parts of it in
English.

| File | Contents |
|---|---|
| [`memoria.pdf`](memoria.pdf) | The report, ready to read and print |
| `memoria.tex`, `capitulos/` | LaTeX sources: one file per chapter and appendix |
| `bibliografia.bib` | References (APA 7 with `biblatex-apa`) |
| `pruebas/revisar.py` | Checks the report: compilation, references, that the reference implementation reproduces the 323 vectors, and Spanish typography |

Build from this folder with `latexmk -pdf memoria.tex` (pdflatex and biber; `biblatex-apa` is in TeX Live), or build
and check everything with `python3 pruebas/revisar.py`.

How to cite:

> Garrido, Y. (2026). *Predicción de llegadas de autobuses con posiciones en tiempo real y horarios interpolados*
> [Informe técnico]. https://github.com/Garridoparrayeray/bide-eta/tree/main/memoria

---

## En castellano

La descripción completa del método: los datos y sus problemas, la localización sobre el recorrido, el modelo del
tiempo por tramo, las tres capas de predicción, el aprendizaje y la recalibración de cada noche, la evaluación entera,
la medición que hay detrás de cada constante, los vectores de prueba y la implementación de referencia (anexo E, el
mismo [`referencia/referencia.py`](../referencia/referencia.py) de este repositorio). Los artículos 1 y 2 resumen
partes de ella en inglés.

Se compila desde esta carpeta con `latexmk -pdf memoria.tex` (pdflatex y biber; `biblatex-apa` viene en TeX Live), o
se compila y se revisa todo con `python3 pruebas/revisar.py`.
