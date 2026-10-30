#!/bin/bash
# Baixa perfil_eleitor_secao (TSE) 2026/2022/2024 por UF. Retomável (curl -C -).
cd "$(dirname "$0")/.."
export B=https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitor_secao
UFS="AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"

baixa() {
  y=$1; u=$2; n=perfil_eleitor_secao_${y}_$u.zip; f=dados/perfil/raw/$n
  code=$(curl -s -o /dev/null -w "%{http_code}" -I -A "pesquisa-eleicoes/1.0" "$B/$n")
  if [ "$code" != 200 ]; then echo "$(date +%T) $y $u HTTP $code (sem arquivo)"; return; fi
  if curl -sf -C - --retry 5 --retry-delay 10 -A "pesquisa-eleicoes/1.0" -o "$f" "$B/$n"; then
    echo "$(date +%T) $y $u ok $(du -h "$f" | cut -f1)"
  else
    echo "$(date +%T) $y $u ERRO"
  fi
}
export -f baixa

for y in 2026 2022 2024; do for u in $UFS; do echo "$y $u"; done; done |
  xargs -P 2 -L 1 bash -c 'baixa "$0" "$1"'
echo FIM
