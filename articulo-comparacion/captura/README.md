# articulo-comparacion/captura/ — the method against Bizkaibus's own waiting times

*Castellano más abajo.*

## Purpose

Bizkaibus shows its own real-time waiting times at stops (official app since 2023, some stop displays). This folder
captures those official predictions together with the live feed, so that both can be compared with the method of this
repository **on the same buses, stops and moments, against the same actual passage**.

## What is captured

| Data | Source | Frequency | File |
|---|---|---|---|
| Live positions (SIRI Vehicle Monitoring) | `https://ctb-siri.s3.eu-south-2.amazonaws.com/bizkaibus-vehicle-positions.xml` | every 20 s | `vm_AAAAMMDD-HHMMSS.xml` |
| Official waiting times | `https://apli.bizkaia.net/APPS/DANOK/TQWS/TQ.ASMX/GetPasoParadaMobile_JSON` (the service behind the official app) | every ~60 s, for each stop in [`paradas.json`](paradas.json) | `oficial.jsonl` |
| Timetable of the day (GTFS) | `https://ctb-gtfs.s3.eu-south-2.amazonaws.com/bizkaibus.zip` | once a day | `gtfs-AAAAMMDD.zip` |

The 60 stops are intermediate stops with many buses and lines, at least 15 minutes from the start of the trip, plus
28 **priority** stops: the ones users pointed out (San Juan, Durango, Elorrio) and the Bilbao stops where the actual
passage deviates most from the published time. Each stop has its reason in `paradas.json`. The official service needs
the stop code with four digits (`0356`, not `356`; `00356` is another stop); the data are stored with the timetable
number.

Each line of `oficial.jsonl` (a real one, first line of the stop only):

```json
{"t": 1794070792.3, "hora": "2026-11-07T17:59:52+01:00", "parada": "356", "estado": "OK", "lineas": [{"linea": "A3144", "ruta": "BILBAO", "e1": {"minutos": 7, "metros": 2355, "tipo": ""}, "e2": {"minutos": 30, "metros": 9137, "tipo": ""}}], "segundos": 1.22}
```

`e1` and `e2` are the next two buses of the line at that stop, as the official service gives them: minutes to arrival
and the bus's distance in metres. `estado` is `OK`, `NOINFO` (no buses announced) or `ERROR`.

The method's predictions are **not** captured from the Bide+ API: they are recomputed afterwards with
`referencia/referencia.py` on the same feed snapshots, which reproduces the production engine exactly. The only
difference with the live app is that the replay does not use the log of buses already passed, which only
affects trips that have left the feed.

## When and where

The workflow [`.github/workflows/comparacion.yml`](../../.github/workflows/comparacion.yml) captures continuously from
06:00 to 23:00 Madrid time on GitHub Actions: each run lasts until 23:00 (at most 335 minutes) and launches the next
one when it ends, with an hourly schedule as a backup in case GitHub delays or skips a run, as in the capture of the
Bide+ app. Each block is uploaded to the release `comparacion-AAAA-MM` of this repository as `captura-<start>.tar.xz`.
The feed repeats old data from 23:58 to 05:00, so night hours are not captured.

To run it on your own computer (Python 3.9+, no other dependency, works on Windows):

```bash
python3 articulo-comparacion/captura/capturar.py --minutos 60 --salida mi-captura
```

## Days

The week runs from Sunday 8 to Saturday 14 November 2026. [`dias.json`](dias.json) lists the days the analysis uses:
Wednesday 11 November was a general strike (Bizkaibus ran minimum services, about 30 %), so it is captured like the
others but analysed **separately**, not in the results of the week. Monday 9 only covers 12:42 to 23:00.

## Load and attribution

The capture makes one request to the official service per stop and minute (about one per second in total), sequentially,
with a user agent that points to this repository, and one request to the public feed every 20 s. Data belong to their
publishers (Diputación Foral de Bizkaia / Bizkaibus); they are kept here for research, with attribution. If the
publisher asks us to stop or to remove them, we will.

---

## Castellano

**Para qué.** Bizkaibus enseña sus propios tiempos de espera en tiempo real (app oficial desde 2023 y algunas pantallas
en marquesinas). Esta carpeta guarda esas predicciones oficiales junto con el feed, para compararlas con el método de
este repositorio **en los mismos autobuses, paradas y momentos, contra el mismo paso real**.

**Qué se guarda.** El feed SIRI cada 20 s (`vm_*.xml`), los tiempos de espera oficiales de 60 paradas cada minuto
(`oficial.jsonl`) y el horario GTFS del día. De las 60 paradas, 28 son **prioritarias**: las que señalaron usuarios
(San Juan, Durango, Elorrio) y las de Bilbao donde el paso real más se aparta de la hora publicada. El motivo de cada
una está en `paradas.json`. El servicio oficial pide el código de parada con cuatro cifras (`0356`, no `356`).

Las predicciones del método **no** se piden a la API de Bide+: se recalculan después con `referencia/referencia.py`
sobre las mismas capturas del feed, que da exactamente lo mismo que el motor de producción.

**Cuándo y dónde.** Sin parar de 06:00 a 23:00 en GitHub Actions: cada tanda dura hasta las 23:00 (como mucho 335
minutos) y al terminar lanza la siguiente, con un cron horario de respaldo por si GitHub se salta alguna, como en la
captura de Bide+. Cada bloque se sube a la release `comparacion-AAAA-MM`. Para hacerlo en tu ordenador: `python3 articulo-comparacion/captura/capturar.py --minutos 60 --salida mi-captura`.

**Días.** La semana va del domingo 8 al sábado 14 de noviembre de 2026. [`dias.json`](dias.json) dice qué días usa
el análisis: el miércoles 11 hubo huelga general (Bizkaibus con servicios mínimos, alrededor del 30 %), así que se
captura como los demás pero se analiza **aparte**, fuera de los resultados de la semana. El lunes 9 solo va de 12:42 a
23:00.

**Carga y atribución.** Una petición por parada y minuto al servicio oficial, una detrás de otra, identificándose con
este repositorio. Los datos son de quien los publica (Diputación Foral de Bizkaia / Bizkaibus) y se guardan para
investigación, citando la fuente. Si piden que paremos o que los quitemos, lo haremos.
