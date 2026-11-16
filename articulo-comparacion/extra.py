"""Análisis complementarios del artículo 2 pedidos en la tercera ronda de revisión.

Uso: python3 extra.py <carpeta de pares> <carpeta de capturas por día> [--tramos <carpeta de la ablación sin tramos>]
                      [--tex <carpeta>]

1. Cobertura de los anuncios del primer autobús a menos de 30 min, por minutos anunciados: cuántos se emparejan y
   cuántos entran en el conjunto principal; y la precisión oficial en los pares que no entran (sin feed, sin confirmar).
2. Remuestreo por líneas (2000) de la diferencia Bide+ − oficial a ±2 min, por horizonte.
3. Ablación: IC por viajes de (Bide+ sin tramos − oficial) y (Bide+ − Bide+ sin tramos).
4. Paradas: cuántas siguen por encima de cero con la corrección de Holm (p bilateral normal con el ET del remuestreo).
5. Pares usados por el modelo del viajero.
"""
import argparse
import collections
import datetime
import glob
import json
import math
import os
import random
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import resultados as RS  # noqa: E402

BINS = [(0, 2, '0--2'), (3, 5, '3--5'), (6, 9, '6--9'), (10, 19, '10--19'), (20, 29, '20--29')]


def bin_m(m):
    for lo, hi, n in BINS:
        if lo <= m <= hi:
            return n
    return None


def p2(ps, f):
    return 100 * sum(abs(RS.errores(p)[f]) <= 120 for p in ps) / len(ps) if ps else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pares')
    ap.add_argument('capturas')
    ap.add_argument('--tramos')
    ap.add_argument('--tex')
    a = ap.parse_args()
    cfg = RS.config()
    aparte = set(cfg['aparte'])
    excluidas = set(cfg.get('paradas_excluidas', {}))
    tex = collections.defaultdict(list)

    # 1. Cobertura por minutos anunciados (primer autobús, m < 30, 06–23 h, días normales).
    anuncios = collections.Counter()
    for dia in sorted(os.listdir(a.capturas)):
        d = '%s-%s-%s' % (dia[:4], dia[4:6], dia[6:])
        if d in aparte or not os.path.exists(os.path.join(a.pares, 'pares-%s.jsonl' % dia)):
            continue
        for f in glob.glob(os.path.join(a.capturas, dia, '**', 'oficial.jsonl'), recursive=True):
            for linea in open(f, encoding='utf-8'):
                o = json.loads(linea)
                if o.get('estado') != 'OK':
                    continue
                h = datetime.datetime.fromisoformat(o['hora']).hour
                if not (6 <= h < 23):
                    continue
                for l in o['lineas']:
                    if l.get('linea') and l.get('e1') and l['e1'].get('minutos') is not None and l['e1']['minutos'] < 30:
                        anuncios[bin_m(l['e1']['minutos'])] += 1
    todos = [p for p in RS.leer(a.pares) if p['dia'] not in aparte and RS.INICIO <= p['t'] < RS.FIN]
    en30 = [p for p in todos if RS.horizonte(p) is not None]
    e1 = [p for p in en30 if p['e'] == 1 and p['minutos'] < 30]
    valido = lambda p: p['parada'] not in excluidas and not RS.paso_fallido(p)
    principal = [p for p in e1 if p['capa'] == 'feed' and valido(p) and RS.identidad_confirmada(p)]
    sin_feed = [p for p in en30 if p['capa'] != 'feed' and valido(p)]
    sin_conf = [p for p in en30 if p['capa'] == 'feed' and valido(p) and not RS.identidad_confirmada(p)]
    princ_todos = [p for p in en30 if p['capa'] == 'feed' and valido(p) and RS.identidad_confirmada(p)]
    print('== Cobertura (e1, m<30)')
    tot = sum(anuncios.values())
    print('[texto] anuncios %d emparejados %d (%.1f %%) principal %d (%.1f %%)' % (
        tot, len(e1), 100 * len(e1) / tot, len(principal), 100 * len(principal) / tot))
    for lo, hi, n in BINS:
        a_n = anuncios[n]
        e_n = sum(1 for p in e1 if bin_m(p['minutos']) == n)
        p_n = sum(1 for p in principal if bin_m(p['minutos']) == n)
        print('  %-6s anuncios %7d emparejados %5.1f %% principal %5.1f %%' % (n, a_n, 100 * e_n / a_n, 100 * p_n / a_n))
        tex['cobertura'].append('%s & %s & %.0f & %.0f \\\\' % (n, '{:,}'.format(a_n), 100 * e_n / a_n, 100 * p_n / a_n))
    tex['cobertura'].append('\\midrule\nAll & %s & %.0f & %.0f \\\\' % ('{:,}'.format(tot), 100 * len(e1) / tot, 100 * len(principal) / tot))
    for nombre, ps in (('principal', princ_todos), ('sin feed', sin_feed), ('sin confirmar', sin_conf)):
        print('[texto] ±2 en %s (%d pares): horario %.1f oficial %.1f bide %.1f' % (
            nombre, len(ps), p2(ps, 'horario'), p2(ps, 'oficial'), p2(ps, 'bide')))
        tex['excluidos'].append('%s & %s & %.0f & %.0f & %.0f \\\\' % (
            {'principal': 'Main analysis', 'sin feed': 'Bus not in the feed at $t$',
             'sin confirmar': 'Identity not confirmed'}[nombre], '{:,}'.format(len(ps)),
            p2(ps, 'horario'), p2(ps, 'oficial'), p2(ps, 'bide')))

    semana, _ = RS.cargar(a.pares)
    por_h = collections.defaultdict(list)
    for p in semana:
        por_h[RS.horizonte(p)].append(p)

    # 2. Remuestreo por líneas.
    print('\n== Remuestreo por líneas (2000)')
    for _, _, h in RS.HORIZONTES + [(0, 0, 'All')]:
        ps = semana if h == 'All' else por_h[h]
        lo, hi, g = RS.bootstrap_dif(ps, lambda p: p['linea'], 2000)
        print('[texto] %-6s líneas %d IC [%+.1f, %+.1f]' % (h, g, 100 * lo, 100 * hi))
        tex['lineas'].append('%s%s & $[%+.1f, %+.1f]$ \\\\' % ('\\midrule\n' if h == 'All' else '', h, 100 * lo, 100 * hi))

    # 3. Ablación con IC.
    if a.tramos:
        clave_par = lambda p: (p['dia'], p['vehiculo'], p['viaje'], p['parada'], p['t'], p['e'])
        claves = {clave_par(p) for p in semana}
        alt = {clave_par(p): p['metodo'] for p in RS.leer_crudo(a.tramos) if clave_par(p) in claves}
        comunes = [p for p in semana if clave_par(p) in alt]
        sin = [dict(p, metodo=alt[clave_par(p)]) for p in comunes]
        # (sin tramos − oficial): a='bide' sobre los pares sin tramos.
        lo, hi, _ = RS.bootstrap_dif(sin, RS.clave_viaje, 2000)
        print('\n[texto] Ablación: sin tramos − oficial, IC por viajes [%+.1f, %+.1f] (n=%d)' % (100 * lo, 100 * hi, len(sin)))
        lo2, hi2, _ = RS.bootstrap_dif(sin, lambda p: p['parada'], 2000)
        print('[texto] Ablación: sin tramos − oficial, IC por paradas [%+.1f, %+.1f]' % (100 * lo2, 100 * hi2))
        # (con − sin tramos): emparejados por par.
        grupos = collections.defaultdict(lambda: [0, 0, 0])
        for p, q in zip(comunes, sin):
            g = grupos[RS.clave_viaje(p)]
            g[0] += 1
            g[1] += abs(RS.errores(p)['bide']) <= 120
            g[2] += abs(RS.errores(q)['bide']) <= 120
        lista = list(grupos.values())
        rnd = random.Random(7)
        difs = []
        for _ in range(2000):
            n = x = y = 0
            for g in rnd.choices(lista, k=len(lista)):
                n += g[0]; x += g[1]; y += g[2]
            difs.append((x - y) / n)
        print('[texto] Ablación: Bide+ − sin tramos, IC por viajes [%+.1f, %+.1f]' % (100 * RS.cuantil(difs, 0.025), 100 * RS.cuantil(difs, 0.975)))

    # 4. Paradas con Holm.
    print('\n== Paradas (3–30 min), Holm')
    por_parada = collections.defaultdict(list)
    for p in semana:
        if p['real'] - p['t'] >= 180:
            por_parada[p['parada']].append(p)
    pvals = []
    for s, ps in por_parada.items():
        if len(ps) < 100:
            continue
        d = (p2(ps, 'bide') - p2(ps, 'oficial')) / 100
        grupos = collections.defaultdict(lambda: [0, 0, 0])
        for p in ps:
            e = RS.errores(p)
            g = grupos[RS.clave_viaje(p)]
            g[0] += 1; g[1] += abs(e['bide']) <= 120; g[2] += abs(e['oficial']) <= 120
        lista = list(grupos.values())
        rnd = random.Random(int(s) if s.isdigit() else 1)
        difs = []
        for _ in range(2000):
            n = x = y = 0
            for g in rnd.choices(lista, k=len(lista)):
                n += g[0]; x += g[1]; y += g[2]
            difs.append((x - y) / n)
        m = sum(difs) / len(difs)
        se = math.sqrt(sum((v - m) ** 2 for v in difs) / (len(difs) - 1))
        z = d / se if se > 0 else float('inf')
        pvals.append((math.erfc(abs(z) / math.sqrt(2)), s, d))
    pvals.sort()
    k = len(pvals)
    favor = 0
    for i, (pv, s, d) in enumerate(pvals):
        if pv > 0.05 / (k - i):
            break
        if d > 0:
            favor += 1
    print('[texto] Paradas: %d; Bide+ por encima con Holm (5 %%) en %d' % (k, favor))

    # 5. Modelo del viajero: pares usados.
    viajero = [p for p in RS.cargar(a.pares, ventana='anunciado')[0] if 3 <= p['minutos'] <= 29]
    usados = [p for p in viajero if p.get('siguiente') is not None and p['siguiente'] - p['real'] <= 7200]
    print('[texto] Modelo del viajero: %d de %d pares (sin siguiente autobús en 2 h: %d)' % (len(usados), len(viajero), len(viajero) - len(usados)))

    # 6. Emparejamiento: precisión oficial por deciles de la razón distancia oficial / línea recta (dentro de 0,6–2,0,
    # autobús a más de 500 m) y diferencia Bide+ − oficial frente al rechazo por parada.
    print('\n== Emparejamiento')
    conr = sorted(((p['metros_oficial'] / p['metros_bus'], p) for p in semana
                   if p.get('metros_bus') and p['metros_bus'] > 500 and p.get('metros_oficial')), key=lambda x: x[0])
    n = len(conr)
    for k in range(10):
        trozo = [p for _, p in conr[k * n // 10:(k + 1) * n // 10]]
        print('[texto] decil %d razón %.2f–%.2f pares %d oficial ±2 %.1f bide ±2 %.1f' % (
            k + 1, conr[k * n // 10][0], conr[(k + 1) * n // 10 - 1][0], len(trozo), p2(trozo, 'oficial'), p2(trozo, 'bide')))
        tex['razon'].append('%d & %.2f--%.2f & %s & %.0f & %.0f \\\\' % (
            k + 1, conr[k * n // 10][0], conr[(k + 1) * n // 10 - 1][0], '{:,}'.format(len(trozo)), p2(trozo, 'oficial'), p2(trozo, 'bide')))
    elig = collections.defaultdict(lambda: [0, 0])
    for p in en30:
        if p['capa'] == 'feed' and valido(p):
            elig[p['parada']][0] += 1
            elig[p['parada']][1] += not RS.identidad_confirmada(p)
    xs, ys = [], []
    for s_, ps in por_parada.items():
        if len(ps) >= 100 and elig[s_][0]:
            xs.append(100 * elig[s_][1] / elig[s_][0])
            ys.append(p2(ps, 'bide') - p2(ps, 'oficial'))
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    alto = [y for x, y in zip(xs, ys) if x >= 15]
    bajo = [y for x, y in zip(xs, ys) if x < 15]
    print('[texto] Rechazo por parada frente a diferencia: r = %.2f; paradas con rechazo ≥15 %%: %d, diferencia media %.1f; '
          'con <15 %%: %d, %.1f' % (r, len(alto), sum(alto) / max(1, len(alto)), len(bajo), sum(bajo) / max(1, len(bajo))))

    if a.tex:
        for clave, filas in tex.items():
            with open(os.path.join(a.tex, clave + '.tex'), 'w', encoding='utf-8') as f:
                f.write(re.sub(r'(?<=& )-(?=\d)', '$-$', '\n'.join(filas)) + '\n')


if __name__ == '__main__':
    main()
