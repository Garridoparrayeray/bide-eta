# bide-eta

**Bus arrival prediction from position-only real-time feeds and interpolated timetables.**
Reference implementation, test vectors, public evaluator and data of the method behind the
[Bizkaibus+](https://www.bideplus.eus) app (Bide+). *Versión en castellano: [LEEME.md](LEEME.md).*

Bizkaibus, the interurban bus network of Biscay (Spain), publishes the GPS position and the next stop of every vehicle
but not its delay, and the intermediate times of its official timetable are interpolated at constant speed. The method
works with timetable differences instead of absolute times, learns the actual travel time of every segment between
stops by time band with medians shrunk towards the all-day median, and predicts in three layers with explicit
abstention rules: the position projected on the route, the last stop registered by the feed, and the timetable
corrected trip by trip.

## Publications

The work is published in three parts, each in its own folder:

| | Folder | What it is | Status |
|---|---|---|---|
| 1 | [`memoria/`](memoria/) | **Technical report** (in Spanish, APA 7): the complete method, every measurement behind each constant, the full evaluation and the reference implementation. LaTeX sources and PDF. | Published first |
| 2 | [`articulo-metodo/`](articulo-metodo/) | **Paper 1** (in English): the reproducible method, its evaluation over 23 days and the comparison with other methods. | Draft |
| 3 | [`articulo-comparacion/`](articulo-comparacion/) | **Paper 2** (in English): the method against the waiting times that Bizkaibus itself shows, on the same buses and stops. The one-week capture is in [`captura/`](articulo-comparacion/captura/). | Capturing data |

Shared by the three:

| Folder | Contents |
|---|---|
| [`referencia/`](referencia/) | `referencia.py`, a reimplementation of the method written only from the technical report; `vectores.json`, test vectors with 407 checks produced by the production engine; `comprobar.py`, which checks one against the other; `evaluar.py`, the public evaluator |
| [`datos/`](datos/) | The learned tables (segment times, pace factors, per-trip corrections), the evaluation data behind the tables of the papers, and the data sheet |

## Quick start

Python 3.9 or later, standard library only.

```bash
python3 referencia/comprobar.py
```

It prints `407 de 407 comprobaciones coinciden con el código de producción` when the reference implementation
reproduces the production engine exactly.

To evaluate on captures of the live feed (SIRI Vehicle Monitoring files `vm_*.xml`) with a timetable database built
from the GTFS:

```bash
python3 referencia/evaluar.py --capturas <folder with vm_*.xml> --base <bizkaibus.sqlite> --tablas datos/tablas
```

It prints the share of arrivals within ±1, ±2 and ±3 minutes by horizon, for the method and for the published
timetable, and can write 15-second error histograms (`--jsonl`). With 40 minutes of the live feed of 7 November 2026
(92,686 predictions) its histograms are identical, bin by bin, to those of the production evaluator, in the three
modes (`normal`, `sin-gps`, `sin-feed`).

## Results so far

On 2.37 million predictions from 17 days (15–31 October 2026) checked against the actual passage, the displayed
arrival is within ±2 minutes 96% of the time when the bus is under three minutes away and 67% at ten to twenty
minutes, against 24% and 25% for the published timetable.

## How to cite

The method is described in the technical report (in Spanish), which has its own DOI:

> Garrido, Y. (2026). *Predicción de llegadas de autobuses con posiciones en tiempo real y horarios interpolados*
> (Version 2.1) [Technical report]. Zenodo. https://doi.org/10.5281/zenodo.24041572

```bibtex
@techreport{garrido_memoria_2026,
  author      = {Garrido, Yeray},
  title       = {Predicción de llegadas de autobuses con posiciones en tiempo real y horarios interpolados},
  institution = {Zenodo},
  type        = {Technical report},
  year        = {2026},
  version     = {2.1},
  doi         = {10.5281/zenodo.24041572},
  language    = {spanish}
}
```

To cite the code and data of this repository, use the "Cite this repository" button (from
[`CITATION.cff`](CITATION.cff)) or:

```bibtex
@software{garrido_bide_eta_2026,
  author  = {Garrido, Yeray},
  title   = {bide-eta: bus arrival prediction from position-only real-time feeds and interpolated timetables},
  year    = {2026},
  url     = {https://github.com/Garridoparrayeray/bide-eta},
  version = {0.1.0}
}
```

Author: Yeray Garrido, [ORCID 0009-0008-0459-0294](https://orcid.org/0009-0008-0459-0294).

## Licence

- Code: [MIT](LICENSE).
- Text and data produced here (documentation, learned tables, evaluation results): [CC BY 4.0](LICENSE-CC-BY-4.0.txt).
- Timetable and live feed: open data of their publishers, reused with attribution (sources in
  [`datos/README.md`](datos/README.md)).

The production engine of the app is not part of this repository and is not public. Bizkaibus+ is an independent app
with no relation to Bizkaibus, the Diputación Foral de Bizkaia or the service operators.
