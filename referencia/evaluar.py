"""Evaluador público de las llegadas: mide la implementación de referencia (referencia.py) con capturas del feed.

Escrito a partir del capítulo «Resultados» de la memoria, sin el código PHP del motor. Por cada instantánea de las
capturas, cada autobús y cada parada que le queda (de la próxima a ocho más allá), predice la llegada con
referencia.Matcher y la compara con el paso real: el punto medio entre la última instantánea en la que el autobús aún
no había pasado la parada y la primera en la que ya sí (ecuación de la verdad de referencia). Los errores se guardan en
histogramas de 15 s por capa, estado, horizonte, franja y tramos sin aprender, en el mismo formato que la evaluación de
producción (histograma-v1), para poder sumar capturas y comparar las dos.

Uso:
  python3 evaluar.py --capturas <carpeta con vm_*.xml> --base <bizkaibus.sqlite> --tablas <carpeta con
      segment-times.json, pace-factors.json y trip-offsets.json> [--seguimiento <carpeta>] [--modo normal|sin-gps|sin-feed]
      [--jsonl <fichero>] [--festivo]

Sin dependencias fuera de la biblioteca estándar de Python 3.9 o posterior.
"""
import argparse
import datetime
import glob
import json
import math
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import referencia as R

MADRID = ZoneInfo('Europe/Madrid')
SIRI = '{http://www.siri.org.uk/siri}'
REF = re.compile(r'^trp_[A-Za-z]+(\d+)_(\d+)_[A-Za-z0-9]+_(\d+)')
HORIZONTES = [(0, 180, '0-3'), (180, 360, '3-6'), (360, 600, '6-10'), (600, 1200, '10-20')]
PARADAS_POR_DELANTE = 8           # se evalúan las paradas de la próxima (n) a n + 8
CUBO_SEGUNDOS = 15                # anchura de cada barra del histograma
CUBO_MAXIMO = 81                  # los errores de más de 81 cubos (20 min y 15 s) van al último


# ----------------------------------------------------------------------------- capturas
def capturas_de(carpeta):
    ficheros = glob.glob(os.path.join(carpeta, 's*.xml')) + glob.glob(os.path.join(carpeta, 'vm_*.xml'))
    return sorted(ficheros)


def fecha_de(fichero):
    """La fecha (y la hora completa) de la primera RecordedAtTime del fichero."""
    with open(fichero, encoding='utf-8', errors='replace') as f:
        cabeza = f.read(4096)
    m = re.search(r'<RecordedAtTime>([^<]+)<', cabeza)
    if m is None:
        return None, None
    return m.group(1)[:10], m.group(1)


def segundos_del_dia(iso, dia):
    """Segundos desde la medianoche de Madrid de «dia»; None si la hora es de otro día o no se entiende."""
    if not iso:
        return None
    try:
        instante = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00'))
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=MADRID)
    local = instante.astimezone(MADRID)
    if local.date().isoformat() != dia:
        return None
    return local.hour * 3600 + local.minute * 60 + local.second


def texto(nodo, ruta):
    hallado = nodo.find(ruta)
    if hallado is None or hallado.text is None:
        return None
    return hallado.text.strip()


def leer_instantanea(fichero, dia):
    """Las entradas del feed agrupadas por «línea|número de viaje», como las lee el motor."""
    try:
        raiz = ET.parse(fichero).getroot()
    except ET.ParseError:
        return {}
    mapa = {}
    for actividad in raiz.iter(SIRI + 'VehicleActivity'):
        mvj = actividad.find(SIRI + 'MonitoredVehicleJourney')
        if mvj is None:
            continue
        ref = texto(mvj, SIRI + 'VehicleJourneyRef')
        if ref is None:
            continue
        m = REF.match(ref)
        if m is None:
            continue
        # La línea como la escribe el horario: el feed pone A0651 y el horario 651.
        linea, viaje, salida = R.line_key(m.group(1)), m.group(2), int(m.group(3))
        orden = texto(mvj, SIRI + 'MonitoredCall/' + SIRI + 'Order')
        if orden is None:
            orden = texto(mvj, SIRI + 'MonitoredCall/' + SIRI + 'VisitNumber')
        if orden is not None:
            orden = int(orden)
        leida = segundos_del_dia(texto(actividad, SIRI + 'RecordedAtTime'), dia)
        lat = lon = posicion = None
        lat_txt = texto(mvj, SIRI + 'VehicleLocation/' + SIRI + 'Latitude')
        lon_txt = texto(mvj, SIRI + 'VehicleLocation/' + SIRI + 'Longitude')
        if lat_txt is not None and lon_txt is not None:
            hora = texto(mvj, SIRI + 'LocationRecordedAtTime')
            if hora is None:
                hora = texto(actividad, SIRI + 'RecordedAtTime')
            posicion = segundos_del_dia(hora, dia)
            if posicion is not None:
                lat, lon = float(lat_txt), float(lon_txt)
        entrada = {'tripRef': ref, 'lineId': linea, 'departureSeconds': salida,
                   'vehicleRef': texto(mvj, SIRI + 'VehicleRef') or '',
                   'currentStopId': texto(mvj, SIRI + 'MonitoredCall/' + SIRI + 'StopPointRef'),
                   'order': orden, 'lat': lat, 'lon': lon, 'locationSeconds': posicion, 'recordedSeconds': leida}
        mapa.setdefault(linea + '|' + viaje, []).append(entrada)
    return mapa


# ----------------------------------------------------------------------------- horario
class Horario:
    """Los viajes del horario (la base SQLite que construye la app a partir del GTFS)."""

    def __init__(self, ruta):
        self.db = sqlite3.connect('file:%s?mode=ro' % ruta, uri=True)
        self.alias = {}
        self.viajes = {}

    def viajes_de(self, refs):
        faltan = [r for r in set(refs) if r not in self.alias]
        for i in range(0, len(faltan), 500):
            trozo = faltan[i:i + 500]
            marcas = ','.join('?' * len(trozo))
            for trip, viaje in self.db.execute('SELECT trip_id, service_journey_id FROM trip_aliases WHERE trip_id IN (%s)' % marcas, trozo):
                self.alias[trip] = viaje
            for r in trozo:
                self.alias.setdefault(r, None)
        return {r: self.alias[r] for r in refs}

    def viaje(self, id_viaje):
        """El viaje como lo espera referencia.Matcher: paradas con horas, coordenadas y metros, y el trazado."""
        if id_viaje in self.viajes:
            return self.viajes[id_viaje]
        cabecera = self.db.execute('SELECT line_id, trip_number, first_departure_seconds, shape_id FROM service_journeys WHERE id = ?', (id_viaje,)).fetchone()
        filas = self.db.execute('SELECT p.seq_order, p.stop_id, p.arrival_seconds, p.departure_seconds, p.dist_m, s.lat, s.lon '
                                'FROM passing_times p JOIN stops s ON s.id = p.stop_id WHERE p.service_journey_id = ? '
                                'ORDER BY p.seq_order', (id_viaje,)).fetchall()
        paradas = []
        for seq, parada, llegada, salida, metros, lat, lon in filas:
            if llegada is None:
                llegada = salida
            if salida is None:
                salida = llegada
            paradas.append({'seq': seq, 'id': parada, 'arr': llegada, 'dep': salida, 'dist': metros, 'lat': lat, 'lon': lon})
        trazado = None
        if cabecera is not None and cabecera[3]:
            fila = self.db.execute('SELECT points FROM shapes WHERE id = ?', (cabecera[3],)).fetchone()
            if fila is not None:
                trazado = [tuple(p) for p in json.loads(fila[0])]
        viaje = None
        if cabecera is not None and paradas:
            viaje = {'line': cabecera[0], 'trip': cabecera[1], 'stops': paradas, 'shape': trazado}
        self.viajes[id_viaje] = viaje
        return viaje


# ----------------------------------------------------------------------------- verdad de referencia
def paso_real(por_vehiculo, instantes, vehiculo, clave, desde, seq):
    """Instante en que el autobús pasa la parada seq: a medio camino entre la última instantánea en la que aún no la
    había pasado y la primera en la que ya sí, sin cambiar de viaje. None si deja de verse antes."""
    for siguiente in range(desde + 1, len(instantes)):
        visto = por_vehiculo.get(vehiculo, {}).get(siguiente)
        if visto is None:
            return None
        clave_siguiente, entrada = visto
        if clave_siguiente != clave:
            return None
        if entrada.get('order') is not None and entrada['order'] > seq:
            return (instantes[siguiente] + instantes[siguiente - 1]) / 2
    return None


def horizonte_de(segundos):
    for desde, hasta, nombre in HORIZONTES:
        if desde <= segundos < hasta:
            return nombre
    return None


def cubo(error):
    return str(max(-CUBO_MAXIMO, min(CUBO_MAXIMO, math.floor(error / CUBO_SEGUNDOS))))


def tramos_sin_aprender(paradas, seq, orden, tramos, franja):
    faltan = 0
    for i in range(len(paradas) - 1):
        desde = paradas[i]['seq']
        if desde >= seq or desde < orden - 1:
            continue
        if R.segment_seconds(tramos, paradas[i]['id'], paradas[i + 1]['id'], franja) is None:
            faltan += 1
    return faltan


# ----------------------------------------------------------------------------- evaluación
def evaluar(ficheros, n_predecir, horario, tramos, ritmo, viajes, modo, festivo):
    dia, captura = fecha_de(ficheros[0])
    instantaneas = []
    for fichero in ficheros:
        mapa = leer_instantanea(fichero, dia)
        ahora = 0
        for entradas in mapa.values():
            for e in entradas:
                if e['locationSeconds'] is not None:
                    ahora = max(ahora, e['locationSeconds'])
        if modo == 'sin-gps':
            for entradas in mapa.values():
                for e in entradas:
                    e['lat'] = e['lon'] = e['locationSeconds'] = None
        instantaneas.append((ahora, mapa))
    instantes = [ahora for ahora, _ in instantaneas]

    por_vehiculo = {}
    for i, (_, mapa) in enumerate(instantaneas):
        for clave, entradas in mapa.items():
            for e in entradas:
                por_vehiculo.setdefault(e['vehicleRef'], {})[i] = (clave, e)

    histogramas = {}
    for i, (ahora, mapa) in enumerate(instantaneas[:n_predecir]):
        refs = [e['tripRef'] for entradas in mapa.values() for e in entradas]
        alias = horario.viajes_de(refs)
        # El emparejador guarda, para cada viaje, la primera entrada del feed que es suya.
        primera = {}
        for entradas in mapa.values():
            for e in entradas:
                viaje = alias.get(e['tripRef'])
                if viaje is not None and viaje not in primera:
                    primera[viaje] = e
        franja = R.band_for(dia, ahora)
        for clave, entradas in mapa.items():
            for e in entradas:
                id_viaje = alias.get(e['tripRef'])
                if id_viaje is None or e['order'] is None:
                    continue
                viaje = horario.viaje(id_viaje)
                if viaje is None:
                    continue
                vivo = primera.get(id_viaje)
                if modo == 'sin-feed':
                    vivo = None
                predictor = R.Matcher(viaje, vivo, ahora, dia, tramos, ritmo, viajes, festivo)
                propio = R.Matcher(viaje, e, ahora, dia, tramos, ritmo, viajes, festivo)
                for parada in viaje['stops']:
                    seq = parada['seq']
                    if seq < e['order'] or seq > e['order'] + PARADAS_POR_DELANTE:
                        continue
                    real = paso_real(por_vehiculo, instantes, e['vehicleRef'], clave, i, seq)
                    if real is None:
                        continue
                    horizonte = horizonte_de(real - ahora)
                    if horizonte is None:
                        continue
                    salida = predictor.enrich(parada['arr'], seq)
                    capa = 3
                    if modo != 'sin-feed' and propio.position() is not None:
                        capa = 1
                    elif modo != 'sin-feed' and (propio.position() is not None or propio.registration() is not None):
                        capa = 2
                    sin_aprender = None
                    if capa == 1:
                        sin_aprender = min(tramos_sin_aprender(viaje['stops'], seq, e['order'], tramos, franja), 2)
                    llave = (capa, salida['status'], horizonte, franja, sin_aprender)
                    h = histogramas.setdefault(llave, {'n': 0, 'app': {}, 'horario': {}})
                    h['n'] += 1
                    b_app, b_hor = cubo(salida['eta'] - real), cubo(parada['arr'] - real)
                    h['app'][b_app] = h['app'].get(b_app, 0) + 1
                    h['horario'][b_hor] = h['horario'].get(b_hor, 0) + 1
    tipo_dia = 'laborable'
    if datetime.date.fromisoformat(dia).isoweekday() >= 6:
        tipo_dia = 'fin_semana'
    filas = []
    for (capa, estado, horizonte, franja, sin_aprender), h in sorted(histogramas.items(), key=lambda kv: str(kv[0])):
        filas.append({'formato': 'histograma-v1', 'captura': captura, 'fecha': dia, 'tipo_dia': tipo_dia,
                      'motor': 'referencia-py', 'instantaneas': n_predecir, 'modo': modo, 'capa': capa, 'estado': estado,
                      'horizonte': horizonte, 'franja': franja, 'tramos_sin_aprender': sin_aprender, 'n': h['n'],
                      'app': dict(sorted(h['app'].items(), key=lambda kv: int(kv[0]))),
                      'horario': dict(sorted(h['horario'].items(), key=lambda kv: int(kv[0])))})
    return filas


# ----------------------------------------------------------------------------- resumen
def dentro(histograma, segundos):
    """Fracción de errores dentro de ±segundos: los cubos de 15 s enteros que caben en el intervalo."""
    n = sum(histograma.values())
    if n == 0:
        return None
    lo, hi = -segundos // CUBO_SEGUNDOS, segundos // CUBO_SEGUNDOS - 1
    return sum(v for k, v in histograma.items() if lo <= int(k) <= hi) / n


def resumen(filas):
    juntos = {}
    for f in filas:
        for fuente in ('app', 'horario'):
            destino = juntos.setdefault((f['horizonte'], fuente), {})
            for k, v in f[fuente].items():
                destino[k] = destino.get(k, 0) + v
    lineas = []
    for _, _, horizonte in HORIZONTES:
        for fuente in ('app', 'horario'):
            h = juntos.get((horizonte, fuente), {})
            n = sum(h.values())
            if n == 0:
                continue
            partes = ['%s ±%d min %3.0f %%' % ('', s // 60, 100 * dentro(h, s)) for s in (60, 120, 180)]
            lineas.append('%-7s llega en %5s min: n=%6d |%s' % (fuente, horizonte, n, ' |'.join(partes)))
    return '\n'.join(lineas)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--capturas', required=True)
    p.add_argument('--seguimiento')
    p.add_argument('--base', required=True)
    p.add_argument('--tablas', required=True)
    p.add_argument('--modo', default='normal', choices=['normal', 'sin-gps', 'sin-feed'])
    p.add_argument('--jsonl')
    p.add_argument('--festivo', action='store_true', help='el día de las capturas es festivo entre semana')
    a = p.parse_args()
    ficheros = capturas_de(a.capturas)
    if not ficheros:
        sys.exit('No hay capturas (vm_*.xml) en ' + a.capturas)
    n_predecir = len(ficheros)
    if a.seguimiento:
        ficheros += capturas_de(a.seguimiento)
    tramos = json.load(open(os.path.join(a.tablas, 'segment-times.json'), encoding='utf-8'))
    ritmo = json.load(open(os.path.join(a.tablas, 'pace-factors.json'), encoding='utf-8'))
    viajes = json.load(open(os.path.join(a.tablas, 'trip-offsets.json'), encoding='utf-8'))
    filas = evaluar(ficheros, n_predecir, Horario(a.base), tramos, ritmo, viajes, a.modo, a.festivo)
    print(resumen(filas))
    if a.jsonl:
        with open(a.jsonl, 'a', encoding='utf-8') as f:
            for fila in filas:
                f.write(json.dumps(fila, ensure_ascii=False) + '\n')
        print('%d filas de histograma añadidas a %s' % (len(filas), a.jsonl), file=sys.stderr)


if __name__ == '__main__':
    main()
