"""Votos do 1º turno de 2026 por cidade, cargo e partido/candidato, a partir dos boletins de urna (bweb 1T, todos os cargos).
Saída: dados/parquet/t1_cargos_cidade.parquet — uma linha por (uf, cidade, cargo, nr_votavel), com partido e votos."""
import duckdb, os
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
con = duckdb.connect()
con.execute("SET preserve_insertion_order=false")
con.execute(f"""COPY (
  SELECT SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, any_value(NM_MUNICIPIO) nm_municipio,
         CAST(CD_CARGO_PERGUNTA AS INT) cd_cargo, any_value(DS_CARGO_PERGUNTA) cargo,
         CAST(NR_VOTAVEL AS INT) nr_votavel, any_value(NM_VOTAVEL) nm_votavel,
         CAST(NR_PARTIDO AS INT) nr_partido, any_value(SG_PARTIDO) sg_partido,
         any_value(CD_TIPO_VOTAVEL) cd_tipo_votavel, any_value(DS_TIPO_VOTAVEL) tipo_votavel,
         sum(CAST(QT_VOTOS AS BIGINT)) votos, count(DISTINCT NR_ZONA || '-' || NR_SECAO) secoes
  FROM read_csv('{D}/bweb/2026_t1/csv/bweb_1t_*.csv', delim=';', header=true, encoding='latin-1', all_varchar=true, union_by_name=true)
  GROUP BY 1, 2, 4, 6, 8
) TO '{D}/parquet/t1_cargos_cidade.parquet' (FORMAT parquet, COMPRESSION zstd)""")
print(con.execute(f"""SELECT cd_cargo, any_value(cargo), count(*) linhas, sum(votos) votos, count(DISTINCT uf || cd_municipio) cidades
  FROM '{D}/parquet/t1_cargos_cidade.parquet' GROUP BY 1 ORDER BY 1""").fetchdf().to_string())
