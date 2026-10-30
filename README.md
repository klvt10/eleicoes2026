# eleicoes2026

Checagem de alegações sobre a eleição presidencial de 2026 (Lula × Flávio Bolsonaro) com os dados oficiais do TSE por seção eleitoral, e um site estático com os resultados.

- `scripts/` — backend: baixa os boletins de urna (bweb) e demais arquivos do TSE, gera os Parquet em `dados/parquet/` e os JSON consumidos pelo site em `site/dados/`. Python + DuckDB (`.venv`).
- `site/` — frontend estático (Netlify, pasta `site/`): mapa de transferências (`index.html`), presidente × outros cargos (`comparativo.html`), modelo de previsão (`modelo.html`) e votos por urna (`votos-por-urna.html`).
- `relatorios/` — relatórios e tabelas de saída das checagens.
- `dados/` — não versionado (56 GB). Recriar com `scripts/download_2022_2024.sh`, `scripts/build_bweb.py` etc.

## Votos por urna

`scripts/votos_por_urna.py` lê `dados/parquet/bweb_{2026_t1,2026_t2,2022_t2}_secao.parquet` e grava em `site/dados/votos_por_urna/` o histograma de urnas por número de votos de cada candidato (por UF, com os votos do adversário, comparecimento, aptos, brancos/nulos, sem biometria e o outro turno nas mesmas seções) e a lista das urnas em que algum dos dois teve até 10 votos. A página `site/votos-por-urna.html` filtra por região, estado e condição (até / pelo menos / exatamente N votos).

## Publicação

`scripts/publica_site.sh` troca o número de versão dos arquivos e faz o deploy no Netlify.
