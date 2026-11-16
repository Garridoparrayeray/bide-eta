"""Convierte referencias.bib (biblatex) en referencias-bibtex.bib para la versión de Springer (BibTeX, sn-basic)."""
import re
s = open('referencias.bib', encoding='utf-8').read()
s = re.sub(r'^@online\{', '@misc{', s, flags=re.M)
s = re.sub(r'^@report\{', '@techreport{', s, flags=re.M)
def fecha(m):
    año = re.match(r'\{?(\d{4})', m.group(2)).group(1)
    return '%syear%s= {%s},' % (m.group(1), m.group(3), año)
s = re.sub(r'^(\s*)date(\s*)= *\{([^}]*)\},', lambda m: '%syear%s= {%s},' % (m.group(1), m.group(2), m.group(3)[:4]), s, flags=re.M)
s = re.sub(r'^(\s*)location(\s*)=', r'\1address\2=', s, flags=re.M)
s = re.sub(r'^(\s*)eid(\s*)=', r'\1pages\2=', s, flags=re.M)
s = re.sub(r'^(\s*)urldate(\s*)= *\{([^}]*)\},', r'\1note\2= {Accessed \3},', s, flags=re.M)
s = re.sub(r'^\s*(langid|shortauthor|addendum)\s*=.*\n', '', s, flags=re.M)
s = s.replace('author      = {{European Committee for Standardization (CEN)}},', 'author      = {{CEN}},\n  institution = {European Committee for Standardization},')
open('referencias-bibtex.bib', 'w', encoding='utf-8').write(s)

# Declaraciones con los encabezados de Springer (sección «Declarations»), a partir de declaraciones.tex.
d = open('declaraciones.tex', encoding='utf-8').read()
for viejo, nuevo in (('\\section*{Declaration of competing interest}', '\\bmhead{Competing interests}'),
                     ('\\section*{Funding}', '\\bmhead{Funding}'),
                     ('\\section*{CRediT authorship contribution statement}', '\\bmhead{Author contributions}'),
                     ('\\section*{Data availability}', '\\bmhead{Data and code availability}'),
                     ('\\section*{Data collection and terms of use}', '\\bmhead{Data collection and terms of use}')):
    assert d.count(viejo) == 1, viejo
    d = d.replace(viejo, nuevo)
d = d.replace('\\bmhead{Data and code availability}',
              '\\bmhead{Ethics approval and consent}\n\nNot applicable: the study involves no human participants and no '
              'personal data.\n\n\\bmhead{Data and code availability}')
open('declaraciones-springer.tex', 'w', encoding='utf-8').write(
    '% Generado por bib-a-bibtex.py a partir de declaraciones.tex: no editar a mano.\n\\section*{Declarations}\n' + d)

# Las referencias web sin fecha (GTFS, GTFS-Realtime, Punto de Acceso Nacional) llevan «n.d.», como en APA.
s = open('referencias-bibtex.bib', encoding='utf-8').read()
entradas = re.split(r'(?=^@)', s, flags=re.M)
entradas = [e if not e.startswith('@') or re.search(r'^\s*year\s*=', e, flags=re.M)
            else re.sub(r'\n\}\s*$', '\n  year        = {n.d.}\n}\n\n', e.rstrip() + '\n') for e in entradas]
open('referencias-bibtex.bib', 'w', encoding='utf-8').write(''.join(entradas))
