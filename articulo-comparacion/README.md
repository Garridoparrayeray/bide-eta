# articulo-comparacion/ — Paper 2: the method against Bizkaibus's own waiting times

Paper 2 compares the arrivals predicted by the method with the waiting times that Bizkaibus itself shows to passengers,
on the same vehicles and stops, against the actual passage reconstructed from the live feed.

| Folder | Contents |
|---|---|
| [`captura/`](captura/) | The capture: the live feed every 20 s and the official waiting times of 60 stops every minute, continuously from 06:00 to 23:00 for one week, uploaded to the monthly release `comparacion-AAAA-MM` with the timetable of the day |
| `comparar.py` | Pairs each official announcement with the bus that actually passes and with the method's prediction for that bus at the same minute (`referencia/referencia.py`, learned tables of 7 November); one line per pair |
| `resultados.py` | Tables of the paper from the pairs, with 95 % bootstrap intervals by whole trips |
| `articulo.tex`, `cuerpo.tex`, `resumen.tex`, `tabla-dias.tex`, `tablas/` | The paper (draft) |

Build with `latexmk -pdf articulo.tex`. To redo a day: download and unpack its `captura-AAAAMMDD-*.tar.xz`, run
`python3 comparar.py --bloques <folder> --base bizkaibus.sqlite --tablas <tables> --paradas captura/paradas.json
--salida pares-AAAAMMDD.jsonl`, then `python3 resultados.py <folder with the pares files> --tex tablas`.

---

## En castellano

El artículo 2 compara las llegadas que predice el método con los tiempos de espera que el propio Bizkaibus muestra a
los viajeros, en los mismos autobuses y paradas, frente al paso real reconstruido a partir del feed en directo.

| Carpeta | Contenido |
|---|---|
| [`captura/`](captura/) | La captura: el feed en directo cada 20 s y los tiempos de espera oficiales de 60 paradas cada minuto, sin parar de 06:00 a 23:00 durante una semana, subida a la release mensual `comparacion-AAAA-MM` con el horario del día |

`comparar.py` empareja cada tiempo oficial con el autobús que pasa de verdad y con la predicción del método en el mismo
minuto; `resultados.py` hace las tablas. El artículo (borrador) está en `articulo.tex`.
