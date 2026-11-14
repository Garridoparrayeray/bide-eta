"""Tablas del artículo 2 a partir de los pares de comparar.py (pares-AAAAMMDD.jsonl y sus .cuentas.json).

Uso: python3 resultados.py <carpeta con los pares> [--ablacion <carpeta con los pares de comparar.py --sin-aprender>]
                           [--tex <carpeta para las tablas LaTeX>] [--remuestreos 2000]

Tres fuentes, todas contra el paso real a: el horario publicado (la hora del GTFS en la parada), el tiempo real oficial
de Bizkaibus (hora de la consulta + 60 × minutos anunciados) y Bide+ (redondeado a minutos desde la consulta, con el
redondeo de la app: mitades hacia fuera del cero). Error = predicción − a (positivo: el autobús llega antes de lo
anunciado).

Conjunto principal: días normales (sin los de «aparte» de captura/dias.json), sin las paradas de «paradas_excluidas»,
con 0 ≤ a − t < 30 min, Bide+ calculado con el autobús en el feed y la identidad del autobús confirmada por la distancia
que da el servicio oficial (ver identidad_confirmada). El resto de variantes van en la tabla de sensibilidad.
"""
import argparse
import collections
import datetime
import glob
import gzip
import json
import math
import os
import random
import statistics

AQUI = os.path.dirname(os.path.abspath(__file__))
HORIZONTES = [(0, 180, '0--3'), (180, 360, '3--6'), (360, 600, '6--10'), (600, 1200, '10--20'), (1200, 1800, '20--30')]
ANUNCIADOS = [(0, 2, '0--2'), (3, 5, '3--5'), (6, 9, '6--9'), (10, 19, '10--19'), (20, 29, '20--29'), (30, 999, '30+')]
FUENTES = ('horario', 'oficial', 'bide')
NOMBRES = {'horario': 'Timetable', 'oficial': 'Official', 'bide': 'Bide+'}
DIAS_SEMANA = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def redondeo_php(x):
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def leer(carpeta):
    for f in sorted(glob.glob(os.path.join(carpeta, 'pares-*.jsonl*'))):
        if f.endswith('.json'):
            continue
        abrir = gzip.open if f.endswith('.gz') else open
        with abrir(f, 'rt', encoding='utf-8') as fh:
            for linea in fh:
                yield json.loads(linea)


def config():
    return json.load(open(os.path.join(AQUI, 'captura', 'dias.json'), encoding='utf-8'))


def identidad_confirmada(p, tolerancia_m=500, razon=(0.6, 2.0)):
    """El servicio oficial da la distancia del autobús que anuncia. Se acepta el emparejamiento si se parece a la
    distancia del autobús emparejado (por el trazado, según el feed): a menos de 500 m, o entre 0,6 y 2 veces."""
    mo, mb = p.get('metros_oficial'), p.get('metros_bus')
    if mo is None or mb is None:
        return False
    return abs(mo - mb) <= tolerancia_m or (mb > 0 and razon[0] <= mo / mb <= razon[1])


VELOCIDAD_MAXIMA = 30.0   # m/s (108 km/h)


def paso_imposible(p):
    """El paso real exigiría ir a más de 30 m/s desde donde estaba el autobús (según el feed o el servicio oficial):
    la reconstrucción del paso ha fallado (le pasa sobre todo cerca de las terminales de Bilbao)."""
    d = [x for x in (p.get('metros_bus'), p.get('metros_oficial')) if x is not None]
    return bool(d) and min(d) > VELOCIDAD_MAXIMA * max(1, (p['real'] - p['t']) + 60)


def errores(p, desplazamiento=0, oficial_extra=0, bide='minutos'):
    t, real = p['t'], p['real'] + desplazamiento
    if bide == 'segundos':
        b = p['metodo']
    elif bide == 'suelo':
        b = t + 60 * max(0, math.floor((p['metodo'] - t) / 60))
    else:
        b = t + 60 * max(0, redondeo_php((p['metodo'] - t) / 60))
    return {'horario': p['horario'] - real, 'oficial': p['oficial'] + oficial_extra - real, 'bide': b - real}


def horizonte(p):
    h = p['real'] - p['t']
    for lo, hi, nombre in HORIZONTES:
        if lo <= h < hi:
            return nombre
    return None


def anunciado(p):
    for lo, hi, nombre in ANUNCIADOS:
        if lo <= p['minutos'] <= hi:
            return nombre
    return None


def clave_viaje(p):
    return (p['dia'], p['viaje'], p['vehiculo'])


def clave_paso(p):
    return (p['dia'], p['viaje'], p['vehiculo'], p['parada'], round(p['real']))


def cargar(carpeta, variante='principal'):
    """Pares de la semana según la variante. Devuelve (semana, aparte)."""
    cfg = config()
    aparte = set(cfg['aparte'])
    excluidas = set(cfg.get('paradas_excluidas', {}))
    semana, separado = [], []
    for p in leer(carpeta):
        if horizonte(p) is None:
            continue
        if p['parada'] in excluidas and variante != 'con_excluidas':
            continue
        if paso_imposible(p) and variante != 'con_excluidas':
            continue
        if variante in ('principal', 'con_excluidas', 'estricta') and p.get('capa') != 'feed':
            continue
        if variante in ('principal', 'con_excluidas') and not identidad_confirmada(p):
            continue
        if variante == 'estricta' and not identidad_confirmada(p, 300, (0.8, 1.25)):
            continue
        if variante == 'feed' and p.get('capa') != 'feed':
            continue
        (separado if p['dia'] in aparte else semana).append(p)
    return semana, separado


def resumen(pares, **kw):
    out = {}
    for f in FUENTES:
        e = [errores(p, **kw)[f] for p in pares]
        a = [abs(x) for x in e]
        n = len(e)
        out[f] = {'n': n, 'mediana': statistics.median(a), 'mae': sum(a) / n,
                  'p1': sum(x <= 60 for x in a) / n, 'p2': sum(x <= 120 for x in a) / n, 'p3': sum(x <= 180 for x in a) / n,
                  'sesgo': statistics.median(e), 'antes': sum(x > 120 for x in e) / n}
    return out


def bootstrap_dif(pares, agrupar, remuestreos, semilla=7, umbral=120, a='bide', b='oficial'):
    """IC 95 % (percentil) de la diferencia a − b en la proporción a ±umbral, remuestreando grupos enteros."""
    grupos = collections.defaultdict(lambda: [0, 0, 0])
    for p in pares:
        e = errores(p)
        g = grupos[agrupar(p)]
        g[0] += 1
        g[1] += abs(e[a]) <= umbral
        g[2] += abs(e[b]) <= umbral
    lista = list(grupos.values())
    rnd = random.Random(semilla)
    difs = []
    for _ in range(remuestreos):
        n = x = y = 0
        for g in rnd.choices(lista, k=len(lista)):
            n += g[0]
            x += g[1]
            y += g[2]
        difs.append((x - y) / n)
    difs.sort()
    return difs[int(0.025 * remuestreos)], difs[int(0.975 * remuestreos) - 1], len(lista)


def prueba_pareada(pares, agrupar):
    """Diferencia media de pérdida d = |e_oficial| − |e_Bide+| (s) con error típico robusto por grupos (tipo
    Diebold–Mariano con dependencia dentro de cada grupo). Devuelve (media, ET, z)."""
    sumas = collections.defaultdict(lambda: [0.0, 0])
    for p in pares:
        e = errores(p)
        s = sumas[agrupar(p)]
        s[0] += abs(e['oficial']) - abs(e['bide'])
        s[1] += 1
    n = sum(s[1] for s in sumas.values())
    media = sum(s[0] for s in sumas.values()) / n
    g = len(sumas)
    var = sum((s[0] - media * s[1]) ** 2 for s in sumas.values()) * g / (g - 1) / n ** 2
    et = math.sqrt(var)
    return media, et, media / et


def modelo_viajero(pares, minutos_antes):
    """El viajero llega a la parada k minutos antes de la hora anunciada. Pierde el autobús si este pasa antes de que
    llegue; si no, espera a − (anuncio − k). Devuelve, por fuente, (proporción que lo pierde, espera media en min)."""
    out = {}
    for f in FUENTES:
        pierde, esperas = 0, []
        for p in pares:
            e = errores(p)[f]
            llegada = p['real'] + e - 60 * minutos_antes
            if p['real'] < llegada:
                pierde += 1
            else:
                esperas.append((p['real'] - llegada) / 60)
        out[f] = (pierde / len(pares), sum(esperas) / len(esperas))
    return out


def fila(nombre, r, n=None):
    celdas = ['%.0f & %.0f & %.0f' % (r[f]['mediana'], 100 * r[f]['p2'], 100 * r[f]['antes']) for f in FUENTES]
    return '%s & %s & %s \\\\' % (nombre, '{:,}'.format(n if n is not None else r['oficial']['n']), ' & '.join(celdas))


def nombre_dia(d, aparte):
    return '%s %d Nov%s' % (DIAS_SEMANA[datetime.date.fromisoformat(d).weekday()], int(d[8:]), ' (strike)' if d in aparte else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('carpeta')
    ap.add_argument('--ablacion')
    ap.add_argument('--tex')
    ap.add_argument('--remuestreos', type=int, default=2000)
    a = ap.parse_args()
    cfg = config()
    aparte = set(cfg['aparte'])
    tex = collections.defaultdict(list)
    semana, separado = cargar(a.carpeta)
    print('Conjunto principal: %d pares, %d pasos, %d viajes, %d vehículos, %d líneas, %d paradas' % (
        len(semana), len({clave_paso(p) for p in semana}), len({clave_viaje(p) for p in semana}),
        len({p['vehiculo'] for p in semana}), len({p['linea'] for p in semana}), len({p['parada'] for p in semana})))

    # 1. Flujo de anuncios a pares, por día.
    print('\n== Flujo')
    todos = list(leer(a.carpeta))
    excluidas = set(cfg.get('paradas_excluidas', {}))
    for f in sorted(glob.glob(os.path.join(a.carpeta, 'pares-*.jsonl.cuentas.json'))):
        c = json.load(open(f))
        d = c['dia']
        ps = [p for p in todos if p['dia'] == d and horizonte(p) is not None]
        feed = [p for p in ps if p['capa'] == 'feed']
        sin_excl = [p for p in feed if p['parada'] not in excluidas and not paso_imposible(p)]
        conf = [p for p in sin_excl if identidad_confirmada(p)]
        r = (nombre_dia(d, aparte), c['consultas'], c['anuncios'], c['ruta_doble'], c['sin_paso'], len(ps),
             len(ps) - len(feed), len(feed) - len(sin_excl), len(sin_excl) - len(conf), len(conf))
        print('  %-20s consultas %6d anuncios %7d doble %5d sin_paso %7d pares %6d sin_feed %6d parada_excl %5d '
              'sin_confirmar %6d principal %6d' % r)
        tex['flujo'].append('%s & %s \\\\' % (r[0], ' & '.join('{:,}'.format(x) for x in r[1:])))

    # 2. Por horizonte real.
    print('\n== Por minutos hasta el paso real')
    por_h = collections.defaultdict(list)
    for p in semana:
        por_h[horizonte(p)].append(p)
    for _, _, h in HORIZONTES:
        r = resumen(por_h[h])
        print('  %-7s n=%6d | %s' % (h, len(por_h[h]), ' | '.join('%s med %4.0f ±1 %3.0f ±2 %3.0f ±3 %3.0f sesgo %+5.0f antes %3.0f' % (
            NOMBRES[f], r[f]['mediana'], 100 * r[f]['p1'], 100 * r[f]['p2'], 100 * r[f]['p3'], r[f]['sesgo'], 100 * r[f]['antes']) for f in FUENTES)))
        tex['horizonte'].append(fila(h, r))
        tex['horizonte_extra'].append('%s & %s \\\\' % (h, ' & '.join('%.0f & %+.0f' % (100 * r[f]['p1'], r[f]['sesgo']) for f in FUENTES)))
    for _, _, h in HORIZONTES:
        r = resumen(por_h[h])
        cola = {f: sum(abs(errores(p)[f]) > 600 for p in por_h[h]) / len(por_h[h]) for f in FUENTES}
        tex['colas'].append('%s & %s \\\\' % (h, ' & '.join('%.0f & %.1f' % (r[f]['mae'], 100 * cola[f]) for f in FUENTES)))
    r = resumen(semana)
    tex['horizonte'].append('\\midrule\n' + fila('All', r))
    tex['horizonte_extra'].append('\\midrule\nAll & %s \\\\' % ' & '.join('%.0f & %+.0f' % (100 * r[f]['p1'], r[f]['sesgo']) for f in FUENTES))
    print('  Todo    | %s' % ' | '.join('%s ±2 %.1f' % (NOMBRES[f], 100 * r[f]['p2']) for f in FUENTES))

    # 3. Inferencia: IC de la diferencia (por viajes y por paradas) y prueba pareada.
    print('\n== Bide+ − oficial a ±2 min: IC 95 %% (%d remuestreos) y prueba pareada de |error|' % a.remuestreos)
    for _, _, h in HORIZONTES + [(0, 0, 'All')]:
        ps = semana if h == 'All' else por_h[h]
        lo1, hi1, gv = bootstrap_dif(ps, clave_viaje, a.remuestreos)
        lo2, hi2, gp = bootstrap_dif(ps, lambda p: p['parada'], a.remuestreos)
        m, et, z = prueba_pareada(ps, lambda p: p['parada'])
        print('  %-7s viajes [%+.1f, %+.1f] (%d)  paradas [%+.1f, %+.1f] (%d)  d = %.0f s (ET %.0f, z = %.1f)' % (
            h, 100 * lo1, 100 * hi1, gv, 100 * lo2, 100 * hi2, gp, m, et, z))
        tex['inferencia'].append('%s & $[%+.1f, %+.1f]$ & $[%+.1f, %+.1f]$ & %.0f & %.0f & %.1f \\\\' % (
            h, 100 * lo1, 100 * hi1, 100 * lo2, 100 * hi2, m, et, z))

    # 4. Por minutos anunciados por el servicio oficial (lo que vio el viajero).
    print('\n== Por minutos anunciados (oficial)')
    por_a = collections.defaultdict(list)
    for p in semana:
        por_a[anunciado(p)].append(p)
    for _, _, h in ANUNCIADOS:
        if por_a[h]:
            r = resumen(por_a[h])
            print('  %-7s n=%6d | %s' % (h, len(por_a[h]), ' | '.join('%s ±2 %3.0f antes %3.0f' % (NOMBRES[f], 100 * r[f]['p2'], 100 * r[f]['antes']) for f in FUENTES)))
            tex['anunciado'].append(fila(h, r))

    # 5. Sensibilidad.
    print('\n== Sensibilidad (±2 min, todos los horizontes y 10–20 min)')
    variantes = [
        ('Main analysis', semana, {}),
        ('Actual passage $-60$ s', semana, {'desplazamiento': -60}),
        ('Actual passage $-30$ s', semana, {'desplazamiento': -30}),
        ('Actual passage $+30$ s', semana, {'desplazamiento': 30}),
        ('Actual passage $+60$ s', semana, {'desplazamiento': 60}),
        ('Official $+30$ s (minutes truncated)', semana, {'oficial_extra': 30}),
        ('Bide+ in seconds', semana, {'bide': 'segundos'}),
        ('Bide+ minutes truncated', semana, {'bide': 'suelo'}),
    ]
    for nombre, var in (('Stricter identity check', 'estricta'), ('No identity check', 'feed'),
                        ('No identity check, with fallback', 'todos'), ('With stop 3394 and impossible passages', 'con_excluidas')):
        variantes.append((nombre, cargar(a.carpeta, var)[0], {}))
    rnd = random.Random(11)
    por_paso = collections.defaultdict(list)
    for p in semana:
        por_paso[clave_paso(p)].append(p)
    variantes.append(('One pair per passage (random)', [rnd.choice(v) for v in por_paso.values()], {}))
    variantes.append(('Without priority stops', [p for p in semana if not p['prioritaria']], {}))
    variantes.append(('Bide+ with live position only', [p for p in semana if p['estado'] == 'live'], {}))
    for nombre, ps, kw in variantes:
        r = resumen(ps, **kw)
        r10 = resumen([p for p in ps if horizonte(p) == '10--20'], **kw)
        print('  %-48s n=%7d | todo: hor %4.1f ofi %4.1f bide %4.1f | 10–20: ofi %4.1f bide %4.1f' % (
            nombre, len(ps), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
        tex['sensibilidad'].append('%s & %s & %.0f & %.0f & %.0f & %.0f & %.0f \\\\' % (
            nombre, '{:,}'.format(len(ps)), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
    for umbral, clave in ((60, 'p1'), (180, 'p3')):
        r = resumen(semana)
        tex['sensibilidad'].append('Threshold $\\pm%d$ min & %s & %.0f & %.0f & %.0f & -- & -- \\\\' % (
            umbral // 60, '{:,}'.format(len(semana)), 100 * r['horario'][clave], 100 * r['oficial'][clave], 100 * r['bide'][clave]))
    r = resumen(semana)
    tex['sensibilidad'].append('Mean absolute error (s) & %s & %.0f & %.0f & %.0f & -- & -- \\\\' % (
        '{:,}'.format(len(semana)), r['horario']['mae'], r['oficial']['mae'], r['bide']['mae']))

    # 6. Modelo del viajero (horizontes de 3 a 30 min, cuando decide cuándo salir).
    print('\n== Modelo del viajero (3–30 min): pierde el autobús / espera media (min)')
    ps = [p for p in semana if p['real'] - p['t'] >= 180]
    for k in (1, 2, 3):
        m = modelo_viajero(ps, k)
        print('  llega %d min antes: %s' % (k, ' | '.join('%s pierde %.0f %% espera %.1f' % (NOMBRES[f], 100 * m[f][0], m[f][1]) for f in FUENTES)))
        tex['viajero'].append('%d min & %s \\\\' % (k, ' & '.join('%.0f & %.1f' % (100 * m[f][0], m[f][1]) for f in FUENTES)))

    # 7. Grupos: tipo de día, paradas, anuncio, capa de Bide+, campo «tipo» del servicio oficial.
    print('\n== Grupos')
    grupos = [
        ('Weekdays', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() < 5]),
        ('Sunday', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() == 6]),
        ('Saturday', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() == 5]),
        ('Priority stops', [p for p in semana if p['prioritaria']]),
        ('Other stops', [p for p in semana if not p['prioritaria']]),
        ('Next bus ($e_1$)', [p for p in semana if p['e'] == 1]),
        ('Second bus ($e_2$)', [p for p in semana if p['e'] == 2]),
    ]
    for nombre, ps in grupos:
        if ps:
            tex['grupos'].append(fila(nombre, resumen(ps)))
            print('  %-20s n=%6d ofi %.1f bide %.1f' % (nombre, len(ps), 100 * resumen(ps)['oficial']['p2'], 100 * resumen(ps)['bide']['p2']))
    print('  estados de Bide+:', collections.Counter(p['estado'] for p in semana).most_common())
    print('  tipo (oficial):', collections.Counter(p.get('tipo', '') for p in semana).most_common())

    # 8. Por día (con el de huelga aparte).
    por_dia = collections.defaultdict(list)
    for p in semana + separado:
        por_dia[p['dia']].append(p)
    for d in sorted(por_dia):
        tex['dias'].append(fila(nombre_dia(d, aparte), resumen(por_dia[d])))

    # 9. Paradas: en cuántas gana Bide+ con IC por viajes que no cruza el cero.
    por_parada = collections.defaultdict(list)
    for p in semana:
        if p['real'] - p['t'] >= 180:
            por_parada[p['parada']].append(p)
    gana = gana_ic = 0
    for s, ps in por_parada.items():
        r = resumen(ps)
        if r['bide']['p2'] > r['oficial']['p2']:
            gana += 1
            lo, hi, _ = bootstrap_dif(ps, clave_viaje, 300, semilla=3)
            gana_ic += lo > 0
    print('\n== Paradas: Bide+ mejor en %d de %d; con el IC 95 %% por encima de cero en %d' % (gana, len(por_parada), gana_ic))

    # 10. Ablación: Bide+ sin lo aprendido, en los mismos pares.
    if a.ablacion:
        sin = {(p['dia'], p['vehiculo'], p['viaje'], p['parada'], p['t'], p['e']): p for p in leer(a.ablacion)}
        print('\n== Ablación (mismos pares)')
        for _, _, h in HORIZONTES + [(0, 0, 'All')]:
            ps = semana if h == 'All' else por_h[h]
            pares = [(p, sin.get((p['dia'], p['vehiculo'], p['viaje'], p['parada'], p['t'], p['e']))) for p in ps]
            pares = [(p, q) for p, q in pares if q is not None]
            if not pares:
                continue
            con = resumen([p for p, _ in pares])
            sin_r = resumen([q for _, q in pares])
            print('  %-7s n=%6d ofi %.1f | Bide+ %.1f | sin aprender %.1f' % (h, len(pares), 100 * con['oficial']['p2'], 100 * con['bide']['p2'], 100 * sin_r['bide']['p2']))
            tex['ablacion'].append('%s & %s & %.0f & %.0f & %.0f & %.0f \\\\' % (
                h, '{:,}'.format(len(pares)), 100 * con['horario']['p2'], 100 * con['oficial']['p2'], 100 * sin_r['bide']['p2'], 100 * con['bide']['p2']))

    if a.tex:
        os.makedirs(a.tex, exist_ok=True)
        for clave, filas in tex.items():
            with open(os.path.join(a.tex, clave + '.tex'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(filas) + '\n')


if __name__ == '__main__':
    main()
