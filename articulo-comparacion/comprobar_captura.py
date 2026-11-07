"""Comprobación de extremo a extremo de una captura de la comparación (no es todavía el análisis del artículo).

Uso: python3 articulo-comparacion/comprobar_captura.py <carpeta con vm_*.xml y oficial.jsonl> <bizkaibus.sqlite>
(la base del horario la construye la app a partir del GTFS del día, como para referencia/evaluar.py).

Para cada tiempo oficial (parada, línea, e1) busca el primer autobús de esa línea que pasa por esa parada después de
la consulta, con el paso real reconstruido de los cambios de próxima parada del feed, y calcula para ese mismo autobús
y parada la llegada del método (referencia.py) y la hora publicada.
"""
import collections
import datetime
import json
import os
import sys

BIDE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BIDE, 'referencia'))
import evaluar as E  # noqa: E402
import referencia as R  # noqa: E402

captura, base = sys.argv[1], sys.argv[2]
ficheros = E.capturas_de(captura)
dia, _ = E.fecha_de(ficheros[0])
tablas = os.path.join(BIDE, 'datos', 'tablas')
tramos = json.load(open(os.path.join(tablas, 'segment-times.json'), encoding='utf-8'))
ritmo = json.load(open(os.path.join(tablas, 'pace-factors.json'), encoding='utf-8'))
viajes = json.load(open(os.path.join(tablas, 'trip-offsets.json'), encoding='utf-8'))
paradas = {p['id']: p for p in json.load(open(os.path.join(BIDE, 'articulo-comparacion/captura/paradas.json')))['paradas']}

# Instantáneas del feed, como las lee el evaluador público.
instantaneas = []
for f in ficheros:
    mapa = E.leer_instantanea(f, dia)
    ahora = max((e['locationSeconds'] or 0) for es in mapa.values() for e in es) if mapa else 0
    instantaneas.append((ahora, mapa))
instantes = [a for a, _ in instantaneas]
por_vehiculo = {}
for i, (_, mapa) in enumerate(instantaneas):
    for clave, es in mapa.items():
        for e in es:
            por_vehiculo.setdefault(e['vehicleRef'], {})[i] = (clave, e)

horario = E.Horario(base)
refs = {e['tripRef'] for _, m in instantaneas for es in m.values() for e in es}
alias = horario.viajes_de(list(refs))
print('referencias de viaje en el feed: %d; con viaje en el horario: %d' % (len(refs), sum(1 for r in refs if alias.get(r))))

madrid = E.MADRID
def segundos(epoch):
    t = datetime.datetime.fromtimestamp(epoch, madrid)
    return t.hour * 3600 + t.minute * 60 + t.second

pares = []
sin_autobus = collections.Counter()
consultas = collections.Counter()
for linea_json in open(os.path.join(captura, 'oficial.jsonl'), encoding='utf-8'):
    r = json.loads(linea_json)
    if r.get('estado') != 'OK':
        continue
    t = segundos(r['t'])
    i = max(k for k in range(len(instantes)) if instantes[k] <= t) if instantes[0] <= t else None
    if i is None:
        continue
    ahora, mapa = instantaneas[i]
    primera = {}
    for es in mapa.values():
        for e in es:
            v = alias.get(e['tripRef'])
            if v is not None and v not in primera:
                primera[v] = e
    for ln in r.get('lineas', []):
        if not ln.get('e1') or ln['e1'].get('minutos') is None:
            continue
        linea = R.line_key(ln['linea'][1:] if ln['linea'][:1].isalpha() else ln['linea'])
        consultas[(r['parada'], linea)] += 1
        mejor = None
        for clave, es in mapa.items():
            for e in es:
                if e['lineId'] != linea or e['order'] is None:
                    continue
                v = alias.get(e['tripRef'])
                viaje = horario.viaje(v) if v else None
                if viaje is None:
                    continue
                parada = next((p for p in viaje['stops'] if p['id'] == r['parada'] and p['seq'] >= e['order']), None)
                if parada is None:
                    continue
                real = E.paso_real(por_vehiculo, instantes, e['vehicleRef'], clave, i, parada['seq'])
                if real is None or real < t:
                    continue
                if mejor is None or real < mejor[0]:
                    mejor = (real, viaje, parada, primera.get(v), e)
        if mejor is None:
            sin_autobus[(r['parada'], linea)] += 1
            continue
        real, viaje, parada, vivo, e = mejor
        metodo = R.Matcher(viaje, vivo, ahora, dia, tramos, ritmo, viajes).enrich(parada['arr'], parada['seq'])
        pares.append({'parada': r['parada'], 'linea': linea, 'horizonte': real - t,
                      'oficial': t + 60 * ln['e1']['minutos'] - real, 'metodo': metodo['eta'] - real,
                      'estado': metodo['status'], 'horario': parada['arr'] - real})

print('tiempos oficiales (línea y parada con e1): %d; emparejados con un paso real: %d; sin autobús visible que pase: %d'
      % (sum(consultas.values()), len(pares), sum(sin_autobus.values())))

def resumen(nombre, filtro):
    ps = [p for p in pares if filtro(p)]
    if not ps:
        return
    def dentro(k, s):
        return 100 * sum(1 for p in ps if abs(p[k]) <= s) / len(ps)
    def mediana(k):
        v = sorted(abs(p[k]) for p in ps)
        return v[len(v) // 2]
    print('%-22s n=%6d | ±2 min: oficial %5.1f %%  método %5.1f %%  horario %5.1f %% | mediana |e|: %4.0f / %4.0f / %4.0f s'
          % (nombre, len(ps), dentro('oficial', 120), dentro('metodo', 120), dentro('horario', 120),
             mediana('oficial'), mediana('metodo'), mediana('horario')))

for desde, hasta, nombre in [(0, 180, '0-3 min'), (180, 360, '3-6 min'), (360, 600, '6-10 min'), (600, 1200, '10-20 min')]:
    resumen(nombre, lambda p, d=desde, h=hasta: d <= p['horizonte'] < h)
print('-- por parada prioritaria (todas las distancias a menos de 20 min)')
for pid, p in sorted(paradas.items(), key=lambda kv: kv[1]['nombre']):
    if p.get('prioritaria'):
        resumen(p['nombre'][:22], lambda q, pid=pid: q['parada'] == pid and q['horizonte'] < 1200)
sesgo = sorted(p['oficial'] for p in pares if p['horizonte'] < 1200)
print('desvío oficial (oficial - real), mediana: %.0f s; p10 %.0f s; p90 %.0f s' % (
    sesgo[len(sesgo) // 2], sesgo[len(sesgo) // 10], sesgo[9 * len(sesgo) // 10]))
json.dump(pares, open(os.path.join(captura, 'pares.json'), 'w'))
