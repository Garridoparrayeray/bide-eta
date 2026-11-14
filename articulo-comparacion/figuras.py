"""Datos de las figuras del artículo 2 (ficheros .dat para pgfplots) a partir de los pares de comparar.py.

Uso: python3 figuras.py <carpeta con pares-AAAAMMDD.jsonl> <carpeta de salida>

Usa el conjunto principal de resultados.py (días normales, paradas no excluidas, autobús en el feed e identidad
confirmada por la distancia oficial). Bide+ va redondeado a minutos, como en la app.
"""
import collections
import datetime
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
    semana, separado = RS.cargar(entrada)
    for p in semana + separado:
        e = RS.errores(p)
        p['eo'], p['em'], p['eh'] = e['oficial'], e['bide'], e['horario']

    # 1. Por minuto hasta el paso real: ±2 min de las tres fuentes y IC 95 % por viajes de la diferencia Bide+ − oficial.
    por_min = collections.defaultdict(list)
    for p in semana:
        por_min[int((p['real'] - p['t']) // 60)].append(p)
    filas = []
    for m in range(30):
        ps = por_min[m]
        lo, hi, _ = RS.bootstrap_dif(ps, RS.clave_viaje, 1000, semilla=m)
        filas.append((m + 0.5, round(p2([p['eh'] for p in ps]), 1), round(p2([p['eo'] for p in ps]), 1),
                      round(p2([p['em'] for p in ps]), 1), round(100 * lo, 1), round(100 * hi, 1), len(ps)))
    escribir(os.path.join(salida, 'minutos.dat'), 'min hor ofi met diflo difhi n', filas)

    # 2. Función de distribución del error absoluto con el autobús a 10–20 minutos (de 0 a 15 min).
    sel = [p for p in semana if 600 <= p['real'] - p['t'] < 1200]
    filas = []
    for s in range(0, 901, 15):
        filas.append((round(s / 60, 2), round(100 * sum(abs(p['eh']) <= s for p in sel) / len(sel), 2),
                      round(100 * sum(abs(p['eo']) <= s for p in sel) / len(sel), 2),
                      round(100 * sum(abs(p['em']) <= s for p in sel) / len(sel), 2)))
    escribir(os.path.join(salida, 'cdf.dat'), 'min hor ofi met', filas)
    # y el error con signo (cubos de 30 s entre −10 y +10 min; fuera de ese rango no se dibuja, se da en el pie)
    co, cm, ch = collections.Counter(), collections.Counter(), collections.Counter()
    for p in sel:
        for c, k in ((co, 'eo'), (cm, 'em'), (ch, 'eh')):
            if -600 <= p[k] < 600:
                c[int(p[k] // 30)] += 1
    escribir(os.path.join(salida, 'errores.dat'), 'min ofi met hor',
             [((b * 30 + 15) / 60, round(100 * co[b] / len(sel), 2), round(100 * cm[b] / len(sel), 2), round(100 * ch[b] / len(sel), 2))
              for b in range(-20, 20)])
    with open(os.path.join(salida, 'errores-fuera.txt'), 'w') as f:
        for k, n in (('eh', 'horario'), ('eo', 'oficial'), ('em', 'bide')):
            f.write('%s %.1f %.1f\n' % (n, 100 * sum(p[k] < -600 for p in sel) / len(sel), 100 * sum(p[k] >= 600 for p in sel) / len(sel)))

    # 3. Por parada (3–30 min): ±2 de las fuentes y n.
    por_parada = collections.defaultdict(list)
    for p in semana:
        if p['real'] - p['t'] >= 180:
            por_parada[p['parada']].append(p)
    escribir(os.path.join(salida, 'paradas.dat'), 'ofi met n prioritaria hor',
             [(round(p2([p['eo'] for p in ps]), 1), round(p2([p['em'] for p in ps]), 1), len(ps), int(ps[0]['prioritaria']),
               round(p2([p['eh'] for p in ps]), 1)) for ps in por_parada.values() if len(ps) >= 100])

    # 4. Por hora (3–30 min) y 5. por día (3–30 min).
    por_hora = collections.defaultdict(list)
    for p in semana:
        if p['real'] - p['t'] >= 180:
            por_hora[int(p['t'] // 3600)].append(p)
    escribir(os.path.join(salida, 'horas.dat'), 'hora ofi met n hor',
             [(h, round(p2([p['eo'] for p in ps]), 1), round(p2([p['em'] for p in ps]), 1), len(ps), round(p2([p['eh'] for p in ps]), 1))
              for h, ps in sorted(por_hora.items()) if len(ps) >= 200])
    por_dia = collections.defaultdict(list)
    aparte = set(RS.config()['aparte'])
    for p in semana + separado:
        if p['real'] - p['t'] >= 180:
            por_dia[p['dia']].append(p)
    escribir(os.path.join(salida, 'dias.dat'), 'dia ofi met hor',
             [('{%s %d%s}' % (RS.DIAS_SEMANA[datetime.date.fromisoformat(d).weekday()], int(d[8:]), '*' if d in aparte else ''),
               round(p2([p['eo'] for p in v]), 1), round(p2([p['em'] for p in v]), 1), round(p2([p['eh'] for p in v]), 1))
              for d, v in sorted(por_dia.items())])

    # 6. Ejemplos: dos autobuses al azar de toda la red y uno al azar en cada sentido de San Juan (Amorebieta), paradas
    # 3388 y 3391, de las líneas 3513, 3514 y 3515 (semilla fija), entre los pasos con consultas desde 25 minutos antes.
    pasos = collections.defaultdict(list)
    for p in semana:
        if p['e'] == 1:
            pasos[RS.clave_paso(p)].append(p)
    def validos(filtro):
        return sorted(k for k, ps in pasos.items() if filtro(k, ps) and max(p['real'] - p['t'] for p in ps) >= 1500 and len(ps) >= 15)
    rnd = random.Random(2026)
    candidatos = validos(lambda k, ps: True)
    elegidos = rnd.sample(candidatos, 2)
    for parada in ('3388', '3391'):
        elegidos.append(rnd.choice(validos(lambda k, ps, s=parada: k[3] == s and ps[0]['linea'] in ('3513', '3514', '3515'))))
    with open(os.path.join(salida, 'ejemplos.txt'), 'w', encoding='utf-8') as f:
        for i, k in enumerate(elegidos, 1):
            ps = sorted(pasos[k], key=lambda p: p['t'])
            escribir(os.path.join(salida, 'ejemplo%d.dat' % i), 'antes ofi hor met',
                     [(round((p['real'] - p['t']) / 60, 2), round((p['oficial'] - p['t']) / 60, 2), round((p['horario'] - p['t']) / 60, 2),
                       round((p['t'] + 60 * max(0, RS.redondeo_php((p['metodo'] - p['t']) / 60)) - p['t']) / 60, 2)) for p in ps])
            f.write('%d %s línea %s parada %s vehículo %s\n' % (i, k[0], ps[0]['linea'], k[3], k[2]))
    # Y el resumen de San Juan (Amorebieta), líneas 3513–3515, los dos sentidos, de 3 a 30 minutos.
    sj = [p for p in semana if p['parada'] in ('3388', '3391') and p['linea'] in ('3513', '3514', '3515') and p['real'] - p['t'] >= 180]
    r = RS.resumen(sj)
    with open(os.path.join(salida, 'sanjuan.txt'), 'w', encoding='utf-8') as f:
        f.write('pares %d horario %.1f oficial %.1f bide %.1f\n' % (len(sj), 100 * r['horario']['p2'], 100 * r['oficial']['p2'], 100 * r['bide']['p2']))
    print('candidatos', len(candidatos), 'elegidos', elegidos)


if __name__ == '__main__':
    main()
