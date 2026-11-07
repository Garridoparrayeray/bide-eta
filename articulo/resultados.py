"""Las tablas de resultados del artículo, a partir de los datos públicos de evaluación (datos/evaluacion/).

- eta-eval-historial.jsonl: resúmenes por bloque de captura del 15 al 31 de octubre de 2026 (formato resumen-log-v1).
- eta-eval.jsonl: histogramas del error en barras de 15 s desde el 31 de octubre (formato histograma-v1), con los tres
  modos de la evaluación: normal, sin GPS (las posiciones se borran) y sin feed (solo el horario corregido).

Uso: python3 articulo/resultados.py [--latex]
"""
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, '..', 'datos', 'evaluacion')
HORIZONTES = ['0-3', '3-6', '6-10', '10-20']
CUBO = 15


def dentro(h, segundos):
    """Fracción de errores en [-segundos, segundos): las barras de 15 s enteras que caben."""
    n = sum(h.values())
    lo, hi = -segundos // CUBO, segundos // CUBO - 1
    return sum(v for k, v in h.items() if lo <= int(k) <= hi) / n


def mediana_abs(h):
    """Error absoluto mediano, con la resolución de las barras (el primer múltiplo de 15 s que deja la mitad dentro)."""
    for s in range(CUBO, 3600, CUBO):
        if dentro(h, s) >= 0.5:
            return s
    return None


def histogramas(filtro):
    juntos = collections.defaultdict(collections.Counter)
    dias = set()
    for l in open(os.path.join(DATOS, 'eta-eval.jsonl')):
        r = json.loads(l)
        if not filtro(r):
            continue
        dias.add(r['fecha'])
        for fuente in ('app', 'horario'):
            h = r.get(fuente) or {}
            if not isinstance(h, dict):
                continue
            for k, v in h.items():
                juntos[(r['horizonte'], fuente)][int(k)] += v
    return juntos, sorted(dias)


def periodo_octubre():
    suma = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    dias = set()
    for l in open(os.path.join(DATOS, 'eta-eval-historial.jsonl')):
        r = json.loads(l)
        if not r.get('predicciones'):
            continue
        dias.add(r['fecha'])
        for hz, fuentes in (r.get('horizontes') or {}).items():
            for fuente, m in fuentes.items():
                if not m.get('n') or m.get('dentro_2') is None:
                    continue
                s = suma[(hz, fuente)]
                s[0] += m['n']
                for i, c in enumerate(('dentro_1', 'dentro_2', 'dentro_3')):
                    v = m[c]
                    if v > 1:
                        v = v / 100
                    s[i + 1] += m['n'] * v
    filas = {}
    for (hz, fuente), (n, d1, d2, d3) in suma.items():
        filas[(hz, fuente)] = (n, d1 / n, d2 / n, d3 / n)
    return filas, sorted(dias)


def tabla_horizontes(titulo, filas):
    print('\n' + titulo)
    print('%-6s | %-26s | %-26s' % ('min', 'método ±1/±2/±3 (n)', 'horario ±1/±2/±3'))
    for hz in HORIZONTES:
        a, h = filas.get((hz, 'app')), filas.get((hz, 'horario'))
        if a is None:
            continue
        print('%-6s | %3.0f %3.0f %3.0f %% (%7d) | %3.0f %3.0f %3.0f %%' % (
            hz, 100 * a[1], 100 * a[2], 100 * a[3], a[0], 100 * h[1], 100 * h[2], 100 * h[3]))


def de_histogramas(juntos):
    filas = {}
    for (hz, fuente), h in juntos.items():
        filas[(hz, fuente)] = (sum(h.values()), dentro(h, 60), dentro(h, 120), dentro(h, 180), mediana_abs(h))
    return filas


def main():
    octubre, dias_oct = periodo_octubre()
    tabla_horizontes('Periodo 1: %s a %s (%d días con predicciones)' % (dias_oct[0], dias_oct[-1], len(dias_oct)), octubre)

    for modo in ('normal', 'sin-gps', 'sin-feed'):
        juntos, dias = histogramas(lambda r, m=modo: r['modo'] == m)
        filas = de_histogramas(juntos)
        tabla_horizontes('Periodo 2, modo %s: %s a %s (%d días)' % (modo, dias[0], dias[-1], len(dias)), filas)
        if modo == 'normal':
            print('error absoluto mediano (s): ' + ', '.join('%s %s' % (hz, filas[(hz, 'app')][4]) for hz in HORIZONTES))

    print('\nPeriodo 2, modo normal, por capa (±2 min; parte de las predicciones):')
    total = collections.Counter()
    por_capa = {}
    for capa in (1, 2, 3):
        juntos, _ = histogramas(lambda r, c=capa: r['modo'] == 'normal' and r['capa'] == c)
        por_capa[capa] = juntos
        for hz in HORIZONTES:
            total[hz] += sum(juntos[(hz, 'app')].values())
    for capa in (1, 2, 3):
        partes = []
        for hz in HORIZONTES:
            h = por_capa[capa][(hz, 'app')]
            n = sum(h.values())
            if n:
                partes.append('%s: %3.0f %% de %4.1f %%' % (hz, 100 * dentro(h, 120), 100 * n / total[hz]))
        print('  capa %d | %s' % (capa, ' | '.join(partes)))

    print('\nPeriodo 2, modo normal, por tipo de día (±2 min):')
    for tipo in ('laborable', 'fin_semana'):
        juntos, dias = histogramas(lambda r, t=tipo: r['modo'] == 'normal' and r['tipo_dia'] == t)
        filas = de_histogramas(juntos)
        print('  %-10s (%d días) | %s' % (tipo, len(dias), ' | '.join('%s %3.0f %%' % (hz, 100 * filas[(hz, 'app')][2]) for hz in HORIZONTES)))


if __name__ == '__main__':
    main()
