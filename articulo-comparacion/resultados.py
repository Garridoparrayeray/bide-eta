"""Tablas y cifras del artículo 2 a partir de los pares de comparar.py (pares-AAAAMMDD.jsonl y sus .cuentas.json).

Uso: python3 resultados.py <carpeta con los pares> [--ablacion nombre=carpeta ...] [--tex <carpeta>] [--remuestreos 2000]

Tres fuentes, todas contra el paso real a: el horario publicado (la hora del GTFS en la parada), el tiempo real oficial
de Bizkaibus (hora de la consulta + 60 × minutos anunciados) y Bide+ (redondeado a minutos desde la consulta, como la
app: mitades hacia fuera del cero). Error = predicción − a (positivo: el autobús pasa antes de lo previsto).

Conjunto principal: días normales (sin los de «aparte» de captura/dias.json), consultas de 06:00 a 23:00, sin las paradas
de «paradas_excluidas», sin pasos fallidos (ver paso_fallido), con 0 ≤ a − t < 30 min, Bide+ calculado con el autobús en
el feed y la identidad del autobús confirmada por la distancia que da el servicio oficial (ver identidad_confirmada).
Todas las cifras del texto salen de este programa (se imprimen con la etiqueta [texto]).
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
ANUNCIADOS = [(0, 2, '0--2'), (3, 5, '3--5'), (6, 9, '6--9'), (10, 19, '10--19'), (20, 29, '20--29')]
FUENTES = ('horario', 'oficial', 'bide')
NOMBRES = {'horario': 'Timetable', 'oficial': 'Official', 'bide': 'Bide+'}
DIAS_SEMANA = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
INICIO, FIN = 6 * 3600, 23 * 3600
VELOCIDAD_MAXIMA = 30.0       # m/s
DESACUERDO_GPS = 300          # s


def redondeo_php(x):
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def cuantil(v, q):
    """Cuantil con interpolación lineal (como numpy por defecto)."""
    v = sorted(v)
    pos = (len(v) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


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
    """El servicio oficial da la distancia (por carretera, se supone) del autobús que anuncia; metros_bus es la
    distancia en línea recta del autobús emparejado a la parada, según el feed. Se acepta si se parecen: a menos de
    500 m, o con una razón oficial / línea recta entre 0,6 y 2 (la mediana observada es 1,2)."""
    mo, mb = p.get('metros_oficial'), p.get('metros_bus')
    if mo is None or mb is None:
        return False
    return abs(mo - mb) <= tolerancia_m or (mb > 0 and razon[0] <= mo / mb <= razon[1])


def paso_fallido(p):
    """El paso reconstruido no es creíble: (a) el paso por GPS (máxima aproximación, sin el campo de próxima parada)
    difiere más de 5 min, o (b) llegar a tiempo exigiría ir a más de 30 m/s desde la distancia en línea recta (cota
    inferior) dada por el feed o por el servicio oficial, con 60 s de margen por la antigüedad de la copia."""
    if p.get('real_gps') is not None and abs(p['real'] - p['real_gps']) > DESACUERDO_GPS:
        return True
    d = [x for x in (p.get('metros_bus'), p.get('metros_oficial')) if x is not None]
    return bool(d) and min(d) > VELOCIDAD_MAXIMA * max(1, (p['real'] - p['t']) + 60)


def errores(p, desplazamiento=0, oficial_extra=0, bide='minutos', verdad='feed'):
    t = p['t']
    real = (p['real_gps'] if verdad == 'gps' else p['real']) + desplazamiento
    if bide == 'segundos':
        b = p['metodo']
    elif bide == 'suelo':
        b = t + 60 * max(0, math.floor((p['metodo'] - t) / 60))
    else:
        b = t + 60 * max(0, redondeo_php((p['metodo'] - t) / 60))
    return {'horario': p['horario'] - real, 'oficial': p['oficial'] + oficial_extra - real, 'bide': b - real}


def horizonte(p, verdad='feed'):
    h = (p['real_gps'] if verdad == 'gps' else p['real']) - p['t']
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


def cargar(carpeta, variante='principal', ventana='real'):
    """Pares de la semana según la variante. ventana='real': 0 ≤ a − t < 30 min; 'anunciado': minutos anunciados ≤ 29
    y paso en la hora siguiente. Devuelve (semana, aparte)."""
    cfg = config()
    aparte = set(cfg['aparte'])
    excluidas = set(cfg.get('paradas_excluidas', {}))
    semana, separado = [], []
    for p in leer(carpeta):
        if not (INICIO <= p['t'] < FIN):
            continue
        if ventana == 'real' and horizonte(p) is None:
            continue
        if ventana == 'anunciado' and not (p['minutos'] <= 29 and 0 <= p['real'] - p['t'] < 3600):
            continue
        if variante == 'sin_305' and p['parada'] == '305':
            continue
        if p['parada'] in excluidas and variante != 'con_excluidas':
            continue
        if paso_fallido(p) and variante != 'con_excluidas':
            continue
        if variante == 'gps' and (p.get('real_gps') is None or horizonte(p, 'gps') is None):
            continue
        if variante != 'todos' and p.get('capa') != 'feed':
            continue
        if variante not in ('todos', 'feed', 'estricta') and not identidad_confirmada(p):
            continue
        if variante == 'estricta' and not identidad_confirmada(p, 300, (0.9, 1.6)):
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
                  'sesgo': statistics.median(e), 'antes': sum(x > 120 for x in e) / n, 'cola': sum(x > 600 for x in a) / n}
    return out


def bootstrap_dif(pares, agrupar, remuestreos, semilla=7, umbral=120, a='bide', b='oficial', **kw):
    """IC 95 % (percentil) de la diferencia a − b en la proporción a ±umbral, remuestreando grupos enteros."""
    grupos = collections.defaultdict(lambda: [0, 0, 0])
    for p in pares:
        e = errores(p, **kw)
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
    return cuantil(difs, 0.025), cuantil(difs, 0.975), len(lista)


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
    """El viajero llega a la parada k minutos antes de la hora prevista. Si el autobús ya ha pasado, espera al siguiente
    de la misma línea (si no se conoce, el par no cuenta). Devuelve, por fuente: (proporción que lo pierde, espera media
    contando las pérdidas, espera media cuando no lo pierde), en minutos, y el número de pares."""
    out = {}
    usados = [p for p in pares if p.get('siguiente') is not None and p['siguiente'] - p['real'] <= 7200]
    for f in FUENTES:
        pierde, todas, sin_perder = 0, [], []
        for p in usados:
            llegada = p['real'] + errores(p)[f] - 60 * minutos_antes
            if p['real'] < llegada:
                pierde += 1
                todas.append((p['siguiente'] - llegada) / 60)
            else:
                espera = (p['real'] - llegada) / 60
                todas.append(espera)
                sin_perder.append(espera)
        out[f] = (pierde / len(usados), sum(todas) / len(todas), sum(sin_perder) / len(sin_perder))
    return out, len(usados)


def fila(nombre, r, n=None):
    celdas = ['%.0f & %.0f & %.0f' % (r[f]['mediana'], 100 * r[f]['p2'], 100 * r[f]['antes']) for f in FUENTES]
    return '%s & %s & %s \\\\' % (nombre, '{:,}'.format(n if n is not None else r['oficial']['n']), ' & '.join(celdas))


def nombre_dia(d, aparte):
    return '%s %d%s' % (DIAS_SEMANA[datetime.date.fromisoformat(d).weekday()], int(d[8:]), '*' if d in aparte else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('carpeta')
    ap.add_argument('--ablacion', action='append', default=[], help='nombre=carpeta, se puede repetir')
    ap.add_argument('--tex')
    ap.add_argument('--remuestreos', type=int, default=2000)
    a = ap.parse_args()
    R = a.remuestreos
    cfg = config()
    aparte = set(cfg['aparte'])
    excluidas = set(cfg.get('paradas_excluidas', {}))
    tex = collections.defaultdict(list)
    semana, separado = cargar(a.carpeta)
    print('[texto] Conjunto principal: %d pares, %d pasos, %d viajes, %d vehículos, %d líneas, %d paradas' % (
        len(semana), len({clave_paso(p) for p in semana}), len({clave_viaje(p) for p in semana}),
        len({p['vehiculo'] for p in semana}), len({p['linea'] for p in semana}), len({p['parada'] for p in semana})))

    # 1. Flujo y cobertura.
    print('\n== Flujo')
    todos = [p for p in leer(a.carpeta)]
    cobertura = collections.Counter()
    for f in sorted(glob.glob(os.path.join(a.carpeta, 'pares-*.jsonl.cuentas.json'))):
        c = json.load(open(f))
        d = c['dia']
        ps = [p for p in todos if p['dia'] == d and INICIO <= p['t'] < FIN]
        en30 = [p for p in ps if horizonte(p) is not None]
        feed = [p for p in en30 if p['capa'] == 'feed']
        valido = [p for p in feed if p['parada'] not in excluidas and not paso_fallido(p)]
        conf = [p for p in valido if identidad_confirmada(p)]
        r = (nombre_dia(d, aparte), c['consultas'] - c.get('consultas_antes_6', 0), len(ps), len(ps) - len(en30),
             len(en30), len(en30) - len(feed), len(feed) - len(valido), len(valido) - len(conf), len(conf))
        print('  %-8s consultas %6d emparejados %6d fuera_de_30 %6d en_30 %6d sin_feed %6d excl %5d sin_conf %6d principal %6d' % r)
        tex['flujo'].append('%s & %s \\\\' % (r[0], ' & '.join('{:,}'.format(x) for x in r[1:])))
        if d not in aparte:
            cobertura['anuncios'] += c.get('e1_menos_30', 0)
            cobertura['emparejados'] += sum(1 for p in en30 if p['e'] == 1 and p['minutos'] < 30)
            cobertura['principal'] += sum(1 for p in conf if p['e'] == 1 and p['minutos'] < 30)
    if cobertura['anuncios']:
        print('[texto] Cobertura (anuncios del primer autobús a menos de 30 min, 06–23 h, días normales): %d; emparejados '
              '%.1f %%; en el conjunto principal %.1f %%' % (cobertura['anuncios'], 100 * cobertura['emparejados'] / cobertura['anuncios'],
                                                           100 * cobertura['principal'] / cobertura['anuncios']))
    elegibles = [p for p in todos if p['dia'] not in aparte and INICIO <= p['t'] < FIN and horizonte(p) and p['capa'] == 'feed'
                 and p['parada'] not in excluidas]
    fallidos = [p for p in elegibles if paso_fallido(p)]
    print('[texto] Pasos fallidos entre los elegibles: %d de %d (%.2f %%); en Zabalburu (305) %d; con GPS disponible %.1f %% de los elegibles' % (
        len(fallidos), len(elegibles), 100 * len(fallidos) / len(elegibles), sum(p['parada'] == '305' for p in fallidos),
        100 * sum(p.get('real_gps') is not None for p in elegibles) / len(elegibles)))
    print('[texto] Antigüedad de la copia de Bide+: mediana %.0f s; latencia del servicio oficial: mediana %.2f s (pares principales), %.2f s (todas las consultas emparejadas)' % (
        statistics.median(p['t'] - p['instante'] for p in semana), statistics.median(p['segundos_oficial'] for p in semana if p.get('segundos_oficial') is not None),
        statistics.median(p['segundos_oficial'] for p in todos if p.get('segundos_oficial') is not None)))
    razones = [p['metros_oficial'] / p['metros_bus'] for p in todos if p.get('capa') == 'feed' and p.get('metros_bus') and p['metros_bus'] > 1000 and p.get('metros_oficial')]
    print('[texto] Razón distancia oficial / línea recta (autobús a más de 1 km): p10 %.2f, mediana %.2f, p90 %.2f' % (
        cuantil(razones, 0.1), cuantil(razones, 0.5), cuantil(razones, 0.9)))
    rech = collections.defaultdict(lambda: [0, 0])
    for p in elegibles:
        if not paso_fallido(p):
            rech[p['parada']][0] += 1
            rech[p['parada']][1] += not identidad_confirmada(p)
    tasas = sorted(100 * r[1] / r[0] for r in rech.values() if r[0] >= 100)
    print('[texto] Rechazo por la comprobación de identidad, por parada: mediana %.0f %%, mín %.0f %%, máx %.0f %%' % (
        statistics.median(tasas), tasas[0], tasas[-1]))
    acuerdo = [p['real_gps'] - p['real'] for p in semana if p.get('real_gps') is not None]
    print('[texto] Paso por GPS − paso por el feed (principal, %d pares con GPS): p10 %.0f s, mediana %.0f s, p90 %.0f s; |dif| ≤ 60 s en %.0f %%' % (
        len(acuerdo), cuantil(acuerdo, 0.1), cuantil(acuerdo, 0.5), cuantil(acuerdo, 0.9), 100 * sum(abs(x) <= 60 for x in acuerdo) / len(acuerdo)))

    # 2. Por horizonte real.
    print('\n== Por minutos hasta el paso real')
    por_h = collections.defaultdict(list)
    for p in semana:
        por_h[horizonte(p)].append(p)
    for _, _, h in HORIZONTES:
        r = resumen(por_h[h])
        print('  %-7s n=%6d | %s' % (h, len(por_h[h]), ' | '.join('%s med %4.0f ±1 %3.0f ±2 %3.0f ±3 %3.0f sesgo %+5.0f antes %3.0f cola %.1f mae %.0f' % (
            NOMBRES[f], r[f]['mediana'], 100 * r[f]['p1'], 100 * r[f]['p2'], 100 * r[f]['p3'], r[f]['sesgo'], 100 * r[f]['antes'], 100 * r[f]['cola'], r[f]['mae']) for f in FUENTES)))
        tex['horizonte'].append(fila(h, r))
        tex['horizonte_extra'].append('%s & %s \\\\' % (h, ' & '.join('%.0f & %+.0f' % (100 * r[f]['p1'], r[f]['sesgo']) for f in FUENTES)))
        tex['colas'].append('%s & %s \\\\' % (h, ' & '.join('%.0f & %.1f' % (r[f]['mae'], 100 * r[f]['cola']) for f in FUENTES)))
    r = resumen(semana)
    tex['horizonte'].append('\\midrule\n' + fila('All', r))
    tex['horizonte_extra'].append('\\midrule\nAll & %s \\\\' % ' & '.join('%.0f & %+.0f' % (100 * r[f]['p1'], r[f]['sesgo']) for f in FUENTES))
    print('[texto] Todo: %s' % ' | '.join('%s ±2 %.1f' % (NOMBRES[f], 100 * r[f]['p2']) for f in FUENTES))

    # 3. Inferencia.
    print('\n== Bide+ − oficial a ±2 min: IC 95 %% (%d remuestreos) y prueba pareada de |error|' % R)
    for _, _, h in HORIZONTES + [(0, 0, 'All')]:
        ps = semana if h == 'All' else por_h[h]
        lo1, hi1, gv = bootstrap_dif(ps, clave_viaje, R)
        lo2, hi2, gp = bootstrap_dif(ps, lambda p: p['parada'], R)
        m, et, z = prueba_pareada(ps, lambda p: p['parada'])
        m2, et2, z2 = prueba_pareada(ps, lambda p: (p['parada'], p['dia']))
        print('  %-7s viajes [%+.1f, %+.1f] (%d)  paradas [%+.1f, %+.1f] (%d)  d = %.0f s (ET parada %.0f, z %.1f; ET parada-día %.0f, z %.1f)' % (
            h, 100 * lo1, 100 * hi1, gv, 100 * lo2, 100 * hi2, gp, m, et, z, et2, z2))
        tex['inferencia'].append('%s & $[%+.1f, %+.1f]$ & $[%+.1f, %+.1f]$ & %.0f & %.1f & %.1f \\\\' % (
            h, 100 * lo1, 100 * hi1, 100 * lo2, 100 * hi2, m, z, z2))

    # 4. Por minutos anunciados (población definida por el anuncio, paso hasta 60 min).
    print('\n== Por minutos anunciados (oficial, ≤ 29 min; paso en la hora siguiente)')
    anun, _ = cargar(a.carpeta, ventana='anunciado')
    por_a = collections.defaultdict(list)
    for p in anun:
        por_a[anunciado(p)].append(p)
    for _, _, h in ANUNCIADOS:
        if por_a[h]:
            r = resumen(por_a[h])
            print('  %-7s n=%6d | %s' % (h, len(por_a[h]), ' | '.join('%s ±2 %3.0f antes %3.0f' % (NOMBRES[f], 100 * r[f]['p2'], 100 * r[f]['antes']) for f in FUENTES)))
            tex['anunciado'].append(fila(h, r))
    r = resumen(anun)
    tex['anunciado'].append('\\midrule\n' + fila('All', r))
    print('[texto] Por anuncio, todos: %d pares | %s' % (len(anun), ' | '.join('%s ±2 %.1f' % (NOMBRES[f], 100 * r[f]['p2']) for f in FUENTES)))

    # 5. Verdad: desplazamientos y paso por GPS.
    print('\n== Desplazamiento del paso real (±2 min, todo y 10–20 min)')
    for s in range(-180, 181, 30):
        r = resumen(semana, desplazamiento=s)
        r10 = resumen(por_h['10--20'], desplazamiento=s)
        tex['desplazamiento_dat'].append('%d %.1f %.1f %.1f %.1f %.1f' % (s, 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'],
                                                                         100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
        print('  %+4d s: hor %.1f ofi %.1f bide %.1f | 10–20: ofi %.1f bide %.1f' % (s, 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'],
                                                                            100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
    gps, _ = cargar(a.carpeta, 'gps')
    print('\n== Con el paso por GPS como verdad (%d pares)' % len(gps))
    por_hg = collections.defaultdict(list)
    for p in gps:
        por_hg[horizonte(p, 'gps')].append(p)
    for _, _, h in HORIZONTES:
        r = resumen(por_hg[h], verdad='gps')
        lo, hi, _ = bootstrap_dif(por_hg[h], clave_viaje, R, verdad='gps')
        print('  %-7s n=%6d hor %.1f ofi %.1f bide %.1f  IC [%+.1f, %+.1f]' % (h, len(por_hg[h]), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * lo, 100 * hi))
        tex['gps'].append('%s & %s & %.0f & %.0f & %.0f & $[%+.1f, %+.1f]$ \\\\' % (h, '{:,}'.format(len(por_hg[h])), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * lo, 100 * hi))
    r = resumen(gps, verdad='gps')
    tex['gps'].append('\\midrule\nAll & %s & %.0f & %.0f & %.0f & -- \\\\' % ('{:,}'.format(len(gps)), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2']))

    # 6. Sensibilidad.
    print('\n== Sensibilidad (±2 min, todos los horizontes y 10–20 min)')
    variantes = [
        ('Main analysis', semana, {}),
        ('Actual passage $-60$ s', semana, {'desplazamiento': -60}),
        ('Actual passage $+60$ s', semana, {'desplazamiento': 60}),
        ('Actual passage from GPS', gps, {'verdad': 'gps'}),
        ('Official $+30$ s (minutes truncated)', semana, {'oficial_extra': 30}),
        ('Bide+ in seconds', semana, {'bide': 'segundos'}),
        ('Bide+ minutes truncated', semana, {'bide': 'suelo'}),
    ]
    for nombre, var in (('Stricter identity check', 'estricta'), ('No identity check', 'feed'),
                        ('No identity check, with fallback', 'todos'), ('Without Zabalburu (305)', 'sin_305'),
                        ('With stop 3394 and failed passages', 'con_excluidas')):
        variantes.append((nombre, cargar(a.carpeta, var)[0], {}))
    rnd = random.Random(11)
    por_paso = collections.defaultdict(list)
    for p in semana:
        por_paso[clave_paso(p)].append(p)
    variantes.append(('One pair per passage (random)', [rnd.choice(v) for v in por_paso.values()], {}))
    variantes.append(('Without priority stops', [p for p in semana if not p['prioritaria']], {}))
    variantes.append(('Bide+ with live position only', [p for p in semana if p['estado'] == 'live'], {}))
    for nombre, ps, kw in variantes:
        verdad = kw.get('verdad', 'feed')
        r = resumen(ps, **kw)
        r10 = resumen([p for p in ps if horizonte(p, verdad) == '10--20'], **kw)
        print('  %-40s n=%7d | todo: hor %4.1f ofi %4.1f bide %4.1f | 10–20: ofi %4.1f bide %4.1f' % (
            nombre, len(ps), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
        tex['sensibilidad'].append('%s & %s & %.0f & %.0f & %.0f & %.0f & %.0f \\\\' % (
            nombre, '{:,}'.format(len(ps)), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2'], 100 * r10['oficial']['p2'], 100 * r10['bide']['p2']))
    r = resumen(semana)
    tex['metricas'].append('Within $\\pm1$ min (\\%%) & %.0f & %.0f & %.0f \\\\' % (100 * r['horario']['p1'], 100 * r['oficial']['p1'], 100 * r['bide']['p1']))
    tex['metricas'].append('Within $\\pm2$ min (\\%%) & %.0f & %.0f & %.0f \\\\' % (100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2']))
    tex['metricas'].append('Within $\\pm3$ min (\\%%) & %.0f & %.0f & %.0f \\\\' % (100 * r['horario']['p3'], 100 * r['oficial']['p3'], 100 * r['bide']['p3']))
    tex['metricas'].append('Median absolute error (s) & %.0f & %.0f & %.0f \\\\' % (r['horario']['mediana'], r['oficial']['mediana'], r['bide']['mediana']))
    tex['metricas'].append('Mean absolute error (s) & %.0f & %.0f & %.0f \\\\' % (r['horario']['mae'], r['oficial']['mae'], r['bide']['mae']))
    tex['metricas'].append('More than 10 min off (\\%%) & %.1f & %.1f & %.1f \\\\' % (100 * r['horario']['cola'], 100 * r['oficial']['cola'], 100 * r['bide']['cola']))

    # 7. Modelo del viajero: pares cuyo anuncio oficial era de 3 a 29 minutos.
    print('\n== Modelo del viajero (anuncio oficial de 3 a 29 min)')
    ps = [p for p in anun if 3 <= p['minutos'] <= 29]
    for k in (1, 2, 3):
        m, n = modelo_viajero(ps, k)
        print('  %d min antes (%d pares): %s' % (k, n, ' | '.join('%s pierde %.0f %% espera %.1f (sin perder %.1f)' % (NOMBRES[f], 100 * m[f][0], m[f][1], m[f][2]) for f in FUENTES)))
        tex['viajero'].append('%d min & %s \\\\' % (k, ' & '.join('%.0f & %.1f' % (100 * m[f][0], m[f][1]) for f in FUENTES)))

    # 8. Grupos y días.
    print('\n== Grupos')
    grupos = [
        ('Weekdays', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() < 5]),
        ('Saturday', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() == 5]),
        ('Sunday', [p for p in semana if datetime.date.fromisoformat(p['dia']).weekday() == 6]),
        ('Priority stops', [p for p in semana if p['prioritaria']]),
        ('Other stops', [p for p in semana if not p['prioritaria']]),
        ('First bus ($e_1$)', [p for p in semana if p['e'] == 1]),
        ('Second bus ($e_2$)', [p for p in semana if p['e'] == 2]),
    ]
    for nombre, ps in grupos:
        if ps:
            tex['grupos'].append(fila(nombre, resumen(ps)))
            print('  %-20s n=%6d ofi %.1f bide %.1f' % (nombre, len(ps), 100 * resumen(ps)['oficial']['p2'], 100 * resumen(ps)['bide']['p2']))
    print('  estados de Bide+:', collections.Counter(p['estado'] for p in semana).most_common())
    print('  tipo (oficial):', collections.Counter(p.get('tipo', '') for p in semana).most_common(3))
    por_dia = collections.defaultdict(list)
    for p in semana + separado:
        por_dia[p['dia']].append(p)
    for d in sorted(por_dia):
        tex['dias'].append(fila(nombre_dia(d, aparte), resumen(por_dia[d])))
    print('\n== Pares y vehículos por hora (principal)')
    for h in range(6, 23):
        ps = [p for p in semana if int(p['t'] // 3600) == h]
        print('  %02d h: pares %6d vehículos %4d' % (h, len(ps), len({p['vehiculo'] for p in ps})))

    # 9. Paradas.
    por_parada = collections.defaultdict(list)
    for p in semana:
        if p['real'] - p['t'] >= 180:
            por_parada[p['parada']].append(p)
    gana = gana_ic = 0
    pierde = []
    for s, ps in por_parada.items():
        r = resumen(ps)
        if r['bide']['p2'] > r['oficial']['p2']:
            gana += 1
            lo, hi, _ = bootstrap_dif(ps, clave_viaje, R, semilla=3)
            gana_ic += lo > 0
        else:
            pierde.append((s, round(100 * r['horario']['p2']), round(100 * r['oficial']['p2']), round(100 * r['bide']['p2'])))
    print('\n[texto] Paradas: Bide+ mejor en %d de %d; con el IC 95 %% (%d remuestreos) por encima de cero en %d; pierde en %s' % (
        gana, len(por_parada), R, gana_ic, pierde))
    cortos = [p for p in semana if p['real'] - p['t'] < 360 and abs(errores(p)['bide']) > 600]
    print('[texto] Errores de Bide+ de más de 10 min con el autobús a menos de 6 min: %d, en Zabalburu %d; estados %s' % (
        len(cortos), sum(p['parada'] == '305' for p in cortos), collections.Counter(p['estado'] for p in cortos).most_common(3)))

    # 10. Ablación.
    if a.ablacion:
        print('\n== Ablación (mismos pares)')
        alt = {}
        for item in a.ablacion:
            nombre, carpeta = item.split('=', 1)
            alt[nombre] = {(p['dia'], p['vehiculo'], p['viaje'], p['parada'], p['t'], p['e']): p for p in leer(carpeta)}
        orden = [n for n in ('todo', 'tramos', 'ritmo', 'viajes') if n in alt]
        for _, _, h in HORIZONTES + [(0, 0, 'All')]:
            ps = semana if h == 'All' else por_h[h]
            claves = [(p['dia'], p['vehiculo'], p['viaje'], p['parada'], p['t'], p['e']) for p in ps]
            comunes = [(p, c) for p, c in zip(ps, claves) if all(c in alt[n] for n in orden)]
            con = resumen([p for p, _ in comunes])
            celdas = [100 * resumen([alt[n][c] for _, c in comunes])['bide']['p2'] for n in orden]
            print('  %-7s n=%6d ofi %.1f Bide+ %.1f | %s' % (h, len(comunes), 100 * con['oficial']['p2'], 100 * con['bide']['p2'],
                                                         ' '.join('%s %.1f' % (n, v) for n, v in zip(orden, celdas))))
            tex['ablacion'].append('%s%s & %s & %.0f & %s & %.0f \\\\' % ('\\midrule\n' if h == 'All' else '', h, '{:,}'.format(len(comunes)),
                                                                     100 * con['oficial']['p2'], ' & '.join('%.0f' % v for v in celdas), 100 * con['bide']['p2']))

    if a.tex:
        os.makedirs(a.tex, exist_ok=True)
        for clave, filas in tex.items():
            nombre = clave.replace('_dat', '') + ('.dat' if clave.endswith('_dat') else '.tex')
            with open(os.path.join(a.tex, nombre), 'w', encoding='utf-8') as f:
                if clave.endswith('_dat'):
                    f.write('s hor ofi met ofi10 met10\n')
                f.write('\n'.join(filas) + '\n')


if __name__ == '__main__':
    main()
