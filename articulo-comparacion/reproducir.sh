#!/bin/bash
# Reproduce el artículo 2 desde los datos publicados: baja las capturas de la release comparacion-2026-11, empareja cada
# día (comparar.py), hace las ablaciones, las tablas (resultados.py), las figuras (figuras.py) y compila el PDF.
# Necesita: Python 3.9+, gh (o curl) con acceso a la release, y latexmk para el PDF.
# Uso: articulo-comparacion/reproducir.sh <carpeta de trabajo>      (desde la raíz del repositorio)
set -euo pipefail
W=${1:?carpeta de trabajo}
REPO=Garridoparrayeray/bide-eta
REL=comparacion-2026-11
DIAS="20261108 20261109 20261110 20261111 20261112 20261113 20261114"
mkdir -p "$W/dias" "$W/pares" "$W/abl-todo" "$W/abl-tramos" "$W/abl-ritmo" "$W/abl-viajes"
# Base del horario (la que usó el análisis: GTFS publicado el 25/9/2026, válido hasta el 24/11/2026) y tablas aprendidas del 7 de noviembre (datos/tablas).
[ -f "$W/bizkaibus.sqlite" ] || xz -dkc datos/horario/bizkaibus.sqlite.xz > "$W/bizkaibus.sqlite"
TABLAS=datos/tablas
for d in $DIAS; do
  if [ ! -d "$W/dias/$d" ]; then
    mkdir -p "$W/dias/$d"
    gh release download "$REL" -R "$REPO" -p "captura-$d-*.tar.xz" -D "$W/dias/$d"
    for t in "$W/dias/$d"/*.tar.xz; do mkdir -p "${t%.tar.xz}"; tar -xJf "$t" -C "${t%.tar.xz}"; rm "$t"; done
  fi
  base=(--bloques "$W/dias/$d" --base "$W/bizkaibus.sqlite" --tablas "$TABLAS" --paradas articulo-comparacion/captura/paradas.json)
  python3 -I articulo-comparacion/comparar.py "${base[@]}" --salida "$W/pares/pares-$d.jsonl"
  python3 -I articulo-comparacion/comparar.py "${base[@]}" --sin-aprender --salida "$W/abl-todo/pares-$d.jsonl"
  for parte in tramos ritmo viajes; do
    python3 -I articulo-comparacion/comparar.py "${base[@]}" --vaciar $parte --salida "$W/abl-$parte/pares-$d.jsonl"
  done
done
python3 -I articulo-comparacion/resultados.py "$W/pares" --ablacion todo="$W/abl-todo" --ablacion tramos="$W/abl-tramos" \
  --ablacion ritmo="$W/abl-ritmo" --ablacion viajes="$W/abl-viajes" --tex articulo-comparacion/tablas | tee "$W/resultados.txt"
python3 -I articulo-comparacion/figuras.py "$W/pares" articulo-comparacion/figuras
(cd articulo-comparacion && latexmk -pdf -interaction=nonstopmode articulo.tex)
