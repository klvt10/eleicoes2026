"""Junta os CSVs do crawler do 2º turno e gera Parquets + tabela comparativa T1×T2 por seção."""
import duckdb, os
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
con = duckdb.connect()
con.execute(f"""
COPY (
  SELECT uf, CAST(cd_municipio AS INT) cd_municipio, nm_municipio, CAST(nr_zona AS INT) nr_zona,
         CAST(nr_secao AS INT) nr_secao, status, CAST(secao_principal AS INT) secao_principal,
         secoes_agregadas, aptos::INT aptos, comparecimento::INT comparecimento,
         votos_13::INT votos_13, votos_22::INT votos_22, brancos::INT brancos, nulos::INT nulos,
         outros::INT outros, erro
  FROM read_csv('{D}/t2/secoes_*.csv', header=true, all_varchar=true, union_by_name=true)
) TO '{D}/parquet/t2_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")
# T1 em formato largo (1 linha por seção) + T2 lado a lado
con.execute(f"""
COPY (
  WITH v1 AS (
    SELECT uf, cd_municipio, nr_zona, nr_secao,
           sum(votos) FILTER (nr_votavel=13) t1_13, sum(votos) FILTER (nr_votavel=22) t1_22,
           sum(votos) FILTER (nr_votavel=70) t1_70, sum(votos) FILTER (nr_votavel=14) t1_14,
           sum(votos) FILTER (nr_votavel=55) t1_55,
           sum(votos) FILTER (nr_votavel NOT IN (13,22,70,14,55,95,96)) t1_outros,
           sum(votos) FILTER (nr_votavel=95) t1_brancos, sum(votos) FILTER (nr_votavel=96) t1_nulos
    FROM '{D}/parquet/t1_votos_secao.parquet' GROUP BY ALL)
  SELECT d.uf, d.cd_municipio, d.nm_municipio, d.nr_zona, d.nr_secao, d.nr_local, d.nm_local, d.endereco,
         d.aptos t1_aptos, d.comparecimento t1_comparecimento, d.modelo_urna,
         COALESCE(v1.t1_13,0) t1_13, COALESCE(v1.t1_22,0) t1_22, COALESCE(v1.t1_70,0) t1_70,
         COALESCE(v1.t1_14,0) t1_14, COALESCE(v1.t1_55,0) t1_55, COALESCE(v1.t1_outros,0) t1_outros,
         COALESCE(v1.t1_brancos,0) t1_brancos, COALESCE(v1.t1_nulos,0) t1_nulos,
         t2.status t2_status, t2.aptos t2_aptos, t2.comparecimento t2_comparecimento,
         t2.votos_13 t2_13, t2.votos_22 t2_22, t2.brancos t2_brancos, t2.nulos t2_nulos
  FROM '{D}/parquet/t1_detalhe_secao.parquet' d
  LEFT JOIN v1 USING (uf, cd_municipio, nr_zona, nr_secao)
  LEFT JOIN '{D}/parquet/t2_secao.parquet' t2 USING (uf, cd_municipio, nr_zona, nr_secao)
) TO '{D}/parquet/secao_t1_t2.parquet' (FORMAT parquet, COMPRESSION zstd)""")
print(con.sql(f"""SELECT count(*) secoes_t1, count(t2_status) com_t2, count(*) FILTER (t2_status='Totalizada') t2_totalizadas,
  sum(t2_13) t2_13, sum(t2_22) t2_22 FROM '{D}/parquet/secao_t1_t2.parquet'"""))
