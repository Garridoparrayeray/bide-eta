"""Tablas del artículo 2 a partir de los pares de comparar.py (pares-AAAAMMDD.jsonl o .jsonl.gz).

Uso: python3 resultados.py <carpeta con los pares> [--tex <carpeta para las tablas LaTeX>]

Errores = llegada anunciada menos paso real, en segundos. Para el servicio oficial, la hora de la consulta más los
minutos que anuncia; para el método, su llegada prevista y, en «método (minutos)», esa misma llegada redondeada a
minutos enteros desde la hora de la consulta, como la vería el viajero. Los días de «aparte» de captura/dias.json no
entran en la semana y se dan por separado. Los intervalos de confianza (95 %) son de bootstrap por viajes enteros: cada
remuestreo toma viajes (día, línea, número de viaje y vehículo) con reemplazo, con todos sus pares.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import random
import statistics

AQUI = os.path.dirname(os.path.abspath(__file__))
HORIZONTES = [(0, 180, '0--3'), (180, 360, '3--6'), (360, 600, '6--10'), (600, 1200, '10--20'), (1200, 1800, '20--30')]
FUENTES = ('oficial', 'metodo_min', 'metodo')
FUENTES_TEX = ('oficial', 'metodo_min')
NOMBRES = {'oficial': 'Official', 'metodo_min': 'Method (minutes)', 'metodo': 'Method (seconds)'}
REMUESTREOS = 400


def leer(carpeta):
    for f in sorted(glob.glob(os.path.join(carpeta, 'pares-*.jsonl*'))):
        abrir = gzip.open if f.endswith('.gz') else open
        with abrir(f, 'rt', encoding='utf-8') as fh:
            for linea in fh:
                yield json.loads(linea)


def errores(p):
    t, real = p['t'], p['real']
    minutos = round((p['metodo'] - t) / 60)
    return {'oficial': p['oficial'] - real, 'metodo': p['metodo'] - real, 'metodo_min': t + 60 * max(0, minutos) - real}


def resumen(pares):
    out = {}
    for f in FUENTES:
        e = [errores(p)[f] for p in pares]
        a = [abs(x) for x in e]
        out[f] = {'n': len(e), 'mediana': statistics.median(a), 'p1': sum(x <= 60 for x in a) / len(a),
                  'p2': sum(x <= 120 for x in a) / len(a), 'sesgo': statistics.median(e),
                  'antes': sum(x > 120 for x in e) / len(e)}
    return out


def intervalo(pares, umbral=120, semilla=7):
    """IC 95 % de (método en minutos − oficial) en la proporción a ±umbral, por bootstrap de viajes."""
    por_viaje = collections.defaultdict(lambda: [0, 0, 0])
    for p in pares:
        e = errores(p)
        c = por_viaje[(p['dia'], p['viaje'], p['vehiculo'])]
        c[0] += 1
        c[1] += abs(e['metodo_min']) <= umbral
        c[2] += abs(e['oficial']) <= umbral
    grupos = list(por_viaje.values())
    rnd = random.Random(semilla)
    difs = []
    for _ in range(REMUESTREOS):
        n = m = o = 0
        for g in rnd.choices(grupos, k=len(grupos)):
            n += g[0]
            m += g[1]
            o += g[2]
        difs.append((m - o) / n)
    difs.sort()
    return difs[int(0.025 * REMUESTREOS)], difs[int(0.975 * REMUESTREOS) - 1], len(grupos)


def horizonte(p):
    h = p['real'] - p['t']
    for lo, hi, nombre in HORIZONTES:
        if lo <= h < hi:
            return nombre
    return None


def fila_tex(nombre, r):
    celdas = []
    for f in FUENTES_TEX:
        celdas.append('%.0f & %.0f & %.0f' % (r[f]['mediana'], 100 * r[f]['p2'], 100 * r[f]['antes']))
    return '%s & %s & %s \\\\' % (nombre, '{:,}'.format(r['oficial']['n']), ' & '.join(celdas))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('carpeta')
    ap.add_argument('--tex')
    ap.add_argument('--sin-ambiguos', action='store_true', help='quita los pares con otro autobús de la línea a menos de 2 min')
    a = ap.parse_args()
    dias = json.load(open(os.path.join(AQUI, 'captura', 'dias.json'), encoding='utf-8'))
    aparte = set(dias['aparte'])
    semana, separado = [], []
    for p in leer(a.carpeta):
        if horizonte(p) is None:
            continue
        if a.sin_ambiguos and p['hueco'] is not None and p['hueco'] < 120:
            continue
        (separado if p['dia'] in aparte else semana).append(p)

    tablas = {}

    def bloque(titulo, grupos, clave):
        print('\n== ' + titulo)
        print('%-22s %8s | %s' % ('', 'n', ' | '.join('%-30s' % NOMBRES[f] for f in FUENTES)))
        filas = []
        for nombre, ps in grupos:
            if not ps:
                continue
            r = resumen(ps)
            print('%-22s %8d | %s' % (nombre, len(ps), ' | '.join(
                'med %4.0f s ±1 %3.0f%% ±2 %3.0f%% sesgo %+4.0f antes %2.0f%%' % (r[f]['mediana'], 100 * r[f]['p1'], 100 * r[f]['p2'], r[f]['sesgo'], 100 * r[f]['antes'])
                for f in FUENTES)))
            filas.append(fila_tex(nombre, r))
        tablas[clave] = filas

    por_h = collections.defaultdict(list)
    for p in semana:
        por_h[horizonte(p)].append(p)
    bloque('Semana, por cuánto falta (min)', [(h, por_h[h]) for _, _, h in HORIZONTES] + [('All', semana)], 'horizonte')

    print('\nIC 95 %% de (método en minutos − oficial) a ±2 min, bootstrap por viajes:')
    for _, _, h in HORIZONTES:
        if por_h[h]:
            lo, hi, g = intervalo(por_h[h])
            print('  %-7s [%+.1f, %+.1f] puntos (%d viajes)' % (h, 100 * lo, 100 * hi, g))

    print('\nDiagnóstico: anuncio a ±60 s de la hora del horario publicado (y error del horario):')
    for _, _, h in HORIZONTES:
        ps = por_h[h]
        if ps:
            of = sum(abs(p['oficial'] - p['horario']) <= 60 for p in ps) / len(ps)
            me = sum(abs(p['metodo'] - p['horario']) <= 60 for p in ps) / len(ps)
            ho = sum(abs(p['horario'] - p['real']) <= 120 for p in ps) / len(ps)
            print('  %-7s oficial %3.0f %%, método %3.0f %%; el horario acierta a ±2 min el %3.0f %%' % (h, 100 * of, 100 * me, 100 * ho))

    lab = [p for p in semana if __import__('datetime').date.fromisoformat(p['dia']).weekday() < 5]
    fin = [p for p in semana if __import__('datetime').date.fromisoformat(p['dia']).weekday() >= 5]
    bloque('Tipo de día', [('Weekday', lab), ('Weekend', fin)], 'tipo')
    bloque('Paradas', [('Priority stops', [p for p in semana if p['prioritaria']]),
                       ('Other stops', [p for p in semana if not p['prioritaria']])], 'paradas')
    por_dia = collections.defaultdict(list)
    for p in semana + separado:
        por_dia[p['dia']].append(p)
    bloque('Por día', [(d + (' (strike)' if d in aparte else ''), por_dia[d]) for d in sorted(por_dia)], 'dias')
    bloque('Primer y segundo autobús', [('Next bus (e1)', [p for p in semana if p['e'] == 1]),
                                        ('Second bus (e2)', [p for p in semana if p['e'] == 2])], 'e')

    if a.tex:
        os.makedirs(a.tex, exist_ok=True)
        for clave, filas in tablas.items():
            with open(os.path.join(a.tex, clave + '.tex'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(filas) + '\n')


if __name__ == '__main__':
    main()
