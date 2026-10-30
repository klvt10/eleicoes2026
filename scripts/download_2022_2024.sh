#!/bin/bash
# Baixa do CDN do TSE os arquivos oficiais de 2022 (geral) e 2024 (municipal).
B=https://cdn.tse.jus.br/estatistica/sead/odsele
D=$(dirname "$0")/../dados
UFS="AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO"
get() { [ -s "$2" ] && unzip -tq "$2" >/dev/null 2>&1 && return; curl -sS --retry 5 -o "$2" "$1" && echo "ok $2" || echo "FALHA $1"; }
get $B/votacao_secao/votacao_secao_2022_BR.zip $D/2022/raw/votacao_secao_2022_BR.zip &
get $B/detalhe_votacao_secao/detalhe_votacao_secao_2022.zip $D/2022/raw/detalhe_votacao_secao_2022.zip &
get $B/consulta_cand/consulta_cand_2022.zip $D/2022/raw/consulta_cand_2022.zip &
get $B/detalhe_votacao_secao/detalhe_votacao_secao_2024.zip $D/2024/raw/detalhe_votacao_secao_2024.zip &
get $B/consulta_cand/consulta_cand_2024.zip $D/2024/raw/consulta_cand_2024.zip &
wait
for uf in $UFS; do echo "$uf"; done | xargs -P 4 -I{} bash -c "$(declare -f get); B=$B; D=$D; get \$B/votacao_secao/votacao_secao_2022_{}.zip \$D/2022/raw/votacao_secao_2022_{}.zip; [ {} = DF ] || get \$B/votacao_secao/votacao_secao_2024_{}.zip \$D/2024/raw/votacao_secao_2024_{}.zip"
echo FIM
