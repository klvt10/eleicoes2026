#!/bin/bash
# Espera o portal liberar, roda o coletor e repete até não haver seção pendente/com erro.
cd "$(dirname "$0")/.."
URL=https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/ac/ac-p003221-cs.json
while true; do
  until [ "$(curl -s -o /dev/null -m 20 -w '%{http_code}' $URL)" = 200 ]; do
    echo "$(date +%H:%M:%S) BLOQUEADO (429) - nova tentativa em 120s"; sleep 120
  done
  echo "$(date +%H:%M:%S) LIBERADO - iniciando coleta"
  .venv/bin/python scripts/crawl_2t.py
  .venv/bin/python - <<'PY' && { echo "$(date +%H:%M:%S) COLETA COMPLETA"; exit 0; }
import duckdb, sys, glob
n = duckdb.execute("SELECT count(*) FILTER (erro IS NOT NULL) FROM read_csv('dados/t2/secoes_*.csv', all_varchar=true)").fetchone()[0]
print('erros restantes:', n); sys.exit(1 if n or len(glob.glob('dados/t2/secoes_*.csv')) < 28 else 0)
PY
  sleep 60
done
