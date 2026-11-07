"""Captura para comparar las llegadas del método con los tiempos de espera oficiales de Bizkaibus.

Guarda, a la vez:
- el feed SIRI de posiciones de Bizkaibus cada 20 s (vm_AAAAMMDD-HHMMSS.xml), del que sale el paso real de cada
  autobús por cada parada y con el que se recalculan las predicciones del método (referencia/evaluar.py);
- los tiempos de espera oficiales (GetPasoParadaMobile_JSON, el servicio de la app de Bizkaibus) de las paradas de
  paradas.json cada 60 s, una línea JSON por parada y consulta (oficial.jsonl).

No consulta la API de Bide+: las predicciones del método se recalculan después con la implementación de referencia.
Solo biblioteca estándar; funciona igual en Linux, macOS y Windows.

Uso: python3 comparacion/capturar.py --minutos 330 --salida <carpeta>
"""
import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
MADRID = ZoneInfo('Europe/Madrid')
FEED = 'https://ctb-siri.s3.eu-south-2.amazonaws.com/bizkaibus-vehicle-positions.xml'
OFICIAL = 'http://apli.bizkaia.net/APPS/DANOK/TQWS/TQ.ASMX/GetPasoParadaMobile_JSON'
AGENTE = 'bide-eta (investigación abierta; https://github.com/Garridoparrayeray/bide-eta)'
TIEMPO_MAXIMO = 15                # s por petición
PAUSA_ENTRE_PARADAS = 0.2         # s: las paradas se piden una detrás de otra, sin prisa


def pedir(url):
    peticion = urllib.request.Request(url, headers={'User-Agent': AGENTE})
    with urllib.request.urlopen(peticion, timeout=TIEMPO_MAXIMO) as respuesta:
        return respuesta.read()


def leer_oficial(cuerpo):
    """El servicio responde «?({...});» con comillas simples y el resultado en XML dentro."""
    texto = cuerpo.decode('utf-8', errors='replace')
    objeto = json.loads(texto[texto.index('{'):texto.rindex('}') + 1].replace("'", '"'))
    if str(objeto.get('STATUS')) != 'OK':
        return objeto.get('STATUS'), []
    raiz = ET.fromstring(objeto['Resultado'])
    lineas = []
    for paso in raiz.findall('PasoParada'):
        fila = {'linea': paso.findtext('linea'), 'ruta': paso.findtext('ruta')}
        for e in ('e1', 'e2'):
            minutos = paso.findtext(e + '/minutos')
            metros = paso.findtext(e + '/metros')
            if minutos not in (None, ''):
                fila[e] = {'minutos': int(minutos), 'metros': int(metros) if metros not in (None, '') else None,
                           'tipo': paso.findtext(e + '/tipo') or ''}
        lineas.append(fila)
    return 'OK', lineas


def guardar_feed(carpeta):
    ahora = datetime.datetime.now(MADRID)
    try:
        cuerpo = pedir(FEED)
    except Exception as error:
        print('%s feed: %s' % (ahora.strftime('%H:%M:%S'), error), file=sys.stderr)
        return
    with open(os.path.join(carpeta, 'vm_%s.xml' % ahora.strftime('%Y%m%d-%H%M%S')), 'wb') as f:
        f.write(cuerpo)


def guardar_oficial(carpeta, paradas):
    with open(os.path.join(carpeta, 'oficial.jsonl'), 'a', encoding='utf-8') as salida:
        for parada, codigo in paradas:
            antes = time.time()
            fila = {'t': round(antes, 1), 'hora': datetime.datetime.now(MADRID).isoformat(timespec='seconds'), 'parada': parada}
            try:
                url = OFICIAL + '?' + urllib.parse.urlencode({'callback': '?', 'strLinea': '', 'strParada': codigo})
                fila['estado'], fila['lineas'] = leer_oficial(pedir(url))
            except Exception as error:
                fila['estado'], fila['error'] = 'ERROR', str(error)[:200]
            fila['segundos'] = round(time.time() - antes, 2)
            salida.write(json.dumps(fila, ensure_ascii=False) + '\n')
            time.sleep(PAUSA_ENTRE_PARADAS)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--minutos', type=float, default=330)
    p.add_argument('--salida', required=True)
    p.add_argument('--paradas', default=os.path.join(AQUI, 'paradas.json'))
    p.add_argument('--feed-cada', type=int, default=20, help='segundos entre lecturas del feed')
    p.add_argument('--oficial-cada', type=int, default=60, help='segundos entre consultas de cada parada')
    a = p.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    # El servicio oficial pide el código con cuatro cifras (0356); se guarda con el número del horario (356).
    paradas = [(x['id'], x['codigo_oficial']) for x in json.load(open(a.paradas, encoding='utf-8'))['paradas']]
    fin = time.time() + a.minutos * 60
    # Dos hilos: la tanda de paradas tarda casi un minuto y no debe retrasar las lecturas del feed.
    hilos = [threading.Thread(target=cada, args=(a.feed_cada, fin, guardar_feed, a.salida)),
             threading.Thread(target=cada, args=(a.oficial_cada, fin, guardar_oficial, a.salida, paradas))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    consultas = sum(1 for _ in open(os.path.join(a.salida, 'oficial.jsonl'), encoding='utf-8'))
    print('fin: %d lecturas del feed, %d consultas oficiales' % (
        len([n for n in os.listdir(a.salida) if n.startswith('vm_')]), consultas))


def cada(segundos, fin, tarea, *argumentos):
    """Repite la tarea cada tantos segundos hasta el final, sin acumular retraso."""
    proxima = time.time()
    while proxima < fin:
        tarea(*argumentos)
        proxima += segundos
        time.sleep(max(0.0, proxima - time.time()))


if __name__ == '__main__':
    main()
