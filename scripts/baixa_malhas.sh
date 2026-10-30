#!/bin/bash
# Malhas do IBGE (qualidade mínima): estados do Brasil e municípios de cada UF, mais a lista de municípios.
cd "$(dirname "$0")/../dados/geo/raw"
A="pesquisa-eleicoes/1.0"; B=https://servicodados.ibge.gov.br/api
curl -sf -A "$A" -o br_uf.json "$B/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF"
curl -sf -A "$A" -o municipios.json "$B/v1/localidades/municipios?view=nivelado"
for u in AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO; do
  [ -s mun_$u.json ] || curl -sf --retry 3 -A "$A" -o mun_$u.json "$B/v3/malhas/estados/$u?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio"
  echo "$u $(du -h mun_$u.json | cut -f1)"
done
