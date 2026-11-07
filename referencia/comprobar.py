"""Comprueba la implementación de referencia (referencia.py) contra los vectores del código de producción."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import referencia as R

import os
AQUI = os.path.dirname(os.path.abspath(__file__))
V = json.load(open(os.path.join(AQUI, 'vectores.json'), encoding='utf-8'))
fallos = 0
total = 0
def igual(nombre, esperado, obtenido, tol=1e-6):
    global fallos, total
    total += 1
    ok = esperado == obtenido
    if isinstance(esperado, float) or isinstance(obtenido, float):
        ok = esperado is not None and obtenido is not None and abs(esperado - obtenido) <= tol
    if not ok:
        fallos += 1
        print('FALLO', nombre, 'esperado', esperado, 'obtenido', obtenido)

for v in V['percentil']:
    igual('percentil', v['resultado'], R.percentile(v['valores'], v['p']))
for v in V['franja']:
    igual('franja', v['franja'], R.band_for(v['fecha'], v['segundos']))
pace = {'global': {'laborable.punta_manana': 0.9, 'laborable.noche': 0.4}, 'lines': {'3414': {'laborable.punta_manana': 1.35}}}
for v in V['factor_k']:
    igual('k', v['k'], R.pace_factor(pace, v['linea'], v['fecha'], v['segundos']))
for v in V['proyeccion']:
    f, d, l = R.project_onto_segment(v['bus'][0], v['bus'][1], v['A'], v['B'])
    igual('proy f', v['f'], f); igual('proy d', v['distancia_m'], d, 1e-6); igual('proy L', v['largo_m'], l, 1e-6)
for v in V['cubo_largo']:
    igual('cubo', v['cubo'], R.length_bucket(v['metros']))
ratios = {'segments': {'X>Y': {'n': 2, 'all': 1}}, 'lengthRatios': {'2': {'all': 0.769, 'laborable.punta_manana': 0.811}, '4': {'all': 2.0}, '5': {'all': 0.1}}}
for v in V['respaldo_largo']:
    igual('respaldo', v['segundos'], R.fallback_seconds(ratios, float(v['horario_s']), v['metros'], v['franja']), 1e-9)
# lengthRatios en forma de lista (como lo escribe PHP con los seis cubos) da lo mismo que en forma de objeto
lista = {'segments': {'X>Y': {'n': 2, 'all': 1}}, 'lengthRatios': [{'all': 1.0}, {'all': 0.9}, {'all': 0.769, 'laborable.punta_manana': 0.811}, {'all': 0.65}, {'all': 0.64}, {'all': 0.53}]}
igual('respaldo con lista', 0.811 * 120, R.fallback_seconds(lista, 120.0, 800, 'laborable.punta_manana'), 1e-9)
igual('respaldo con lista, cubo 5', 0.53 * 300, R.fallback_seconds(lista, 300.0, 5000, 'laborable.manana'), 1e-9)
igual('tiempos por tramo', V['tiempos_tramo']['resultado'], R.fit_segments(V['tiempos_tramo']['muestras']))
for v in V['k_calibrado']:
    tracks = {'t%d' % i: [{'actualRemaining': 600 * r, 'scheduledRemaining': 600}] for i, r in enumerate(v['cocientes_por_bus'])}
    igual('k calibrado', v['k'], R.shrunk_factor(tracks))
for v in V['paso_real']:
    igual('paso real', v['paso_real'], R.actual_passing_time(v['pista'], v['llegada_programada']), 1e-9)
igual('aclarado', V['aclarado']['indices'], [s['i'] for s in R.thin([{'i': i} for i in range(100)])])

# Corrección por viaje
cv = V['correccion_viaje']
igual('clave del viaje', cv['clave'], R.trip_key('9999', 'S0', 'S4', 28800, 5))
for indice, paradas, tercio in cv['tercios']:
    igual('tercio %d de %d' % (indice, paradas), tercio, R.trip_part(indice, paradas))
for fecha, festivo, dia in cv['dia_servicio']:
    igual('día de servicio ' + fecha, dia, R.service_date(fecha, festivo))
for c in cv['consultas']:
    igual('corrección ' + c['clave'] + ' ' + c['fecha'], c['segundos'], R.trip_offset(cv['tabla'], c['clave'], c['linea'], c['fecha'], c['salida'], c['indice'], c['paradas']))
igual('calibración de la corrección por viaje', V['calibracion_viaje']['resultado'], R.fit_trip_offsets(V['calibracion_viaje']['desvios']))

# Escenarios del emparejador
vj = V['viaje']
segments_base = {'segments': vj['tramos_aprendidos'], 'lengthRatios': vj['proporciones']}
pace_k = {'global': vj['k']}
for e in V['escenarios']:
    publicadas = [p['hora_publicada'] for p in e['paradas']]
    stops = []
    for i, p in enumerate(vj['paradas']):
        dist = None
        if e['trazado']:
            dist = p['dist_m']
        stops.append({'seq': i + 1, 'id': p['id'], 'arr': publicadas[i], 'dep': publicadas[i], 'lat': p['lat'], 'lon': p['lon'],
                      'dist': dist})
    shape = None
    if e['trazado']:
        shape = [[p['lat'], p['lon'], p['dist_m']] for p in vj['paradas']]
    journey = {'stops': stops, 'shape': shape, 'line': '9999'}
    segs = segments_base
    if 'probablemente' in e['escenario']:
        segs = {'segments': {'S0>S1': {'n': 9, 'laborable.punta_manana': 110}, 'S1>S2': {'n': 9, 'laborable.punta_manana': 140},
                             'S2>S3': {'n': 9, 'laborable.punta_manana': 240}, 'S3>S4': {'n': 9, 'laborable.punta_manana': 100}}}
    trips = None
    if e.get('correccion_viaje'):
        trips = cv['tabla']
    festivo = e.get('festivo', False)
    M = R.Matcher(journey, e['entrada'], e['ahora'], vj['fecha'], segs, pace_k, trips, festivo)
    if e['entrada'] is not None:
        pos = M.position()
        exp = e['posicion']
        esperado = None
        if exp is not None:
            esperado = exp['scheduledSeconds']
        obtenido = None
        if pos is not None:
            obtenido = pos['scheduledSeconds']
        igual(e['escenario'] + ' · posición', esperado, obtenido)
    for i, p in enumerate(e['paradas']):
        out = R.Matcher(journey, e['entrada'], e['ahora'], vj['fecha'], segs, pace_k, trips, festivo).enrich(p['hora_publicada'], i + 1)
        igual(e['escenario'] + ' · ' + p['parada'] + ' estado', p['estado'], out['status'])
        igual(e['escenario'] + ' · ' + p['parada'] + ' llegada', p['llegada_estimada'], out['eta'])
        igual(e['escenario'] + ' · ' + p['parada'] + ' retraso', p['retraso_s'], out['delay'])

print(f'{total - fallos} de {total} comprobaciones coinciden con el código de producción')
if fallos:
    sys.exit(1)
sys.exit(0)
