#!/bin/bash
# Resultado de senador 2026 por UF (portal de resultados do TSE, cargo c0005, eleição 6259 = 1º turno).
mkdir -p "$(dirname "$0")/../dados/sen2026/raw" && cd "$(dirname "$0")/../dados/sen2026/raw"
A="pesquisa-eleicoes/1.0"; B=https://resultados.tse.jus.br/oficial/ele2026
for u in ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to; do
  [ -s t1_$u.json ] || curl -sf --retry 3 -A "$A" -o t1_$u.json "$B/6259/dados/$u/$u-c0005-e006259-u.json" || echo "falhou $u"
done
ls | wc -l
