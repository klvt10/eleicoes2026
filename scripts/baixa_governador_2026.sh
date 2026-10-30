#!/bin/bash
# Resultado de governador 2026 por UF (arquivo de resultado por UF do portal de resultados do TSE, .../dados/<uf>/<uf>-c0003-e<eleição>-u.json): 1º turno (eleição 6259) e 2º turno (6260, só AM e RN).
cd "$(dirname "$0")/../dados/gov2026/raw"
A="pesquisa-eleicoes/1.0"; B=https://resultados.tse.jus.br/oficial/ele2026
for u in ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to; do
  curl -sf --retry 3 -A "$A" -o t1_$u.json "$B/6259/dados/$u/$u-c0003-e006259-u.json" || echo "falhou t1 $u"
done
for u in am rn; do
  curl -sf --retry 3 -A "$A" -o t2_$u.json "$B/6260/dados/$u/$u-c0003-e006260-u.json" || echo "falhou t2 $u"
done
ls | wc -l
