"""Datos de las figuras del artículo 2 (ficheros .dat para pgfplots) a partir de los pares de comparar.py.

Uso: python3 figuras.py <carpeta con pares-AAAAMMDD.jsonl> <carpeta de salida>

Usa los días normales de la semana (sin los de «aparte» en captura/dias.json). El método va redondeado a minutos, como
lo ve el viajero (igual que en resultados.py).
"""
import collections
import datetime
import json
import os
import random
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import resultados as RS  # noqa: E402


def p2(v):
    return 100 * sum(abs(x) <= 120 for x in v) / len(v)


def escribir(ruta, cabecera, filas):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(cabecera + '\n')
        for fila in filas:
            f.write(' '.join(str(x) for x in fila) + '\n')


def main():
    entrada, salida = sys.argv[1], sys.argv[2]
    os.makedirs(salida, exist_ok=True)
    aparte = set(json.load(open(os.path.join(AQUI, 'captura', 'dias.json'), encoding='utf-8'))['aparte'])
    P = [p for p in RS.leer(entrada) if p['dia'] not in aparte and 0 <= p['real'] - p['t'] < 1800]
    for p in P:
        e = RS.errores(p)
        p['eo'], p['em'] = e['oficial'], e['metodo_min']

    # 1. Por minuto que falta: proporción a ±2 min y error mediano, con IC 95 % por viajes (bootstrap).
    por_min = collections.defaultdict(list)
    for p in P:
        por_min[int((p['real'] - p['t']) // 60)].append(p)
    rnd = random.Random(7)
    filas = []
    for m in range(30):
        ps = por_min[m]
        grupos = collections.defaultdict(lambda: [0, 0, 0])
        for p in ps:
            g = grupos[(p['dia'], p['viaje'], p['vehiculo'])]
            g[0] += 1
            g[1] += abs(p['eo']) <= 120
            g[2] += abs(p['em']) <= 120
        gl = list(grupos.values())
        bo, bm = [], []
        for _ in range(300):
            n = o = me = 0
            for g in rnd.choices(gl, k=len(gl)):
                n += g[0]
                o += g[1]
                me += g[2]
            bo.append(100 * o / n)
            bm.append(100 * me / n)
        bo.sort()
        bm.sort()
        filas.append((m + 0.5, round(p2([p['eo'] for p in ps]), 1), round(bo[7], 1), round(bo[292], 1),
                      round(p2([p['em'] for p in ps]), 1), round(bm[7], 1), round(bm[292], 1),
                      round(statistics.median([abs(p['eo']) for p in ps])), round(statistics.median([abs(p['em']) for p in ps])), len(ps)))
    escribir(os.path.join(salida, 'minutos.dat'), 'min ofi ofilo ofihi met metlo methi maeofi maemet n', filas)

    # 2. Distribución del error con signo, a 10–20 minutos (cubos de 30 s, de −10 a +10 min).
    sel = [p for p in P if 600 <= p['real'] - p['t'] < 1200]
    co, cm = collections.Counter(), collections.Counter()
    for p in sel:
        co[max(-20, min(19, int(p['eo'] // 30)))] += 1
        cm[max(-20, min(19, int(p['em'] // 30)))] += 1
    escribir(os.path.join(salida, 'errores.dat'), 'min ofi met',
             [((b * 30 + 15) / 60, round(100 * co[b] / len(sel), 2), round(100 * cm[b] / len(sel), 2)) for b in range(-20, 20)])

    # 3. Por parada: proporción a ±2 min (horizontes de 3 a 30 min).
    por_parada = collections.defaultdict(list)
    for p in P:
        if p['real'] - p['t'] >= 180:
            por_parada[p['parada']].append(p)
    escribir(os.path.join(salida, 'paradas.dat'), 'ofi met n prioritaria',
             [(round(p2([p['eo'] for p in ps]), 1), round(p2([p['em'] for p in ps]), 1), len(ps), int(ps[0]['prioritaria']))
              for ps in por_parada.values() if len(ps) >= 100])

    # 4. Por hora del día (horizontes de 3 a 30 min).
    por_hora = collections.defaultdict(list)
    for p in P:
        if p['real'] - p['t'] >= 180:
            por_hora[int(p['t'] // 3600)].append(p)
    escribir(os.path.join(salida, 'horas.dat'), 'hora ofi met n',
             [(h, round(p2([p['eo'] for p in ps]), 1), round(p2([p['em'] for p in ps]), 1), len(ps))
              for h, ps in sorted(por_hora.items()) if len(ps) >= 200])

    # 5. Por día.
    por_dia = collections.defaultdict(list)
    for p in RS.leer(entrada):
        if 180 <= p['real'] - p['t'] < 1800:
            e = RS.errores(p)
            por_dia[p['dia']].append((e['oficial'], e['metodo_min']))
    nombres = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    escribir(os.path.join(salida, 'dias.dat'), 'dia ofi met',
             [('{%s %d%s}' % (nombres[datetime.date.fromisoformat(d).weekday()], int(d[8:]), '*' if d in aparte else ''),
               round(p2([x[0] for x in v]), 1), round(p2([x[1] for x in v]), 1)) for d, v in sorted(por_dia.items())])

    # 6. Un autobús de ejemplo: el paso (viaje, parada) con más consultas desde 25 min antes, con errores medianos
    # parecidos a los del conjunto (para no escoger un caso extremo a favor de ninguno).
    pasos = collections.defaultdict(list)
    for p in P:
        if p['e'] == 1:
            pasos[(p['dia'], p['viaje'], p['vehiculo'], p['parada'], round(p['real']))].append(p)
    candidatos = []
    for k, ps in pasos.items():
        h = [p['real'] - p['t'] for p in ps]
        if max(h) >= 1500 and len(ps) >= 20:
            mo = statistics.median([abs(p['eo']) for p in ps])
            mm = statistics.median([abs(p['em']) for p in ps])
            candidatos.append((abs(mo - 190) + abs(mm - 80), k))
    candidatos.sort()
    k = candidatos[0][1]
    ps = sorted(pasos[k], key=lambda p: p['t'])
    escribir(os.path.join(salida, 'ejemplo.dat'), 'antes ofi met',
             [(round((p['real'] - p['t']) / 60, 2), round((p['oficial'] - p['t']) / 60, 2), round((p['t'] + 60 * max(0, round((p['metodo'] - p['t']) / 60)) - p['t']) / 60, 2)) for p in ps])
    with open(os.path.join(salida, 'ejemplo.txt'), 'w', encoding='utf-8') as f:
        f.write('%s viaje %s vehículo %s parada %s línea %s paso %s\n' % (k[0], k[1], k[2], k[3], ps[0]['linea'], k[4]))
    print('ejemplo:', k, ps[0]['linea'], len(ps))


if __name__ == '__main__':
    main()
