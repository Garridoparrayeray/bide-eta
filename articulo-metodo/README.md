# articulo-metodo/ — Paper 1: the reproducible method

*Predicting bus arrivals when the feed reports positions but not delays: a reproducible three-layer method with an
open reference implementation.*

| File | Contents |
|---|---|
| `articulo.tex` | Main file: abstract, introduction, data, evaluation, reproducibility and conclusions |
| `relacionado.tex`, `metodo.tex`, `evaluacion-dias.tex`, `discusion.tex`, `apendice.tex` | Related work, method, day-by-day evaluation, discussion and the table of constants |
| `referencias.bib` | References, each checked against its DOI or primary source |
| `resultados.py` | Recomputes the result tables from [`../datos/evaluacion/`](../datos/evaluacion/) |

Build with `latexmk -pdf articulo.tex` (pdflatex and biber; the `elsarticle` class is in TeX Live). The tables can be
checked with `python3 articulo-metodo/resultados.py` from the root of the repository.

---

## En castellano

El artículo 1 describe el método con detalle suficiente para reimplementarlo y lo evalúa en 23 días. Se compila con
`latexmk -pdf articulo.tex` (pdflatex y biber), y `python3 articulo-metodo/resultados.py`, desde la raíz del
repositorio, vuelve a calcular sus tablas a partir de los datos públicos.
