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

# Viajes que pasan de medianoche
dv = V['dia_del_viaje']
for c in dv['casos']:
    igual('día del viaje: salida %d a las %d' % (c['salida'], c['ahora']), c['dias_atras'], R.days_ago({'departureSeconds': c['salida']}, c['ahora']))
igual('buses de viajes de ayer', dv['de_ayer'], R.vehicles_of_day(dv['feed'], dv['ahora'], 1))
igual('buses de viajes de hoy', dv['de_hoy'], R.vehicles_of_day(dv['feed'], dv['ahora'], 0))

# Buses que faltan en una lectura del feed
br = V['buses_retenidos']
igual('buses retenidos 180 s', br['resultado'], R.with_held(br['feed'], br['anterior'], br['ahora']))

# Emparejado de cada bus con su viaje
em = V['emparejado']
for c in em['casos']:
    entrada = R.lookup({'9999|101': c['buses']}, em['alias'], '9999', '101', c['salida'], c['viaje'])
    igual('emparejado: ' + c['caso'], c['bus'], None if entrada is None else entrada['vehicleRef'])

# Lectura del feed SIRI
igual('lectura del feed SIRI', V['lectura_feed']['resultado'], R.parse_siri(V['lectura_feed']['xml'], V['lectura_feed']['hoy']))

# Registro de pasos
rp = V['registro_pasos']
igual('registro de pasos: campos', rp['campos'], R.passage_fields(rp['feed']))
igual('registro de pasos: campos por parada', rp['campos_paradas'], R.passage_stop_fields(rp['feed']))
igual('registro de pasos: lectura', rp['lectura']['resultado'], R.merge_passages(rp['lectura']['viaje_de_cada_campo'], rp['lectura']['valores']))
historial = {ref: {str(k): v for k, v in stops.items()} for ref, stops in R.stops_from_hash(rp['historial']['hash']).items()}
igual('registro de pasos: historial', rp['historial']['resultado'], historial)

# Retraso que se muestra
rm = V['retraso_mostrado']
for c in rm['minutos']:
    igual('minutos mostrados de %s s' % c['segundos'], c['minutos'], R.display_delay_minutes(c['segundos']))

# Elección nocturna del percentil de la corrección por viaje
ep = V['eleccion_percentil']
entreno = [r for r in ep['desvios'] if r['date'] < ep['primer_dia_de_prueba']]
prueba = [r for r in ep['desvios'] if r['date'] >= ep['primer_dia_de_prueba']]
for c in ep['por_percentil']:
    errores = R.trip_offset_errors(prueba, R.fit_trip_offsets(entreno, c['percentil']))
    igual('percentil %.2f: error medio' % c['percentil'], float(c['error_medio_s']), errores[1])
    igual('percentil %.2f: a ±2 min' % c['percentil'], float(c['a_2_min']), errores[3])
elegido, errores = R.choose_trip_offset_rank(entreno, prueba, ep['candidatos'])
igual('percentil elegido', ep['elegido'], elegido)
igual('error medio sin corregir', float(ep['sin_corregir']['error_medio_s']), errores[0])
igual('a ±2 min sin corregir', float(ep['sin_corregir']['a_2_min']), errores[2])
igual('la tabla nueva se escribe solo si baja el error medio', ep['se_escribe'], errores[1] < errores[0])

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

# Escenarios con el registro de pasos: sin bus en el feed
journey_base = {'stops': [{'seq': i + 1, 'id': p['id'], 'arr': p['llegada'], 'dep': p['salida'], 'lat': p['lat'], 'lon': p['lon'],
                           'dist': p['dist_m']} for i, p in enumerate(vj['paradas'])],
                'shape': [[p['lat'], p['lon'], p['dist_m']] for p in vj['paradas']], 'line': '9999'}
for e in V['escenarios_pasos']:
    for i, p in enumerate(e['paradas']):
        out = R.Matcher(journey_base, None, e['ahora'], vj['fecha'], segments_base, pace_k, None, False, e['paso_registrado']).enrich(p['hora_publicada'], i + 1)
        igual(e['escenario'] + ' · ' + p['parada'] + ' estado', p['estado'], out['status'])
        igual(e['escenario'] + ' · ' + p['parada'] + ' llegada', p['llegada_estimada'], out['eta'])
        igual(e['escenario'] + ' · ' + p['parada'] + ' retraso', p['retraso_s'], out['delay'])

# Retraso que se muestra de cada bus
for c in rm['buses']:
    M = R.Matcher(journey_base, c['entrada'], c['ahora'], vj['fecha'], segments_base, pace_k)
    igual(c['caso'] + ' · retraso actual', c['retraso_actual_s'], M.current_delay())
    igual(c['caso'] + ' · retraso mostrado', c['retraso_mostrado_s'], M.display_delay())

print(f'{total - fallos} de {total} comprobaciones coinciden con el código de producción')
if fallos:
    sys.exit(1)
sys.exit(0)
