"""Implementación de referencia del motor de llegadas de Bizkaibus+, escrita solo a partir de la especificación
de la tesis (no del código PHP). Se valida contra los vectores de prueba generados con el código de producción.

Convenciones que hay que respetar al portar a otro lenguaje:
  * Tiempos en segundos desde la medianoche de Europe/Madrid del día de servicio (pueden pasar de 86 400).
  * round() es el redondeo de PHP: mitades hacia fuera del cero (no el «redondeo del banquero» de Python).
  * Las medianas son la mediana BAJA: x_(floor(p*(n-1))) sobre los valores ordenados.
"""
import datetime
import math
import re
import zlib
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------------------- constantes
MADRID = ZoneInfo('Europe/Madrid')
METERS_PER_DEGREE = 111320.0
MAX_LOCATION_AGE = 600            # s: antigüedad máxima del dato del bus
NOT_STARTED_GRACE = 60            # s: el viaje cuenta como empezado 60 s antes de su salida
MAX_WAIT_AT_ORIGIN = 3600         # s: el bus que espera en la primera parada se sitúa hasta 1 h antes de salir
SEGMENTS_BEHIND, SEGMENTS_AHEAD = 3, 2
MAX_FROM_SHAPE = 50.0             # m: pasillo con trazado
MAX_FROM_ROUTE, MAX_FROM_ROUTE_RATIO = 150.0, 0.15   # m y fracción: pasillo sin trazado
BEYOND_SLACK, AMBIGUITY = 100.0, 20.0                # m
REGISTRATION_SHARE = 0.5
REGISTRATION_MAX_SEGMENT = 1200   # s
CROSSCHECK_MAX_SEGMENT = 360      # s
MAX_GPS_VS_STOP = 360             # s
MAX_PLAUSIBLE_DELAY = 2700        # s
STALE_GRACE = 120                 # s
PASSED_DISTANCE = 150.0           # m: el GPS, más lejos de la parada, la da por pasada aunque el feed no lo diga
ARRIVING_MAX = 180                # s: en «0 min» sin confirmar el paso antes de «puede que ya haya pasado»
SCHEDULE_ORIGIN_OFFSET = 60       # s
WRONG_SCHEDULE_GAP = WRONG_SCHEDULE_PASSED = 600     # s
WRONG_SCHEDULE_LEARNED_SHARE = 0.8
K_MIN, K_MAX = 0.6, 1.2
RATIO_MIN, RATIO_MAX = 0.3, 1.5
LENGTH_CUTS = [300, 600, 1000, 1500, 3000]
BANDS = [(0, 6, 'madrugada'), (6, 9, 'punta_manana'), (9, 13, 'manana'), (13, 16, 'mediodia'),
         (16, 20, 'punta_tarde'), (20, 24, 'noche')]
MIN_TRACKS_PER_SEGMENT = 2
SEGMENT_BAND_PRIOR_TRACKS = 5
SHRINKAGE_TRACKS = 10
MAX_SAMPLES_PER_TRACK = 30
MAX_GAP_BETWEEN_SNAPSHOTS = 300
TRIP_PARTS = 3                    # tercios del recorrido en la corrección por viaje
TRIP_OFFSET_RANK = 0.4            # percentil de los desvíos que toma la corrección por viaje (no la media)
TRIP_OFFSET_CLIP = 900            # s: recorte de cada desvío al calibrar la corrección por viaje
TRIP_OFFSET_LINE_PRIOR = 20       # pasos: peso de la franja en la corrección de la línea
TRIP_OFFSET_RANKS = [0.3, 0.35, 0.4, 0.45, 0.5]   # percentiles entre los que elige la recalibración
TRIP_OFFSET_TRIP_PRIOR_DAYS = 1   # días: peso de la línea en la corrección del viaje


# ----------------------------------------------------------------------------- utilidades
def php_round(x):
    """round() de PHP con 0 decimales: las mitades se alejan del cero."""
    if x >= 0:
        return math.floor(x + 0.5)
    return -math.floor(-x + 0.5)


def percentile(values, p):
    ordered = sorted(values)
    return float(ordered[int(math.floor(p * (len(ordered) - 1)))])


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ----------------------------------------------------------------------------- franja y factores
def band_for(date_iso, seconds):
    weekday = datetime.date.fromisoformat(date_iso).isoweekday()   # 1 = lunes ... 7 = domingo
    day_type = 'laborable'
    if weekday >= 6:
        day_type = 'fin_semana'
    hour = (seconds // 3600) % 24
    for lo, hi, name in BANDS:
        if lo <= hour < hi:
            return day_type + '.' + name
    return day_type + '.noche'


def line_key(line):
    """El número de línea sin ceros a la izquierda: el feed escribe 0651 y el horario, 651."""
    if line is None:
        return None
    key = str(line).lstrip('0')
    if key == '':
        return '0'
    return key


def by_line(table):
    """Una tabla por línea con los números de línea sin ceros a la izquierda; si dos coinciden, queda la primera."""
    out = {}
    for line, values in (table or {}).items():
        out.setdefault(line_key(line), values)
    return out


def pace_factor(pace, line, date_iso, seconds):
    band = band_for(date_iso, seconds)
    k = 1.0
    lines = by_line(pace.get('lines', {}))
    key = line_key(line)
    if key is not None and band in lines.get(key, {}):
        k = lines[key][band]
    elif band in pace.get('global', {}):
        k = pace['global'][band]
    return clamp(float(k), K_MIN, K_MAX)


# ----------------------------------------------------------------------------- tiempos por tramo
def length_bucket(meters):
    for i, cut in enumerate(LENGTH_CUTS):
        if meters < cut:
            return i
    return len(LENGTH_CUTS)


def segment_seconds(segments, from_id, to_id, band):
    seg = segments.get('segments', {}).get(from_id + '>' + to_id)
    if seg is None:
        return None
    if band in seg:
        return float(seg[band])
    if 'all' in seg:
        return float(seg['all'])
    return None


def length_ratios(segments):
    """lengthRatios como diccionario {'0': {...}, ...}. PHP lo escribe como lista si tiene todos los cubos 0..5."""
    ratios = segments.get('lengthRatios') or {}
    if isinstance(ratios, list):
        return {str(i): r for i, r in enumerate(ratios)}
    return ratios


def fallback_seconds(segments, scheduled, meters, band):
    ratios = length_ratios(segments)
    if not ratios or meters is None or meters <= 0:
        return None
    bucket = ratios.get(str(length_bucket(meters)))
    if bucket is None:
        return None
    ratio = bucket.get(band, bucket.get('all'))
    if ratio is None:
        return None
    return clamp(float(ratio), RATIO_MIN, RATIO_MAX) * scheduled


def expected_seconds(stops, segments, t_from, t_target, band, k):
    """Tiempo esperado para ir del instante programado t_from al t_target, tramo a tramo."""
    if not segments.get('segments'):
        return k * (t_target - t_from)
    total = 0.0
    for i in range(len(stops) - 1):
        leave, reach = stops[i]['arr'], stops[i + 1]['arr']
        if reach <= t_from:
            continue
        if leave >= t_target:
            break
        scheduled = reach - leave
        tau = segment_seconds(segments, stops[i]['id'], stops[i + 1]['id'], band)
        if tau is None:
            meters = None
            if stops[i]['dist'] is not None and stops[i + 1]['dist'] is not None:
                meters = stops[i + 1]['dist'] - stops[i]['dist']
            tau = fallback_seconds(segments, float(scheduled), meters, band)
            if tau is None:
                tau = k * scheduled
        share = 1.0
        if scheduled > 0:
            share = (min(reach, t_target) - max(leave, t_from)) / scheduled
        total += max(0.0, share) * tau
    return total


def learned_share(stops, segments, t_from, t_target, band):
    total = learned = 0
    for i in range(len(stops) - 1):
        leave, reach = stops[i]['arr'], stops[i + 1]['arr']
        if reach <= t_from:
            continue
        if leave >= t_target:
            break
        total += reach - leave
        if segment_seconds(segments, stops[i]['id'], stops[i + 1]['id'], band) is not None:
            learned += reach - leave
    if total <= 0:
        return 0.0
    return learned / total


# ----------------------------------------------------------------------------- geometría
# ----------------------------------------------------------------------------- corrección por viaje
def trip_key(line, first_stop, last_stop, departure, count):
    return '%s|%s|%s|%d|%d' % (line_key(line), first_stop, last_stop, departure, count)


def same_line(key):
    """La clave de un viaje con su número de línea sin ceros a la izquierda."""
    parts = key.split('|', 1)
    parts[0] = line_key(parts[0])
    return '|'.join(parts)


def trip_part(index, count):
    if count <= 0:
        return 0
    return clamp((TRIP_PARTS * index) // count, 0, TRIP_PARTS - 1)


def day_type(date_iso):
    return band_for(date_iso, 0).split('.')[0]


def service_date(date_iso, holiday):
    """Día con el que calcula la capa 3: en un festivo entre semana, el domingo de esa semana."""
    if not holiday:
        return date_iso
    day = datetime.date.fromisoformat(date_iso)
    return (day + datetime.timedelta(days=7 - day.isoweekday())).isoformat()


def trip_offset(table, key, line, date_iso, departure, index, count):
    """Segundos que se suman a la capa 3: los del viaje en su tercio; si no, los de su línea y franja; si no, la franja."""
    trips = {}
    for k, v in table.get('trips', {}).items():
        trips.setdefault(same_line(k), v)
    parts = trips.get(same_line(key), {}).get(day_type(date_iso))
    if parts is not None:
        return float(parts[trip_part(index, count)])
    band = band_for(date_iso, departure)
    line_bands = by_line(table.get('lines', {})).get(line_key(line), {})
    if band in line_bands:
        return float(line_bands[band])
    if band in table.get('global', {}):
        return float(table['global'][band])
    return 0.0


def project_onto_segment(lat, lon, a, b):
    m_lon = math.cos(math.radians(lat)) * METERS_PER_DEGREE
    ax, ay = (a['lon'] - lon) * m_lon, (a['lat'] - lat) * METERS_PER_DEGREE
    bx, by = (b['lon'] - lon) * m_lon, (b['lat'] - lat) * METERS_PER_DEGREE
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    f = 0.0
    if l2 > 0:
        f = clamp(-(ax * dx + ay * dy) / l2, 0.0, 1.0)
    px, py = ax + f * dx, ay + f * dy
    return f, math.hypot(px, py), math.sqrt(l2)


def position(journey, live, now):
    """Capa 1: dónde pone el horario al bus (T_pos). None si el GPS no sirve."""
    stops, shape = journey['stops'], journey.get('shape')
    if live.get('lat') is None or live.get('lon') is None or live.get('locationSeconds') is None or live.get('order') is None:
        return None
    t_gps = live['locationSeconds']
    if now - t_gps > MAX_LOCATION_AGE or len(stops) < 2:
        return None
    if t_gps < stops[0]['dep'] - NOT_STARTED_GRACE:
        return waiting_at_origin(live, stops[0], t_gps)
    nxt = next((i for i, s in enumerate(stops) if s['seq'] == live['order']), None)
    if nxt is None:
        return None
    first, last = max(0, nxt - SEGMENTS_BEHIND), min(len(stops) - 2, nxt + SEGMENTS_AHEAD)
    if shape and all(stops[i]['dist'] is not None for i in range(first, last + 2)):
        lo, hi = stops[first]['dist'], stops[last + 1]['dist']
        limit = stops[nxt]['dist'] + BEYOND_SLACK
        best_exp = best_beyond = None
        for (alat, alon, ad), (blat, blon, bd) in zip(shape, shape[1:]):
            if bd < lo or ad > hi:
                continue
            f, d, _ = project_onto_segment(live['lat'], live['lon'], {'lat': alat, 'lon': alon}, {'lat': blat, 'lon': blon})
            along = ad + f * (bd - ad)
            if along <= limit:
                if best_exp is None or d < best_exp[0]:
                    best_exp = (d, along)
            elif best_beyond is None or d < best_beyond[0]:
                best_beyond = (d, along)
        best = best_exp
        if best_beyond is not None and (best is None or best_beyond[0] + AMBIGUITY < best[0]):
            best = best_beyond
        if best is None or best[0] > MAX_FROM_SHAPE:
            return None
        d, along = best
        along = clamp(along, lo, hi)
        for i in range(first, last + 1):
            s0, s1 = stops[i]['dist'], stops[i + 1]['dist']
            if along > s1 and i < last:
                continue
            f = 0.0
            if s1 > s0:
                f = clamp((along - s0) / (s1 - s0), 0.0, 1.0)
            sched = php_round(stops[i]['dep'] + f * (stops[i + 1]['arr'] - stops[i]['dep']))
            return {'scheduledSeconds': sched, 'locationSeconds': t_gps, 'offRouteMeters': d, 'method': 'shape'}
        return None
    best = None
    for i in range(first, last + 1):
        f, d, length = project_onto_segment(live['lat'], live['lon'], stops[i], stops[i + 1])
        if best is None or d < best[0]:
            allowed = max(MAX_FROM_ROUTE, length * MAX_FROM_ROUTE_RATIO)
            best = (d, allowed, stops[i]['dep'] + f * (stops[i + 1]['arr'] - stops[i]['dep']))
    if best is None or best[0] > best[1]:
        return None
    return {'scheduledSeconds': php_round(best[2]), 'locationSeconds': t_gps, 'offRouteMeters': best[0], 'method': 'segment'}


def waiting_at_origin(live, first, t_gps):
    """Antes de su hora: el bus que espera en la primera parada (a 150 m o menos) ya se sitúa allí."""
    if first['dep'] - t_gps > MAX_WAIT_AT_ORIGIN:
        return None
    dx = (live['lon'] - first['lon']) * math.cos(math.radians(first['lat']))
    dy = live['lat'] - first['lat']
    meters = math.hypot(dx, dy) * METERS_PER_DEGREE
    if meters > MAX_FROM_ROUTE:
        return None
    return {'scheduledSeconds': min(first['arr'], first['dep']), 'locationSeconds': first['dep'],
            'offRouteMeters': meters, 'method': 'origin'}


DAY_SECONDS = 86400
MATCH_TOLERANCE = 180             # s: emparejado por línea y número de viaje cuando falta la referencia exacta
HOLD_SECONDS = 180                # s: un bus que falta en una lectura del feed se sigue usando con su último dato


# ----------------------------------------------------------------------------- el feed
def iso_duration_seconds(text):
    """«PT2M30S» son 150 s y «-PT45S», -45; lo que no tiene esa forma, 0."""
    m = re.match(r'^(-?)PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', text or '')
    if not m:
        return 0
    seconds = int(m.group(2) or 0) * 3600 + int(m.group(3) or 0) * 60 + int(m.group(4) or 0)
    return -seconds if m.group(1) == '-' else seconds


def seconds_of_day(text, day_iso):
    """Segundos desde la medianoche de Madrid de «day_iso»; None si la hora es de otro día o no se entiende."""
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=MADRID)
    local = moment.astimezone(MADRID)
    if local.date().isoformat() != day_iso:
        return None
    return local.hour * 3600 + local.minute * 60 + local.second


def parse_siri(xml_text, day_iso):
    """Las entradas del feed SIRI Vehicle Monitoring, agrupadas por «línea|número de viaje». La referencia del viaje
    (trp_A0651_737_ABC1_28500) da la línea (sin ceros: 651), el número de viaje y la salida del viaje en segundos."""
    def child(node, *path):
        for name in path:
            if node is None:
                return None
            node = next((c for c in node if c.tag.rsplit('}', 1)[-1] == name), None)
        return node

    def text(node, *path):
        found = child(node, *path)
        return None if found is None else (found.text or '')

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return {}
    out = {}
    delivery = child(root, 'ServiceDelivery', 'VehicleMonitoringDelivery')
    for activity in ([] if delivery is None else delivery):
        if activity.tag.rsplit('}', 1)[-1] != 'VehicleActivity':
            continue
        mvj = child(activity, 'MonitoredVehicleJourney')
        ref = text(mvj, 'VehicleJourneyRef')
        if ref is None:
            continue
        m = re.match(r'^trp_[A-Za-z]+(\d+)_(\d+)_[A-Za-z0-9]+_(\d+)', ref)
        if not m:
            continue
        line, trip_number, departure = line_key(m.group(1)), m.group(2), int(m.group(3))
        order = text(mvj, 'MonitoredCall', 'Order')
        if order is None:
            order = text(mvj, 'MonitoredCall', 'VisitNumber')
        recorded = seconds_of_day(text(activity, 'RecordedAtTime'), day_iso) if text(activity, 'RecordedAtTime') is not None else None
        lat = lon = location = None
        if text(mvj, 'VehicleLocation', 'Latitude') is not None and text(mvj, 'VehicleLocation', 'Longitude') is not None:
            when = text(mvj, 'LocationRecordedAtTime')
            if when is None:
                when = text(activity, 'RecordedAtTime') or ''
            location = seconds_of_day(when, day_iso)
            if location is not None:
                lat, lon = float(text(mvj, 'VehicleLocation', 'Latitude')), float(text(mvj, 'VehicleLocation', 'Longitude'))
        delay = text(mvj, 'Delay')
        out.setdefault(line + '|' + trip_number, []).append({
            'tripRef': ref, 'lineId': line, 'departureSeconds': departure,
            'delaySeconds': iso_duration_seconds('PT0S' if delay is None else delay),
            'vehicleRef': text(mvj, 'VehicleRef') or '', 'currentStopId': text(mvj, 'MonitoredCall', 'StopPointRef'),
            'order': None if order is None else int(order), 'lat': lat, 'lon': lon,
            'locationSeconds': location, 'recordedSeconds': recorded})
    return out


def has_time(entry):
    return entry.get('locationSeconds') is not None or entry.get('recordedSeconds') is not None


def days_ago(entry, now):
    """1 si el bus va en un viaje de ayer (su salida queda más de 12 h por delante de ahora), 0 si es de hoy."""
    return int((entry.get('departureSeconds') or 0) - now > DAY_SECONDS / 2)


def vehicles_of_day(vm_map, now, days):
    """Los buses de viajes de hace «days» días, con sus horas contadas desde la medianoche de ese día (para los de
    ayer, las 00:30 son las 24:30). Un dato sin hora de hoy no cuenta."""
    out = {}
    for key, entries in vm_map.items():
        for entry in entries:
            if days_ago(entry, now) != days or not has_time(entry):
                continue
            entry = dict(entry)
            for field in ('locationSeconds', 'recordedSeconds'):
                if entry.get(field) is not None:
                    entry[field] += days * DAY_SECONDS
            out.setdefault(key, []).append(entry)
    return out


def with_held(vm_map, previous, now):
    """El feed nuevo más los buses de la lectura anterior que faltan en él: el último dato de cada uno se sigue usando
    hasta HOLD_SECONDS si su viaje no lo lleva ya otro bus y el bus no aparece en otro viaje."""
    out = {key: list(entries) for key, entries in vm_map.items()}
    present = {str(e.get('vehicleRef') or '') for entries in vm_map.values() for e in entries}
    for key, entries in previous.items():
        if key in vm_map or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('vehicleRef') in (None, '', '0', 0) or str(entry['vehicleRef']) in present:
                continue
            seen = entry.get('locationSeconds')
            if seen is None:
                seen = entry.get('recordedSeconds')
            if seen is None or not 0 <= now - seen <= HOLD_SECONDS:
                continue
            held = dict(entry)
            held.setdefault('held', True)
            out.setdefault(key, []).append(held)
            present.add(str(entry['vehicleRef']))
    return out


def lookup(vm_map, aliases, line, trip_number, first_departure, journey_id=None):
    """La entrada del feed de un viaje del horario: la de su referencia exacta (aliases: referencia del feed -> viaje);
    si no, la de la misma línea y número de viaje con la salida más cercana a MATCH_TOLERANCE o menos, sin reutilizar
    una entrada emparejada exactamente con otro viaje."""
    by_journey = {}
    for entries in vm_map.values():
        for entry in entries:
            exact = aliases.get(entry.get('tripRef'))
            if exact is not None:
                by_journey.setdefault(exact, entry)
    if journey_id is not None and journey_id in by_journey:
        return by_journey[journey_id]
    best, best_diff = None, None
    for entry in vm_map.get('%s|%s' % (line, trip_number), []):
        if journey_id is not None and aliases.get(entry.get('tripRef')) is not None:
            continue
        diff = abs(entry['departureSeconds'] - first_departure)
        if diff <= MATCH_TOLERANCE and (best_diff is None or diff < best_diff):
            best, best_diff = entry, diff
    return best


# ----------------------------------------------------------------------------- registro de pasos
def passage_fields(vm_map):
    """Lo que se guarda cada minuto por referencia de viaje: «orden de la próxima parada:hora del dato»."""
    out = {}
    for entries in vm_map.values():
        for entry in entries:
            if not entry.get('tripRef') or entry.get('order') is None:
                continue
            seconds = entry.get('recordedSeconds')
            if seconds is None:
                seconds = entry.get('locationSeconds')
            if seconds is None:
                continue
            out[str(entry['tripRef'])] = '%d:%d' % (int(entry['order']), int(seconds))
    return out


def decode_passage(value):
    m = re.fullmatch(r'(\d+):(\d+)', value) if isinstance(value, str) else None
    return None if m is None else {'order': int(m.group(1)), 'seconds': int(m.group(2))}


def passage_stop_fields(vm_map):
    """El historial por parada: «referencia#orden» -> hora."""
    out = {}
    for ref, value in passage_fields(vm_map).items():
        p = decode_passage(value)
        out['%s#%d' % (ref, p['order'])] = str(p['seconds'])
    return out


def merge_passages(journey_of_field, values):
    """Por viaje del horario, el paso de orden mayor de todas sus referencias."""
    out = {}
    for i, value in enumerate(values):
        p = decode_passage(value)
        if p is None or i >= len(journey_of_field):
            continue
        journey = journey_of_field[i]
        if journey not in out or p['order'] > out[journey]['order']:
            out[journey] = p
    return out


def stops_from_hash(fields):
    trips = {}
    for field, seconds in fields.items():
        m = re.fullmatch(r'(.+)#(\d+)', str(field))
        if not m or not str(seconds).isdigit():
            continue
        trips.setdefault(m.group(1), {})[int(m.group(2))] = int(seconds)
    return {ref: dict(sorted(stops.items())) for ref, stops in sorted(trips.items())}


# ----------------------------------------------------------------------------- el emparejador
class Matcher:
    def __init__(self, journey, live, now, date_iso, segments, pace, trips=None, holiday=False, passage=None):
        # passage: el paso registrado del viaje ({'order', 'seconds'}, merge_passages), que el motor solo consulta
        # cuando ningún bus del feed lleva exactamente ese viaje.
        self.passage = passage
        self.j, self.live, self.now, self.date = journey, live, now, date_iso
        self.seg, self.pace = segments, pace
        self.trips = trips
        self.service = service_date(date_iso, holiday)
        self.distrusted = False
        self._pos = None
        self._pos_done = False

    def position(self):
        if not self._pos_done:
            self._pos_done = True
            self._pos = None
            if self.live:
                self._pos = position(self.j, self.live, self.now)
            if self._pos is not None:
                reg = self.registration()
                gps_delay = self._pos['locationSeconds'] - self._pos['scheduledSeconds']
                if reg is not None and reg['gap'] <= CROSSCHECK_MAX_SEGMENT and abs(gps_delay - reg['delay']) > MAX_GPS_VS_STOP:
                    self.distrusted = True
                    self._pos = None
        return self._pos

    def registration(self):
        live, stops = self.live, self.j['stops']
        if not live or live.get('order') is None or self.distrusted:
            return None
        order = live['order']
        if order < 2:
            return None
        ref = live.get('locationSeconds')
        if ref is None:
            ref = live.get('recordedSeconds')
        if ref is None or self.now - ref > MAX_LOCATION_AGE:
            return None
        if not stops or ref < stops[0]['dep'] - NOT_STARTED_GRACE:
            return None
        by_seq = {s['seq']: s for s in stops}
        if order not in by_seq or order - 1 not in by_seq:
            return None
        prev, nxt = by_seq[order - 1]['arr'], by_seq[order]['arr']
        if nxt - prev > REGISTRATION_MAX_SEGMENT:
            return None
        band = band_for(self.date, ref)
        k = pace_factor(self.pace, live.get('lineId'), self.date, ref)
        to_next = php_round(REGISTRATION_SHARE * expected_seconds(stops, self.seg, prev, nxt, band, k))
        return {'order': order, 'ref': ref, 'previous': prev, 'next': nxt, 'toNext': to_next,
                'delay': ref + to_next - nxt, 'gap': nxt - prev}

    def registered_eta(self, target, target_seq):
        reg = self.registration()
        if reg is None or target_seq < reg['order']:
            return None
        after = 0.0
        if target > reg['next']:
            band = band_for(self.date, reg['ref'])
            k = pace_factor(self.pace, self.live.get('lineId'), self.date, reg['ref'])
            after = expected_seconds(self.j['stops'], self.seg, reg['next'], target, band, k)
        return php_round(reg['ref'] + reg['toNext'] + after)

    def origin_eta(self, target, target_seq):
        """Esperando en la primera parada, la llegada es la de la capa 3 (no ha recorrido nada todavía)."""
        stops = self.j['stops']
        if not self.seg.get('segments') or target <= stops[0]['dep']:
            return None
        return max(self.learned_arrival(target) + self.trip_offset(target_seq), self.now)

    def learned_arrival(self, target):
        stops = self.j['stops']
        first = stops[0]['dep']
        mid = (first + target) // 2
        band = band_for(self.service, mid)
        k = pace_factor(self.pace, self.j.get('line'), self.service, mid)
        return first + SCHEDULE_ORIGIN_OFFSET + php_round(expected_seconds(stops, self.seg, first - 1, target, band, k))

    def eta_for_stop(self, target, target_seq):
        pos = self.position()
        if pos is not None:
            if pos['method'] == 'origin':
                eta = self.origin_eta(target, target_seq)
                if eta is not None:
                    return eta, eta - target, True
            if target < pos['scheduledSeconds']:
                passed = pos['locationSeconds'] - (pos['scheduledSeconds'] - target)
                return passed, pos['locationSeconds'] - pos['scheduledSeconds'], True
            band = band_for(self.date, pos['locationSeconds'])
            k = pace_factor(self.pace, self.live.get('lineId'), self.date, pos['locationSeconds'])
            eta = php_round(pos['locationSeconds'] + expected_seconds(self.j['stops'], self.seg, pos['scheduledSeconds'], target, band, k))
            return eta, eta - target, True
        reg_eta = self.registered_eta(target, target_seq)
        if reg_eta is not None:
            return reg_eta, reg_eta - target, False
        return target, 0, False

    def passed_at(self, target, target_seq):
        pos = self.position()
        order = None
        if self.live:
            order = self.live.get('order')
        if pos is not None:
            if pos['method'] == 'origin':
                return None
            feed_past = order is not None and target_seq < order
            if target < pos['scheduledSeconds'] and (feed_past or self.meters_from_stop(target_seq) > PASSED_DISTANCE):
                return pos['locationSeconds'] - (pos['scheduledSeconds'] - target)
            if feed_past:
                return pos['locationSeconds']
            return None
        if order is not None and target_seq < order:
            reg = self.registration()
            if reg is not None:
                return reg['ref'] - max(0, reg['previous'] - target)
        return None

    def trip_offset(self, target_seq):
        stops = self.j['stops']
        indexes = [i for i, s in enumerate(stops) if s['seq'] == target_seq]
        if not self.trips or not indexes:
            return 0
        key = trip_key(self.j.get('line'), stops[0]['id'], stops[-1]['id'], stops[0]['dep'], len(stops))
        return php_round(trip_offset(self.trips, key, self.j.get('line'), self.service, stops[0]['dep'], indexes[0], len(stops)))

    def scheduled_fields(self, target, target_seq):
        if self.passage is not None and target_seq < self.passage['order']:
            return {'status': 'departed', 'eta': min(self.passage['seconds'], self.now), 'delay': 0}
        out = {'status': 'scheduled', 'eta': target, 'delay': 0}
        stops = self.j['stops']
        if not self.seg.get('segments'):
            return out
        first = stops[0]['dep']
        if target <= first:
            return out
        mid = (first + target) // 2
        band = band_for(self.service, mid)
        corrected = self.learned_arrival(target) + self.trip_offset(target_seq)
        if corrected >= self.now:
            return {'status': 'estimated', 'eta': corrected, 'delay': 0}
        if (corrected < self.now - WRONG_SCHEDULE_PASSED and target - corrected >= WRONG_SCHEDULE_GAP
                and learned_share(stops, self.seg, first - 1, target, band) >= WRONG_SCHEDULE_LEARNED_SHARE):
            out['status'] = 'likely_departed'
        return out

    def enrich(self, target, target_seq):
        live_ok = self.live is not None and (self.position() is not None or self.registration() is not None)
        if not live_ok:
            return self.scheduled_fields(target, target_seq)
        passed = self.passed_at(target, target_seq)
        if passed is not None:
            return {'status': 'departed', 'eta': min(passed, self.now), 'delay': 0}
        if self.position() is None and self.registered_eta(target, target_seq) is None:
            return self.scheduled_fields(target, target_seq)
        eta, delay, positioned = self.eta_for_stop(target, target_seq)
        if abs(delay) > MAX_PLAUSIBLE_DELAY:
            delay = None
        if eta < self.now - STALE_GRACE and not positioned:
            return self.scheduled_fields(target, target_seq)
        if not positioned:
            return {'status': 'estimated', 'eta': eta, 'delay': 0}
        if eta < self.now:
            status = 'live'
            if self.now - eta > ARRIVING_MAX:
                status = 'likely_departed'
            if delay is not None:
                delay = max(delay, self.now - target)
            return {'status': status, 'eta': self.now, 'delay': delay}
        return {'status': 'live', 'eta': eta, 'delay': delay}

    def current_delay(self):
        """Retraso del bus ahora: el de su posición; sin posición, el de la parada registrada; si no, 0."""
        if self.live is None:
            return 0
        pos = self.position()
        if pos is not None:
            return pos['locationSeconds'] - pos['scheduledSeconds']
        reg = self.registration()
        return 0 if reg is None else reg['delay']

    def display_delay(self):
        """Retraso que se muestra del bus: con posición, el que llevará en su próxima parada; si no, current_delay."""
        current = self.current_delay()
        if self.live is None or self.live.get('order') is None or self.position() is None:
            return current
        order = self.live['order']
        nxt = next((s['arr'] for s in self.j['stops'] if s['seq'] == order), None)
        if nxt is None:
            return current
        return self.eta_for_stop(nxt, order)[1]

    def meters_from_stop(self, target_seq):
        for s in self.j['stops']:
            if s['seq'] == target_seq and s.get('lat') is not None and s.get('lon') is not None:
                dx = (self.live['lon'] - s['lon']) * math.cos(math.radians(s['lat']))
                dy = self.live['lat'] - s['lat']
                return math.sqrt(dx * dx + dy * dy) * METERS_PER_DEGREE
        return math.inf


# ----------------------------------------------------------------------------- calibración
def fit_segments(samples):
    groups = {}
    for s in samples:
        g = groups.setdefault(s['from'] + '>' + s['to'], {'all': {}})
        g['all'][s['track']] = s['actual']
        g.setdefault(s['band'], {})[s['track']] = s['actual']
    out = {}
    for key, gr in groups.items():
        if len(gr['all']) < MIN_TRACKS_PER_SEGMENT:
            continue
        seg = {'n': len(gr['all'])}
        all_median = percentile(list(gr['all'].values()), 0.5)
        several = len(gr) > 2
        for name, values in gr.items():
            if name == 'all' and not several:
                continue
            if len(values) < MIN_TRACKS_PER_SEGMENT:
                continue
            v = percentile(list(values.values()), 0.5)
            if name != 'all':
                n = len(values)
                v = (v * n + all_median * SEGMENT_BAND_PRIOR_TRACKS) / (n + SEGMENT_BAND_PRIOR_TRACKS)
            seg[name] = php_round(v)
        if len(seg) > 1:
            out[key] = seg
    return dict(sorted(out.items()))


def fit_trip_offsets(residuals, rank=TRIP_OFFSET_RANK):
    """Tabla de la corrección por viaje a partir de los desvíos (hora real menos capa 3 sin corregir), con el
    percentil «rank» (0,4 de partida; la recalibración lo elige cada noche con choose_trip_offset_rank)."""
    by_band, by_line, by_day, trip_band = {}, {}, {}, {}
    for r in residuals:
        error = clamp(r['error'], -TRIP_OFFSET_CLIP, TRIP_OFFSET_CLIP)
        band = band_for(r['serviceDate'], r['departure'])
        kind = day_type(r['serviceDate'])
        part = trip_part(r['index'], r['count'])
        by_band.setdefault(band, []).append(error)
        by_line.setdefault(r['line'], {}).setdefault(band, []).append(error)
        by_day.setdefault(r['trip'], {}).setdefault(kind, {}).setdefault(part, {}).setdefault(r['date'], []).append(error)
        trip_band.setdefault(r['trip'], {})[kind] = (r['line'], band)
    overall = {band: percentile(v, rank) for band, v in by_band.items()}
    lines = {}
    for line, bands in by_line.items():
        lines[line] = {band: (percentile(v, rank) * len(v) + overall[band] * TRIP_OFFSET_LINE_PRIOR) / (len(v) + TRIP_OFFSET_LINE_PRIOR)
                       for band, v in bands.items()}
    trips = {}
    for trip, kinds in by_day.items():
        for kind, parts in kinds.items():
            line, band = trip_band[trip][kind]
            line_value = lines[line][band]
            values = [php_round(line_value)] * TRIP_PARTS
            for part, days in parts.items():
                day_values = [percentile(v, rank) for v in days.values()]
                values[part] = php_round((sum(day_values) + line_value * TRIP_OFFSET_TRIP_PRIOR_DAYS) / (len(day_values) + TRIP_OFFSET_TRIP_PRIOR_DAYS))
            trips.setdefault(trip, {})[kind] = values
    return {'trips': dict(sorted(trips.items())),
            'lines': {line: {band: php_round(v) for band, v in bands.items()} for line, bands in sorted(lines.items())},
            'global': {band: php_round(v) for band, v in sorted(overall.items())}}


def display_delay_minutes(seconds):
    """Minutos de retraso que se muestran; un retraso de más de 45 min no se muestra."""
    if seconds is None or abs(seconds) > MAX_PLAUSIBLE_DELAY:
        return None
    return php_round(seconds / 60)


def trip_offset_errors(residuals, table):
    """[error medio sin corregir, error medio corregido, % a ±2 min sin, % a ±2 min con] de unos desvíos."""
    before = after = 0.0
    within_before = within_after = 0
    for r in residuals:
        corrected = r['error'] - trip_offset(table, r['trip'], r['line'], r['serviceDate'], r['departure'], r['index'], r['count'])
        before += abs(r['error'])
        after += abs(corrected)
        within_before += abs(r['error']) <= 120
        within_after += abs(corrected) <= 120
    n = max(1, len(residuals))
    return [before / n, after / n, 100 * within_before / n, 100 * within_after / n]


def choose_trip_offset_rank(train, test, ranks=TRIP_OFFSET_RANKS):
    """El percentil que más acierta a ±2 min en los días de prueba aprendiendo con los anteriores; con empate, el de
    menos error medio; con empate en los dos, el primero de la lista. Devuelve también sus errores
    (trip_offset_errors): la tabla nueva solo se escribe si el error medio corregido es menor que el sin corregir."""
    chosen, best = ranks[0], None
    for rank in ranks:
        errors = trip_offset_errors(test, fit_trip_offsets(train, rank))
        if best is None or (errors[3], -errors[1]) > (best[3], -best[1]):
            chosen, best = rank, errors
    return chosen, best


def shrunk_factor(tracks):
    ratios = [sum(s['actualRemaining'] for s in t) / sum(s['scheduledRemaining'] for s in t) for t in tracks.values()]
    m = len(ratios)
    raw = percentile(ratios, 0.5)
    k = 1.0 + (raw - 1.0) * m / (m + SHRINKAGE_TRACKS)
    return php_round(clamp(k, K_MIN, K_MAX) * 1000) / 1000


def actual_passing_time(track, arrival):
    for a, b in zip(track, track[1:]):
        if b['sched'] <= a['sched'] or b['t'] - a['t'] > MAX_GAP_BETWEEN_SNAPSHOTS:
            continue
        if a['sched'] <= arrival <= b['sched']:
            return a['t'] + (arrival - a['sched']) / (b['sched'] - a['sched']) * (b['t'] - a['t'])
    return None


def thin(samples_of_one_track):
    n = len(samples_of_one_track)
    if n <= MAX_SAMPLES_PER_TRACK:
        return samples_of_one_track
    return [samples_of_one_track[(i * n) // MAX_SAMPLES_PER_TRACK] for i in range(MAX_SAMPLES_PER_TRACK)]


def fold(track):
    """Pliegue de la validación cruzada: crc32 (IEEE 802.3, sin signo) módulo 2."""
    return (zlib.crc32(track.encode('utf-8')) & 0xFFFFFFFF) % 2
