# referencia/

| File | What it does |
|---|---|
| `referencia.py` | The method, written only from the technical report (not from the production code): projection on the route, the three prediction layers, segment times, pace factors, per-trip correction and their calibration |
| `vectores.json` | 323 test vectors: concrete inputs and the exact output of the production engine |
| `comprobar.py` | Runs `referencia.py` on every vector and reports how many match |
| `evaluar.py` | Public evaluator: predicts every stop from the next one to eight ahead in each snapshot of the live feed, takes the actual passage from the change of next stop, and writes 15-second error histograms (`histograma-v1`) by layer, status, horizon and time band |
| `desvio-horario.py` | Figures of section 1.1 of the report: line frequency and the gap between the actual passage and the published time |

Conventions to keep when porting to another language (also at the top of `referencia.py`):

- Times are seconds since midnight (Europe/Madrid) of the service day and may exceed 86,400.
- `round()` rounds halves away from zero, as PHP does, not to even.
- Medians are low medians: element ⌊p·(n−1)⌋ of the sorted values.
- Line numbers are written without leading zeros: the feed writes `A0651`, the timetable `651`.

The vectors were produced with the production engine, which is not public; `comprobar.py` only needs this folder.
