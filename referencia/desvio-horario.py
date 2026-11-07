"""Cifras de la sección «El horario publicado se desvía en los dos sentidos» de la memoria: frecuencia de las líneas y desvío entre el paso real y la hora publicada.

Uso:
    python3 desvio-horario.py <bizkaibus.sqlite> <segment-samples.jsonl> [fecha=2026-10-28]

- Frecuencia: para la fecha dada, intervalo mediano entre salidas consecutivas de la misma línea en la misma parada,
  entre las 7:00 y las 21:00 (mismos calendarios que usa la app: máscara de días y excepciones).
- Desvío: para cada muestra de tramo, el paso real por la parada de origen (campo «at», reconstruido con el GPS)
  menos su hora publicada en el horario. Un valor por pista y parada; se descartan desvíos de más de 45 minutos.
"""
import collections
import datetime
import json
import sqlite3
import sys


def low_median(values):
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def share(values, condition):
    return 100 * sum(1 for value in values if condition(value)) / len(values)


def bucket_name(low, high):
    if high < 10 ** 9:
        return f'{low}-{high} min'
    return f'{low}+ min'


def frequencies(db, date_iso):
    bit = 1 << (datetime.date.fromisoformat(date_iso).isoweekday() - 1)
    rows = db.execute('''
        SELECT sj.line_id, pt.stop_id, pt.departure_seconds
        FROM passing_times pt
        JOIN service_journeys sj ON sj.id = pt.service_journey_id
        JOIN service_calendars sc ON sc.id = sj.calendar_id
        WHERE sc.id != 'PRUEBA'
          AND ((sc.weekday_mask & ?) != 0 OR EXISTS (SELECT 1 FROM service_calendar_exceptions e
               WHERE e.calendar_id = sc.id AND e.date = ? AND e.available = 1))
          AND NOT EXISTS (SELECT 1 FROM service_calendar_exceptions e
               WHERE e.calendar_id = sc.id AND e.date = ? AND e.available = 0)
          AND EXISTS (SELECT 1 FROM passing_times p2
               WHERE p2.service_journey_id = pt.service_journey_id AND p2.seq_order > pt.seq_order)
    ''', (bit, date_iso, date_iso)).fetchall()
    by_pair = collections.defaultdict(set)
    for line, stop, seconds in rows:
        if 7 * 3600 <= seconds < 21 * 3600:
            by_pair[(line, stop)].add(seconds)
    medians = []
    for times in by_pair.values():
        times = sorted(times)
        gaps = [(b - a) / 60 for a, b in zip(times, times[1:])]
        if gaps:
            medians.append(low_median(gaps))
    print(f'Frecuencia el {date_iso}: {len(medians)} combinaciones de línea y parada')
    print(f'  intervalo mediano {low_median(medians):.0f} min; >= 60 min {share(medians, lambda m: m >= 60):.0f} %;'
          f' >= 30 min {share(medians, lambda m: m >= 30):.0f} %; <= 15 min {share(medians, lambda m: m <= 15):.0f} %')


def deviations(db, samples_path):
    stops_by_journey = collections.defaultdict(list)
    for journey, seq, stop, arrival in db.execute(
            'SELECT service_journey_id, seq_order, stop_id, arrival_seconds FROM passing_times'):
        stops_by_journey[journey].append((seq, str(stop), arrival))
    for stops in stops_by_journey.values():
        stops.sort()

    seen = set()
    rows = []
    discarded = 0
    for line in open(samples_path, encoding='utf-8'):
        if not line.strip():
            continue
        sample = json.loads(line)
        journey = sample['track'].split('|', 2)[2]
        stops = stops_by_journey.get(journey)
        if not stops:
            continue
        index = next((i for i in range(len(stops) - 1)
                      if stops[i][1] == sample['from'] and stops[i + 1][1] == sample['to']), None)
        if index is None or (sample['track'], index) in seen:
            continue
        seen.add((sample['track'], index))
        deviation = sample['at'] - stops[index][2]
        if abs(deviation) > 2700:
            discarded += 1
            continue
        rows.append((deviation, (stops[index][2] - stops[0][2]) / 60))

    print(f'Desvío paso real - hora publicada: {len(rows)} pasos ({discarded} descartados por más de 45 min)')
    buckets = [(0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 10 ** 9)]
    groups = [(bucket_name(low, high), [d for d, m in rows if low <= m < high])
              for low, high in buckets]
    groups.append(('todos', [d for d, _ in rows]))
    for name, values in groups:
        print(f'  {name:10s} n={len(values):7d}  mediana {low_median(values) / 60:+6.1f} min'
              f'  >2 min antes {share(values, lambda d: d < -120):5.1f} %'
              f'  >5 min después {share(values, lambda d: d > 300):5.1f} %'
              f'  ±2 min {share(values, lambda d: abs(d) <= 120):5.1f} %')
    waits = [d + 120 for d, _ in rows if d >= -120]
    print(f'  llegando 2 min antes y sin perderlo: espera mediana {low_median(waits) / 60:.1f} min,'
          f' p90 {sorted(waits)[int(0.9 * (len(waits) - 1))] / 60:.1f} min')


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    db = sqlite3.connect(sys.argv[1])
    date_iso = '2026-10-28'
    if len(sys.argv) > 3:
        date_iso = sys.argv[3]
    frequencies(db, date_iso)
    deviations(db, sys.argv[2])


if __name__ == '__main__':
    main()
