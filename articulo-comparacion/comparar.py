"""Artículo 2: las llegadas del método frente a los tiempos de espera oficiales de Bizkaibus, en los mismos autobuses,
paradas y minutos, contra el paso real.

Para cada consulta al servicio oficial (una parada y un minuto) y cada línea que da, el servicio anuncia los dos
próximos autobuses (e1 y e2, en minutos). Se emparejan con los autobuses de esa línea que pasan de verdad por la parada
después de la consulta, en el orden en que pasan (e1 con el primero, e2 con el segundo). Para cada uno se toma la
predicción del método en la última instantánea del feed anterior a la consulta (como mucho 60 s antes), calculada con
referencia/referencia.py, y el paso real: el punto medio entre la última instantánea en la que el autobús aún no había
pasado la parada y la primera en la que ya sí (la misma verdad que referencia/evaluar.py).

Las tablas aprendidas del método son las de antes de la semana de captura: el método no aprende de los días que se
miden.

Uso:
  python3 comparar.py --bloques <carpeta con los bloques del día, descomprimidos> --base <bizkaibus.sqlite>
      --tablas <carpeta con segment-times.json, pace-factors.json y trip-offsets.json> --paradas paradas.json
      --salida <pares.jsonl> [--festivo]

Escribe una línea por par (consulta oficial, autobús) con los dos errores. resultados.py hace las tablas.
"""
import argparse
import bisect
import datetime
import glob
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'referencia'))
import referencia as R  # noqa: E402
import evaluar as E  # noqa: E402

MADRID = ZoneInfo('Europe/Madrid')
HORIZONTE_MAXIMO = 3600           # s: se emparejan pasos hasta 60 min después (el análisis principal usa hasta 30)
HUECO_MAXIMO = 90                 # s: el paso real solo vale si las dos copias que lo encierran distan como mucho esto
AUSENCIA_MAXIMA = 300             # s: el autobús puede faltar del feed hasta 5 min sin que se pierda su paso
GPS_RADIO = 500                   # m: el paso por GPS exige un punto del recorrido a menos de esto de la parada
ANTIGUEDAD_MAXIMA = 60            # s: la instantánea del método, como mucho 60 s anterior a la consulta oficial


def linea_numero(texto):
    """La línea como la escribe el horario: el servicio oficial pone A0651 o A3512, el horario 651 o 3512."""
    cifras = ''.join(c for c in str(texto) if c.isdigit())
    return str(int(cifras)) if cifras else str(texto)


def segundos(epoch, dia):
    local = datetime.datetime.fromtimestamp(epoch, MADRID)
    base = datetime.datetime.fromisoformat(dia).replace(tzinfo=MADRID)
    return (local - base).total_seconds()


def paso_real(por_vehiculo, instantes, vehiculo, clave, desde, seq):
    # clave: la referencia completa del viaje en el feed (línea, número y hora de salida); Bizkaibus repite el número
    # de viaje varias veces al día, así que la línea y el número solos no bastan.
    """Paso real por la parada seq, como en evaluar.paso_real (punto medio entre la última copia en la que aún no la
    había pasado y la primera en la que ya sí, sin cambiar de viaje), pero sin perderlo porque el autobús falte de una
    copia suelta (hasta AUSENCIA_MAXIMA) y sin darlo si esas dos copias distan más de HUECO_MAXIMO (hueco del feed)."""
    visto = por_vehiculo.get(vehiculo, {})
    ultimo = desde
    for j in range(desde + 1, len(instantes)):
        if instantes[j] == 0:
            continue
        v = visto.get(j)
        if v is None:
            if instantes[j] - instantes[ultimo] > AUSENCIA_MAXIMA:
                return None
            continue
        clave_j, entrada = v
        if clave_j != clave:
            return None
        if entrada.get('order') is not None and entrada['order'] > seq:
            if instantes[j] - instantes[ultimo] > HUECO_MAXIMO:
                return None
            return (instantes[j] + instantes[ultimo]) / 2
        ultimo = j
    return None


def metros_entre(lat1, lon1, lat2, lon2):
    x = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2)) * R.METERS_PER_DEGREE
    y = (lat2 - lat1) * R.METERS_PER_DEGREE
    return math.hypot(x, y)


def paso_gps(por_vehiculo, vehiculo, clave, desde, lat, lon):
    """Paso por GPS, sin el campo de la próxima parada: el momento de máxima aproximación a la parada, interpolado
    entre los dos puntos del recorrido que la encierran. None si ningún punto queda a menos de GPS_RADIO."""
    if lat is None or lon is None:
        return None
    puntos = []
    for j in sorted(k for k in por_vehiculo.get(vehiculo, {}) if k >= desde):
        clave_j, e = por_vehiculo[vehiculo][j]
        if clave_j != clave:
            break
        if e.get('lat') is None or e.get('locationSeconds') is None:
            continue
        if puntos and puntos[-1][0] == e['locationSeconds']:
            continue
        puntos.append((e['locationSeconds'], e['lat'], e['lon']))
    if not puntos:
        return None
    d = [metros_entre(la, lo, lat, lon) for _, la, lo in puntos]
    k = min(range(len(d)), key=d.__getitem__)
    if d[k] > GPS_RADIO:
        return None
    vecinos = [n for n in (k - 1, k + 1) if 0 <= n < len(puntos)]
    if not vecinos:
        return puntos[k][0]
    n = min(vecinos, key=d.__getitem__)
    tramo = metros_entre(puntos[k][1], puntos[k][2], puntos[n][1], puntos[n][2])
    if tramo == 0 or d[k] + d[n] > 1.3 * tramo:
        return puntos[k][0]
    return puntos[k][0] + (puntos[n][0] - puntos[k][0]) * d[k] / (d[k] + d[n])


def predicciones_del_metodo(ficheros, dia, horario, tablas, objetivo, festivo):
    """Por (autobús, viaje, parada objetivo): la lista de (instante, llegada prevista) y el paso real."""
    tramos, ritmo, viajes = tablas
    instantaneas = []
    for fichero in ficheros:
        mapa = E.leer_instantanea(fichero, dia)
        ahora = max((e['locationSeconds'] for entradas in mapa.values() for e in entradas
                     if e['locationSeconds'] is not None), default=0)
        instantaneas.append((ahora, mapa))
    instantes = [ahora for ahora, _ in instantaneas]
    por_vehiculo = {}
    for i, (_, mapa) in enumerate(instantaneas):
        for clave, entradas in mapa.items():
            for e in entradas:
                por_vehiculo.setdefault(e['vehicleRef'], {})[i] = (e['tripRef'], e)
    metodo = {}       # (vehículo, clave, parada) -> {'linea', 'real', 'pred': [(instante, eta)]}
    for i, (ahora, mapa) in enumerate(instantaneas):
        if ahora == 0:
            continue
        refs = [e['tripRef'] for entradas in mapa.values() for e in entradas]
        alias = horario.viajes_de(refs)
        primera = {}
        for entradas in mapa.values():
            for e in entradas:
                v = alias.get(e['tripRef'])
                if v is not None and v not in primera:
                    primera[v] = e
        for clave, entradas in mapa.items():
            for e in entradas:
                id_viaje = alias.get(e['tripRef'])
                if id_viaje is None or e['order'] is None:
                    continue
                viaje = horario.viaje(id_viaje)
                if viaje is None:
                    continue
                quedan = [p for p in viaje['stops'] if p['seq'] >= e['order'] and p['id'] in objetivo]
                if not quedan:
                    continue
                predictor = None
                for parada in quedan:
                    llave = (e['vehicleRef'], e['tripRef'], parada['id'])
                    fila = metodo.get(llave)
                    if fila is None:
                        real = paso_real(por_vehiculo, instantes, e['vehicleRef'], e['tripRef'], i, parada['seq'])
                        fila = metodo[llave] = {'linea': viaje['line'], 'real': real, 'horario': parada['arr'], 'pred': [],
                                                'id_viaje': id_viaje, 'seq': parada['seq'],
                                                'real_gps': paso_gps(por_vehiculo, e['vehicleRef'], e['tripRef'], i, parada.get('lat'), parada.get('lon'))}
                    if fila['real'] is None or fila['real'] - ahora > HORIZONTE_MAXIMO + ANTIGUEDAD_MAXIMA:
                        continue
                    if predictor is None:
                        predictor = R.Matcher(viaje, primera.get(id_viaje), ahora, dia, tramos, ritmo, viajes, festivo)
                    salida = predictor.enrich(parada['arr'], parada['seq'])
                    try:
                        metros = predictor.meters_from_stop(parada['seq'])
                        if metros is not None and not math.isfinite(metros):
                            metros = None
                    except Exception:
                        metros = None
                    fila['pred'].append((ahora, salida['eta'], salida['status'], metros))
    return metodo


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--bloques', required=True)
    p.add_argument('--base', required=True)
    p.add_argument('--tablas', required=True)
    p.add_argument('--paradas', required=True)
    p.add_argument('--salida', required=True)
    p.add_argument('--festivo', action='store_true')
    p.add_argument('--sin-aprender', action='store_true',
                   help='Bide+ sin ninguna de las tres tablas aprendidas (ablación)')
    p.add_argument('--vaciar', default='',
                   help='ablación por partes: tablas que se vacían, separadas por comas (tramos, ritmo, viajes)')
    a = p.parse_args()

    paradas = {x['id']: x for x in json.load(open(a.paradas, encoding='utf-8'))['paradas']}
    ficheros = sorted(glob.glob(os.path.join(a.bloques, '**', 'vm_*.xml'), recursive=True),
                      key=os.path.basename)
    if not ficheros:
        sys.exit('No hay vm_*.xml en ' + a.bloques)
    dia = os.path.basename(ficheros[0])[3:11]
    dia = '%s-%s-%s' % (dia[:4], dia[4:6], dia[6:])
    tablas = tuple(json.load(open(os.path.join(a.tablas, n), encoding='utf-8'))
                   for n in ('segment-times.json', 'pace-factors.json', 'trip-offsets.json'))
    if a.sin_aprender:
        tablas = ({}, {}, {})
    vaciar = {x for x in a.vaciar.split(',') if x}
    tablas = tuple({} if nombre in vaciar else t for nombre, t in zip(('tramos', 'ritmo', 'viajes'), tablas))
    horario = E.Horario(a.base)
    metodo = predicciones_del_metodo(ficheros, dia, horario, tablas, set(paradas), a.festivo)

    # Los pasos reales por parada y línea, en orden: con ellos se sabe qué autobús es e1 y cuál e2.
    pasos = {}
    for (vehiculo, clave, parada), fila in metodo.items():
        if fila['real'] is not None:
            pasos.setdefault((parada, linea_numero(fila['linea'])), []).append((fila['real'], vehiculo, clave))
    for lista in pasos.values():
        lista.sort()

    oficiales = []
    for fichero in sorted(glob.glob(os.path.join(a.bloques, '**', 'oficial.jsonl'), recursive=True)):
        with open(fichero, encoding='utf-8') as f:
            oficiales += [json.loads(l) for l in f]
    cuentas = {'consultas': 0, 'anuncios': 0, 'sin_paso': 0, 'sin_metodo': 0, 'ruta_doble': 0, 'pares': 0,
               'e1_menos_30': 0, 'consultas_antes_6': 0}
    with open(a.salida, 'w', encoding='utf-8') as salida:
        for o in oficiales:
            if o.get('estado') != 'OK':
                continue
            cuentas['consultas'] += 1
            t = segundos(o['t'], dia)
            if t < 6 * 3600:
                cuentas['consultas_antes_6'] += 1
            lineas = [l for l in o['lineas'] if l.get('linea')]
            cuentas['e1_menos_30'] += sum(1 for l in lineas if l.get('e1') and l['e1'].get('minutos') is not None
                                          and l['e1']['minutos'] < 30 and t >= 6 * 3600)
            repetidas = {k for k in (linea_numero(l['linea']) for l in lineas)
                         if sum(linea_numero(m['linea']) == k for m in lineas) > 1}
            for l in lineas:
                linea = linea_numero(l['linea'])
                for orden, e in enumerate(('e1', 'e2')):
                    if e not in l or l[e].get('minutos') is None:
                        continue
                    cuentas['anuncios'] += 1
                    if linea in repetidas:
                        cuentas['ruta_doble'] += 1
                        continue
                    lista = pasos.get((o['parada'], linea), [])
                    k = bisect.bisect_right(lista, (t, '', ''))
                    if k + orden >= len(lista):
                        cuentas['sin_paso'] += 1
                        continue
                    real, vehiculo, clave = lista[k + orden]
                    if real - t > HORIZONTE_MAXIMO:
                        cuentas['sin_paso'] += 1
                        continue
                    fila_m = metodo[(vehiculo, clave, o['parada'])]
                    preds = [x for x in fila_m['pred'] if t - ANTIGUEDAD_MAXIMA <= x[0] <= t]
                    if preds:
                        instante, eta, estado, metros_bus = preds[-1]
                        capa = 'feed'
                    else:
                        # El autobús aún no está en el feed (o lleva más de 60 s sin dato): la app daría la capa 3, el
                        # horario corregido viaje a viaje, sin dato en directo. Se calcula igual, para no comparar solo
                        # cuando Bide+ ve el autobús.
                        viaje = horario.viaje(fila_m['id_viaje'])
                        salida3 = R.Matcher(viaje, None, t, dia, *tablas, a.festivo).enrich(fila_m['horario'], fila_m['seq'])
                        instante, eta, estado, metros_bus = t, salida3['eta'], salida3['status'], None
                        capa = 'sin_feed'
                        cuentas['sin_metodo'] += 1
                    anterior = lista[k + orden - 1][0] if k + orden >= 1 else None
                    siguiente = lista[k + orden + 1][0] if k + orden + 1 < len(lista) else None
                    cuentas['pares'] += 1
                    salida.write(json.dumps({
                        'dia': dia, 'viaje': clave, 'vehiculo': vehiculo, 'parada': o['parada'], 'prioritaria': bool(paradas[o['parada']].get('prioritaria')),
                        'linea': linea, 'e': orden + 1, 't': round(t), 'real': round(real, 1),
                        'oficial': round(t + 60 * l[e]['minutos']), 'minutos': l[e]['minutos'],
                        'metodo': round(eta), 'estado': estado, 'instante': instante, 'capa': capa,
                        'metros_oficial': l[e].get('metros'), 'tipo': l[e].get('tipo', ''), 'segundos_oficial': o.get('segundos'), 'metros_bus': None if metros_bus is None else round(metros_bus),
                        'horario': metodo[(vehiculo, clave, o['parada'])]['horario'],
                        'hueco': min([abs(real - x) for x in (anterior, siguiente) if x is not None], default=None),
                        'siguiente': None if siguiente is None else round(siguiente, 1),
                        'real_gps': None if fila_m['real_gps'] is None else round(fila_m['real_gps'], 1),
                    }) + '\n')
    print(dia, json.dumps(cuentas))
    with open(a.salida + '.cuentas.json', 'w', encoding='utf-8') as f:
        json.dump(dict(cuentas, dia=dia), f)


if __name__ == '__main__':
    main()
