# articulo-comparacion/ — Paper 2: the method against Bizkaibus's own waiting times

Paper 2 compares the arrivals predicted by the method with the waiting times that Bizkaibus itself shows to passengers,
on the same vehicles and stops, against the actual passage reconstructed from the live feed.

| Folder | Contents |
|---|---|
| [`captura/`](captura/) | The capture: the live feed every 20 s and the official waiting times of 60 stops every minute, continuously from 06:00 to 23:00 for one week, uploaded to the monthly release `comparacion-AAAA-MM` with the timetable of the day |

`comprobar_captura.py` checks one capture end to end: it pairs each official waiting time with the actual passage of
the next bus of that line at that stop, and computes the method's arrival and the published time for the same bus. The
analysis script and the LaTeX sources of the paper will be added here when the week of data is complete.

---

## En castellano

El artículo 2 compara las llegadas que predice el método con los tiempos de espera que el propio Bizkaibus muestra a
los viajeros, en los mismos autobuses y paradas, frente al paso real reconstruido a partir del feed en directo.

| Carpeta | Contenido |
|---|---|
| [`captura/`](captura/) | La captura: el feed en directo cada 20 s y los tiempos de espera oficiales de 60 paradas cada minuto, sin parar de 06:00 a 23:00 durante una semana, subida a la release mensual `comparacion-AAAA-MM` con el horario del día |

`comprobar_captura.py` comprueba una captura de punta a punta: empareja cada tiempo de espera oficial con el paso real
del siguiente autobús de esa línea por esa parada y calcula, para ese mismo autobús, la llegada del método y la hora
publicada. El programa de análisis y las fuentes LaTeX del artículo se añadirán aquí cuando esté completa la semana de
datos.
