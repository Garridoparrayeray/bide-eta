"""Batería de pruebas de la memoria. Desde la carpeta memoria/:

    python3 pruebas/revisar.py               # compila y revisa todo
    python3 pruebas/revisar.py --sin-compilar

Cinco bloques. Los FALLOS hacen que la batería termine con error; los AVISOS se enseñan para revisarlos a mano.

1. Compilación: sin errores, referencias rotas, etiquetas duplicadas ni líneas que se salgan del margen.
2. Bibliografía: toda cita existe, toda entrada se cita, cada entrada tiene los campos de su tipo y figura en
   pruebas/referencias-verificadas.json con la fuente donde se comprobó.
3. Reproducibilidad: la implementación de referencia reproduce los vectores, el texto dice el mismo número de
   comprobaciones que da el programa y el PDF lleva adjuntos los ficheros.
4. Rastros de herramientas y de borrador: nombres de asistentes o modelos de IA, marcadores pendientes y frases de
   relleno típicas de un texto generado o poco revisado.
5. Ortotipografía en castellano: comillas, porcentajes, decimales, palabras repetidas y frases demasiado largas.
"""
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CAPITULOS = os.path.join(RAIZ, 'capitulos')

fallos = []
avisos = []


def fallo(bloque, texto):
    fallos.append((bloque, texto))


def aviso(bloque, texto):
    avisos.append((bloque, texto))


def ficheros_tex():
    rutas = [os.path.join(RAIZ, 'memoria.tex')]
    rutas += sorted(os.path.join(CAPITULOS, f) for f in os.listdir(CAPITULOS) if f.endswith('.tex'))
    return rutas


def leer(ruta):
    with open(ruta, encoding='utf-8') as f:
        return f.read()


def sin_comentarios(linea):
    return re.sub(r'(?<!\\)%.*$', '', linea)


def texto_corrido(fuente):
    """Quita lo que no es prosa: matemáticas, código, entornos de tablas y figuras, y órdenes con argumentos técnicos."""
    if '\\begin{document}' in fuente:
        fuente = fuente.split('\\begin{document}', 1)[1]
    s = '\n'.join(sin_comentarios(l) for l in fuente.split('\n'))
    for entorno in ['lstlisting', 'algorithmic', 'tikzpicture', 'equation', 'align', 'align\\*', 'gather\\*',
                    'tabular', 'tabularx', 'longtable']:
        s = re.sub(r'\\begin\{' + entorno + r'\}.*?\\end\{' + entorno + r'\}', ' ', s, flags=re.S)
    s = re.sub(r'\\\[.*?\\\]', ' ', s, flags=re.S)
    s = re.sub(r'\\(begin|end)\{[^}]*\}(\[[^]]*\])?(\{[^}]*\})?', '\n\n', s)
    s = re.sub(r'\$[^$]*\$', ' FORMULA ', s)
    s = re.sub(r'\\(texttt|ref|eqref|label|cite[pt]?|citealp|url|lstinputlisting|embedfile|include|input)(\[[^]]*\])*\{[^}]*\}', ' X ', s)
    return s


# ----------------------------------------------------------------------------------------------------- 1. compilación
def compilar():
    orden = ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'memoria.tex']
    r = subprocess.run(orden, cwd=RAIZ, capture_output=True)
    if r.returncode != 0:
        fallo('compilación', 'latexmk termina con error (mira memoria.log)')


def revisar_log():
    ruta = os.path.join(RAIZ, 'memoria.log')
    if not os.path.exists(ruta):
        fallo('compilación', 'no hay memoria.log: compila primero')
        return
    log = open(ruta, encoding='latin-1').read()
    for m in re.finditer(r'^! (.*)$', log, flags=re.M):
        fallo('compilación', 'error de LaTeX: ' + m.group(1))
    for m in re.finditer(r"LaTeX Warning: (Reference|Citation) `([^']+)' .*undefined", log):
        fallo('compilación', f'{m.group(1).lower()} sin definir: {m.group(2)}')
    for m in re.finditer(r"Package natbib Warning: Citation `([^']+)' .*undefined", log):
        fallo('compilación', f'cita sin definir: {m.group(1)}')
    for m in re.finditer(r"LaTeX Warning: Label `([^']+)' multiply defined", log):
        fallo('compilación', f'etiqueta duplicada: {m.group(1)}')
    for m in re.finditer(r'Overfull \\hbox \(([\d.]+)pt too wide\)', log):
        if float(m.group(1)) > 1.0:
            fallo('compilación', f'una línea se sale {m.group(1)} pt del margen')
    for m in re.finditer(r"Package biblatex Warning: The following entry could not be found\s*\(biblatex\)\s*in the database:\s*\(biblatex\)\s*(\S+)", log):
        fallo('compilación', f'cita sin entrada en la bibliografía: {m.group(1)}')
    if re.search(r'There were undefined references|Rerun to get cross-references right|Please \(re\)run Biber', log):
        aviso('compilación', 'LaTeX pide otra pasada')


# ---------------------------------------------------------------------------------------------------- 2. bibliografía
# Campos que pide APA 7 para cada tipo de entrada de biblatex.
CAMPOS = {
    'article': ['author', 'title', 'journal', 'volume', 'pages', 'date'],
    'book': ['author', 'title', 'publisher', 'date'],
    'incollection': ['author', 'title', 'booktitle', 'pages', 'publisher', 'date'],
    'report': ['author', 'title', 'number', 'date'],
    'online': ['author', 'title', 'url', 'urldate'],
}


def leer_bib():
    bib = leer(os.path.join(RAIZ, 'bibliografia.bib'))
    entradas = {}
    for m in re.finditer(r'@(\w+)\{([^,\s]+),(.*?)\n\}', bib, flags=re.S):
        campos = dict((k.lower(), v.strip()) for k, v in re.findall(r'(\w+)\s*=\s*(\{.*?\}|\d+)\s*,?\s*\n', m.group(3) + '\n', flags=re.S))
        entradas[m.group(2)] = (m.group(1).lower(), campos)
    return entradas


def revisar_bibliografia():
    entradas = leer_bib()
    citadas = set()
    for ruta in ficheros_tex():
        for m in re.finditer(r'\\cite(?:p|t|alp|alt|author|year)?\*?(?:\[[^]]*\])*\{([^}]*)\}', leer(ruta)):
            citadas.update(k.strip() for k in m.group(1).split(','))
    for clave in sorted(citadas - entradas.keys()):
        fallo('bibliografía', f'se cita «{clave}» y no está en bibliografia.bib')
    for clave in sorted(entradas.keys() - citadas):
        fallo('bibliografía', f'«{clave}» está en la bibliografía y no se cita en el texto')
    verificadas = json.load(open(os.path.join(AQUI, 'referencias-verificadas.json'), encoding='utf-8'))
    for clave, (tipo, campos) in sorted(entradas.items()):
        if tipo not in CAMPOS:
            fallo('bibliografía', f'«{clave}»: tipo de entrada @{tipo} sin revisar para APA')
        for campo in CAMPOS.get(tipo, ['author', 'title', 'date']):
            # APA 7: en las revistas que numeran artículos, el número de artículo (eid) ocupa el lugar de las páginas.
            if campo == 'pages' and 'eid' in campos:
                continue
            if campo not in campos:
                fallo('bibliografía', f'«{clave}» ({tipo}) no tiene {campo}')
        doi = campos.get('doi', '').strip('{}')
        if doi and not re.match(r'^10\.\d{4,9}/\S+$', doi):
            fallo('bibliografía', f'«{clave}»: DOI con formato incorrecto: {doi}')
        enlace = doi or campos.get('url', '').strip('{}') or re.sub(r'.*\\url\{([^}]*)\}.*', r'\1', campos.get('howpublished', ''))
        if not enlace.startswith(('10.', 'http')):
            fallo('bibliografía', f'«{clave}» no tiene DOI ni enlace para consultarla')
        info = verificadas.get(clave)
        if not info or not info.get('fuente') or not info.get('comprobado'):
            fallo('bibliografía', f'«{clave}» no consta como comprobada en referencias-verificadas.json')
        elif info.get('doi') and info['doi'] != doi:
            fallo('bibliografía', f'«{clave}»: el DOI comprobado ({info["doi"]}) no es el de la bibliografía ({doi})')


# ----------------------------------------------------------------------------------------------- 3. reproducibilidad
def revisar_reproducibilidad():
    carpeta = os.path.join(RAIZ, '..', 'referencia')
    r = subprocess.run([sys.executable, '-I', 'comprobar.py'], cwd=carpeta, capture_output=True, text=True)
    m = re.search(r'(\d+) de (\d+) comprobaciones', r.stdout)
    if r.returncode != 0 or not m or m.group(1) != m.group(2):
        fallo('reproducibilidad', 'la implementación de referencia no reproduce todos los vectores: ' + r.stdout.strip()[-200:])
        return
    total = m.group(2)
    textos = [(ruta, leer(ruta)) for ruta in ficheros_tex()] + [(os.path.join(RAIZ, 'README.md'), leer(os.path.join(RAIZ, 'README.md')))]
    for ruta, texto in textos:
        for n in re.findall(r'(\d+) de (\d+) comprobaciones', texto) + re.findall(r'\((\d+) de (\d+)\)', texto):
            if n[0] != total or n[1] != total:
                fallo('reproducibilidad', f'{os.path.basename(ruta)} dice «{n[0]} de {n[1]}» y el programa da {total} de {total}')
    pdf = os.path.join(RAIZ, 'memoria.pdf')
    try:
        lista = subprocess.run(['pdfdetach', '-list', pdf], capture_output=True, text=True).stdout
        for nombre in ['referencia.py', 'comprobar.py', 'vectores.json', 'desvio-horario.py']:
            if not re.search(r'\d+: ' + re.escape(nombre) + r'$', lista, flags=re.M):
                fallo('reproducibilidad', f'el PDF no lleva adjunto {nombre}')
    except FileNotFoundError:
        aviso('reproducibilidad', 'no está pdfdetach (Poppler): no se comprueban los adjuntos del PDF')


# ------------------------------------------------------------------------------------- 4. rastros de herramientas
HERRAMIENTAS = r'\b(Claude|ChatGPT|GPT-?\d|OpenAI|Anthropic|Copilot|Gemini|LLM|modelo de lenguaje|inteligencia artificial generativa|Generated with|Co-Authored-By)\b'
PENDIENTES = r'\b(TODO|FIXME|XXX|TBD|lorem ipsum)\b|\[cita requerida\]|\?\?'
# Frases de relleno o de énfasis vacío, frecuentes en textos generados o poco revisados. Un texto técnico dice el dato.
RELLENO = [
    r'cabe (destacar|señalar|mencionar|resaltar)', r'es importante (destacar|señalar|mencionar|tener en cuenta|recordar)',
    r'vale la pena', r'en resumen,', r'en conclusión,', r'en definitiva', r'sin lugar a dudas', r'sin duda',
    r'juegan? un papel', r'papel (crucial|fundamental|clave)', r'\bcrucial(es)?\b', r'a la hora de [a-záéíóú]+r\b', r'en el ámbito de',
    r'profundizar', r'adentr(arnos|arse)', r'sumerg', r'\bpanorama\b', r'\becosistema\b', r'\bpotenciar\b',
    r'aprovechar al máximo', r'de manera significativa', r'\bsignificativ', r'\binnovador', r'revolucion',
    r'hol[ií]stic', r'sinergi', r'exhaustiv', r'meticulos', r'\bseamless', r'resulta (fundamental|clave|esencial)',
    r'\bdesbloque', r'\bpoderos[oa]', r'de vital importancia', r'\b(es|son|resulta|resultan|factor|elemento|aspecto|papel|punto) clave\b',
    r'\bintegral\b',
    r'en este sentido', r'no solo .{1,80}? sino (también|que)', r'¡',
]


def revisar_rastros():
    rutas = ficheros_tex() + [os.path.join(RAIZ, 'bibliografia.bib'), os.path.join(RAIZ, 'README.md')]
    rutas += [os.path.join(RAIZ, '..', 'referencia', f) for f in os.listdir(os.path.join(RAIZ, '..', 'referencia')) if f.endswith('.py')]
    for ruta in rutas:
        for n, linea in enumerate(leer(ruta).split('\n'), 1):
            if re.search(HERRAMIENTAS, linea, flags=re.I):
                fallo('rastros', f'{os.path.basename(ruta)}:{n}: nombre de herramienta: {linea.strip()[:90]}')
            if re.search(PENDIENTES, sin_comentarios(linea)):
                fallo('rastros', f'{os.path.basename(ruta)}:{n}: marcador pendiente: {linea.strip()[:90]}')
    for ruta in ficheros_tex():
        texto = texto_corrido(leer(ruta))
        for patron in RELLENO:
            for m in re.finditer(patron, texto, flags=re.I | re.S):
                linea = texto[:m.start()].count('\n') + 1
                fallo('rastros', f'{os.path.basename(ruta)}:~{linea}: frase de relleno «{m.group(0)[:60]}»')
        # Comienzos de párrafo repetidos y conectores en cadena
        parrafos = [p.strip() for p in re.split(r'\n\s*\n', texto) if len(p.strip()) > 80]
        iniciales = [re.split(r'[\s,]', p, maxsplit=1)[0] for p in parrafos]
        for a, b, c in zip(iniciales, iniciales[1:], iniciales[2:]):
            if a == b == c and not a.startswith('\\') and a != 'X':
                aviso('rastros', f'{os.path.basename(ruta)}: tres párrafos seguidos empiezan por «{a}»')
        for conector in ['Además', 'Asimismo', 'Por otro lado', 'Por último', 'Es decir']:
            n = len(re.findall(r'\b' + conector + r'\b', texto))
            if n > 4:
                aviso('rastros', f'{os.path.basename(ruta)}: «{conector}» aparece {n} veces')


# ------------------------------------------------------------------------------------------------ 5. ortotipografía
def revisar_ortotipografia():
    for ruta in ficheros_tex():
        nombre = os.path.basename(ruta)
        fuente = leer(ruta)
        if nombre == '00-resumen.tex':
            # El «Abstract» está en inglés, con punto decimal.
            fuente = re.sub(r'\\seccionprincipal\{Abstract\}.*?\\seccionprincipal', r'\\seccionprincipal', fuente, flags=re.S)
        texto = texto_corrido(fuente)
        for n, linea in enumerate(texto.split('\n'), 1):
            if re.search(r'[“”]|(?<![\\`])"[A-Za-zÁÉÍÓÚáéíóúñ]', linea):
                fallo('ortotipografía', f'{nombre}:~{n}: comillas inglesas; en castellano, «angulares»')
            if re.search(r'\d%', linea):
                fallo('ortotipografía', f'{nombre}:~{n}: porcentaje sin espacio fino (escribir 12\\,\\%)')
            if re.search(r'(?<![\w.{])\d+\.\d+(?![\w.}])', re.sub(r'Versión \d+\.\d+|802\.3', '', linea)):
                aviso('ortotipografía', f'{nombre}:~{n}: posible decimal con punto en el texto: {linea.strip()[:80]}')
            for m in re.finditer(r'\b([a-záéíóúñ]{2,})\s+\1\b', linea, flags=re.I):
                fallo('ortotipografía', f'{nombre}:~{n}: palabra repetida «{m.group(0)}»')
            if '—' in linea:
                aviso('ortotipografía', f'{nombre}:~{n}: raya «—» en la prosa; revisar que sea un inciso necesario')
        prosa = re.sub(r'\\[a-zA-Z]+\*?(\[[^]]*\])?', ' ', texto)
        prosa = prosa.replace('{', ' ').replace('}', ' ')
        for frase in re.split(r'(?<=[.:;?!])\s+', prosa):
            palabras = re.findall(r'[A-Za-zÁÉÍÓÚáéíóúñÑüÜ]+', frase)
            if len(palabras) > 60:
                aviso('ortotipografía', f'{nombre}: frase de {len(palabras)} palabras: «{" ".join(palabras[:10])}…»')


# ----------------------------------------------------------------------------------------- 6. normas APA (7.ª edición)
NIVEL = {'chapter': 1, 'section': 2, 'subsection': 3, 'subsubsection': 4, 'paragraph': 5}
MENORES = {'a', 'al', 'con', 'de', 'del', 'e', 'el', 'en', 'la', 'las', 'lo', 'los', 'ni', 'o', 'por', 'que', 'sin',
           'su', 'sus', 'tras', 'u', 'un', 'una', 'y', 'and', 'of', 'the', 'vs'}
ORDEN = ['01-introduccion', '02-marco-teorico', '03-datos', '04-localizacion', '05-modelo', '06-prediccion',
         '07-aprendizaje', '08-resultados', '09-discusion', '10-conclusiones', 'A-constantes', 'B-algoritmos',
         'C-formatos', 'D-vectores', 'E-referencia', 'F-glosario']


def argumento(texto, inicio):
    """Texto del argumento entre llaves que empieza en texto[inicio] == '{'."""
    nivel = 0
    for posicion in range(inicio, len(texto)):
        if texto[posicion] == '{' and texto[posicion - 1] != '\\':
            nivel += 1
        elif texto[posicion] == '}' and texto[posicion - 1] != '\\':
            nivel -= 1
            if nivel == 0:
                return texto[inicio + 1:posicion]
    return ''


def palabras_titulo(titulo):
    """Palabras de un título sin matemáticas ni comandos."""
    titulo = re.sub(r'\$[^$]*\$|\\texttt\{[^{}]*\}|\\[a-zA-Z]+', ' ', titulo)
    return re.findall(r'[A-Za-zÁÉÍÓÚáéíóúñÑüÜ][\wÁÉÍÓÚáéíóúñÑüÜ-]*', titulo)


def mayusculas_apa(donde, titulo):
    """APA: cada palabra con mayúscula inicial, salvo artículos, preposiciones y conjunciones de tres letras o menos."""
    for indice, palabra in enumerate(palabras_titulo(titulo)):
        if palabra[0].islower() and (indice == 0 or palabra.lower() not in MENORES):
            fallo('APA', f'{donde}: «{palabra}» debería ir con mayúscula inicial en «{titulo}»')
            return


def contar_palabras(texto):
    texto = re.sub(r'\\,', '', texto)
    texto = re.sub(r'\$[^$]*\$', 'x', texto)
    texto = re.sub(r'\\[a-zA-Z]+', '', texto)
    return len(texto.split())


def revisar_apa():
    tesis = leer(os.path.join(RAIZ, 'memoria.tex'))
    # Página, letra, espaciado y alineación.
    for requisito, patron in [('papel carta', r'letterpaper'), ('márgenes de 2,54 cm', r'margin=2\.54cm'),
                              ('doble espacio', r'\\doublespacing'), ('Times de 12 puntos', r'12pt.*\n(.*\n)*.*mathptmx'),
                              ('texto alineado a la izquierda', r'\\RaggedRight'), ('sangría de 1,27 cm', r'\\parindent\}\{1\.27cm'),
                              ('sin guiones', r'\\hyphenpenalty=10000')]:
        if not re.search(patron, tesis):
            fallo('APA', f'falta {requisito} en memoria.tex')
    if '\\part{' in tesis:
        fallo('APA', 'APA no usa partes numeradas')
    # Título y encabezado.
    m = re.search(r'\\bfseries ([^\\]+?)\\par\}', tesis)
    if not m:
        fallo('APA', 'no se encuentra el título de la portada')
    else:
        titulo = m.group(1).strip()
        if len(titulo.split()) > 15:
            fallo('APA', f'el título tiene {len(titulo.split())} palabras (APA recomienda unas 12)')
        for sigla in re.findall(r'\b[A-ZÁÉÍÓÚ]{2,}\b', titulo):
            fallo('APA', f'el título no debe llevar abreviaturas: {sigla}')
        mayusculas_apa('título', titulo)
    m = re.search(r'\\newcommand\{\\titulocorto\}\{([^}]*)\}', tesis)
    if not m or len(m.group(1)) > 50 or m.group(1) != m.group(1).upper():
        fallo('APA', 'el título corto del encabezado debe ir en mayúsculas y tener como mucho 50 caracteres')
    # Orden: referencias antes de los apéndices.
    if tesis.find('\\printbibliography') < 0 or tesis.find('\\printbibliography') > tesis.find('\\apendices\n'):
        fallo('APA', 'las referencias deben ir antes de los apéndices')
    if 'title=Referencias' not in tesis:
        fallo('APA', 'la lista de referencias debe titularse «Referencias»')
    # Resúmenes: un párrafo de 150 a 250 palabras y palabras clave.
    resumen = leer(os.path.join(CAPITULOS, '00-resumen.tex'))
    for bloque in re.split(r'\\seccionprincipal\{', resumen)[1:]:
        nombre = bloque.split('}')[0]
        if '\\noindent' not in bloque or '\\textit{' not in bloque:
            fallo('APA', f'{nombre}: falta el párrafo sin sangría o las palabras clave en cursiva')
            continue
        cuerpo = bloque.split('\\noindent', 1)[1].split('\\textit{')[0].strip()
        if '\n\n' in cuerpo:
            fallo('APA', f'{nombre}: debe ser un solo párrafo')
        n = contar_palabras(cuerpo)
        if not 150 <= n <= 250:
            fallo('APA', f'{nombre}: {n} palabras (APA pide de 150 a 250)')
    # Títulos: niveles seguidos, nunca un único subtítulo bajo un título, mayúsculas y sin punto final.
    patron = re.compile(r'\\(chapter|section|subsection|subsubsection|paragraph)\*?(?:\[[^\]]*\])?\{')
    lista = []
    for nombre in ORDEN:
        texto = '\n'.join(sin_comentarios(l) for l in leer(os.path.join(CAPITULOS, nombre + '.tex')).split('\n'))
        for m in patron.finditer(texto):
            titulo = argumento(texto, m.end() - 1)
            lista.append((nombre, NIVEL[m.group(1)], titulo))
            mayusculas_apa(nombre, titulo)
            if titulo.rstrip().endswith('.'):
                fallo('APA', f'{nombre}: el título «{titulo}» no lleva punto final (lo pone el formato)')
    anterior = 0
    for nombre, nivel, titulo in lista:
        if nivel > anterior + 1:
            fallo('APA', f'{nombre}: «{titulo}» salta del nivel {anterior} al {nivel}')
        anterior = nivel
    for indice, (nombre, nivel, titulo) in enumerate(lista):
        hijos = 0
        for _, otro, _ in lista[indice + 1:]:
            if otro <= nivel:
                break
            if otro == nivel + 1:
                hijos += 1
        if hijos == 1:
            fallo('APA', f'{nombre}: «{titulo}» tiene un único subtítulo; APA pide al menos dos o ninguno')
    # Tablas y figuras: título arriba, sin punto, con mayúsculas; letra del mismo tamaño que el texto.
    for ruta in ficheros_tex():
        texto = leer(ruta)
        nombre = os.path.basename(ruta)
        for m in re.finditer(r'\\caption(?:\[[^\]]*\])?\{', texto):
            titulo = argumento(texto, m.end() - 1)
            if titulo.rstrip().endswith('.'):
                fallo('APA', f'{nombre}: el título de tabla o figura «{titulo[:50]}» no lleva punto final')
            if len(palabras_titulo(titulo)) > 16:
                aviso('APA', f'{nombre}: título de tabla o figura largo; lo explicativo va en la nota')
            if not titulo.startswith('\\texttt'):
                mayusculas_apa(nombre, titulo)
        for m in re.finditer(r'\\begin\{(figure|table)\}(.*?)\\end\{\1\}', texto, flags=re.S):
            bloque = m.group(2)
            leyenda = bloque.find('\\caption')
            contenido = re.search(r'\\begin\{(tikzpicture|tabular|tabularx|algorithmic)\}|\\includegraphics', bloque)
            if leyenda < 0 or (contenido and contenido.start() < leyenda):
                fallo('APA', f'{nombre}: el número y el título de cada tabla y figura van encima')
            sin_dibujos = re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', '', bloque, flags=re.S)
            if re.search(r'\\(small|footnotesize|scriptsize|tiny)\b', sin_dibujos):
                fallo('APA', f'{nombre}: las tablas usan la misma letra que el texto')
        for patron in [r'cap[ií]tulos?~\\ref\{', r'secci[oó]n(es)?~\\ref\{', r'\\ref\{(cap|sec):']:
            if re.search(patron, texto):
                fallo('APA', f'{nombre}: los títulos no tienen número; las referencias a capítulos y secciones van por su nombre')
    # PDF: carta y encabezado en la portada.
    pdf = os.path.join(RAIZ, 'memoria.pdf')
    try:
        info = subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout
        if '612 x 792' not in info:
            fallo('APA', 'el PDF no está en tamaño carta')
        portada = subprocess.run(['pdftotext', '-f', '1', '-l', '1', pdf, '-'], capture_output=True, text=True).stdout
        if 'PREDICCIÓN DE LLEGADAS DE AUTOBUSES' not in portada or not re.search(r'^\s*1\s*$', portada, flags=re.M):
            fallo('APA', 'la portada debe llevar el título corto y el número de página 1')
    except FileNotFoundError:
        aviso('APA', 'no están pdfinfo ni pdftotext (Poppler): no se revisa el PDF')


def informe_referencias():
    """Escribe pruebas/referencias.md: cada referencia con su enlace de consulta y su búsqueda en Google Académico."""
    from urllib.parse import quote_plus
    entradas = leer_bib()
    verificadas = json.load(open(os.path.join(AQUI, 'referencias-verificadas.json'), encoding='utf-8'))
    def limpio(texto):
        texto = re.sub(r'\\url\{([^}]*)\}', r'\1', texto)
        texto = re.sub(r'\\textsuperscript\{([^}]*)\}', r'\1', texto)
        texto = re.sub(r'[{}]', '', texto).replace('--', '-')
        return re.sub(r'\s+', ' ', texto).strip()
    filas = ['# Referencias de la memoria', '',
             'Cada referencia, con el enlace para consultarla y su búsqueda en Google Académico. Lo genera',
             '`python3 pruebas/revisar.py --informe` a partir de `bibliografia.bib` y `referencias-verificadas.json`.', '',
             '| Referencia | Consultar | Google Académico | Comprobada en |', '|---|---|---|---|']
    for clave, (tipo, campos) in sorted(entradas.items(), key=lambda e: limpio(e[1][1].get('author', e[0])).lower()):
        autores = limpio(campos.get('author', '')).replace(' and ', '; ')
        titulo = limpio(campos.get('title', ''))
        anio = limpio(campos.get('date', '')) or 's.f.'
        doi = limpio(campos.get('doi', ''))
        url = limpio(campos.get('url', '')) or limpio(campos.get('howpublished', ''))
        consultar = '—'
        if url:
            consultar = f'[enlace]({url})'
        if doi:
            consultar = f'[doi.org/{doi}](https://doi.org/{doi})'
        if doi and url:
            consultar += f' · [copia abierta]({url})'
        acceso = verificadas.get(clave, {}).get('acceso')
        if acceso and acceso not in (url,):
            consultar += f' · [acceso]({acceso})'
        apellido = ''
        if ',' in autores:
            apellido = autores.split(',')[0]
        frase = titulo.split('. ')[0]
        if len(frase) < 25:
            frase = titulo
        busqueda = 'https://scholar.google.com/scholar?q=' + quote_plus(('"' + frase[:150] + '" ' + apellido).strip())
        fuente = verificadas.get(clave, {}).get('fuente', '')
        comprobada = fuente
        if fuente.startswith('http'):
            comprobada = f'[{verificadas.get(clave, {}).get("comprobado", "")}]({fuente})'
        filas.append(f'| {autores} ({anio}). *{titulo}*. | {consultar} | [buscar]({busqueda}) | {comprobada} |')
    ruta = os.path.join(AQUI, 'referencias.md')
    open(ruta, 'w', encoding='utf-8').write('\n'.join(filas) + '\n')
    print('Escrito', ruta)


def main():
    if '--informe' in sys.argv:
        informe_referencias()
        return
    if '--sin-compilar' not in sys.argv:
        compilar()
    revisar_log()
    revisar_bibliografia()
    revisar_reproducibilidad()
    revisar_rastros()
    revisar_ortotipografia()
    revisar_apa()
    for bloque, texto in avisos:
        print(f'AVISO  [{bloque}] {texto}')
    for bloque, texto in fallos:
        print(f'FALLO  [{bloque}] {texto}')
    print(f'\nRESULTADO: {len(fallos)} fallos, {len(avisos)} avisos')
    if fallos:
        sys.exit(1)


if __name__ == '__main__':
    main()
