"""Eleitores habilitados sem biometria (campo QT_ELEI_BIOM_SEM_HABILITACAO do boletim de urna), por seção,
cidade e UF, nos dois turnos de 2026 (e 2º turno de 2022 para comparação), ao lado dos votos de presidente.
Saída: dados/sem_biometria/secao.csv|parquet, cidade.csv|parquet, uf.csv|parquet"""
import os, duckdb
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
P, OUT = f'{D}/parquet', f'{D}/sem_biometria'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()
con.execute(f"""
CREATE TABLE s AS
SELECT coalesce(a.uf, b.uf) uf, coalesce(a.cd_municipio, b.cd_municipio) cd_municipio,
       coalesce(a.nm_municipio, b.nm_municipio) nm_municipio,
       coalesce(a.nr_zona, b.nr_zona) nr_zona, coalesce(a.nr_secao, b.nr_secao) nr_secao,
       coalesce(b.nr_local, a.nr_local) nr_local, coalesce(b.nr_urna, a.nr_urna) nr_urna, coalesce(b.aptos, a.aptos) aptos,
       a.comparecimento comp_t1, a.biom_nh sem_biom_t1, a.v13 lula_t1, a.v22 flavio_t1,
       b.comparecimento comp_t2, b.biom_nh sem_biom_t2, b.v13 lula_t2, b.v22 flavio_t2,
       c.comparecimento comp_2022, c.biom_nh sem_biom_2022, c.v13 lula_2022, c.v22 bolsonaro_2022
FROM '{P}/bweb_2026_t1_secao.parquet' a
FULL JOIN '{P}/bweb_2026_t2_secao.parquet' b USING (uf, cd_municipio, nr_zona, nr_secao)
LEFT JOIN '{P}/bweb_2022_t2_secao.parquet' c USING (uf, cd_municipio, nr_zona, nr_secao)""")
NIVEIS = {'secao': 'uf, cd_municipio, nm_municipio, nr_zona, nr_secao, nr_local, nr_urna, aptos',
          'cidade': 'uf, cd_municipio, nm_municipio', 'uf': 'uf'}
for nivel, chave in NIVEIS.items():
    con.execute(f"""
    CREATE OR REPLACE TABLE r_{nivel} AS
    SELECT {chave}, {'count(*) secoes,' if nivel != 'secao' else ''}
      sum(comp_t1) comp_t1, sum(sem_biom_t1) sem_biom_t1, round(100.0 * sum(sem_biom_t1) / nullif(sum(comp_t1), 0), 2) pct_sem_biom_t1,
      sum(comp_t2) comp_t2, sum(sem_biom_t2) sem_biom_t2, round(100.0 * sum(sem_biom_t2) / nullif(sum(comp_t2), 0), 2) pct_sem_biom_t2,
      sum(sem_biom_t2) - sum(sem_biom_t1) var_sem_biom,
      sum(lula_t1) lula_t1, sum(flavio_t1) flavio_t1, sum(lula_t2) lula_t2, sum(flavio_t2) flavio_t2,
      round(100.0 * sum(lula_t2) / nullif(sum(lula_t2 + flavio_t2), 0), 2) pct_lula_t2,
      sum(comp_2022) comp_2022, sum(sem_biom_2022) sem_biom_2022, round(100.0 * sum(sem_biom_2022) / nullif(sum(comp_2022), 0), 2) pct_sem_biom_2022
    FROM s GROUP BY ALL ORDER BY pct_sem_biom_t2 DESC NULLS LAST""")
    con.execute(f"COPY r_{nivel} TO '{OUT}/{nivel}.csv' (HEADER, DELIMITER ';')")
    con.execute(f"COPY r_{nivel} TO '{OUT}/{nivel}.parquet' (FORMAT parquet)")
    print(nivel, con.execute(f"SELECT count(*) FROM r_{nivel}").fetchone()[0], 'linhas')
pd = lambda sql: print(con.execute(sql).fetchdf().to_string(index=False))
print('\n=== Brasil'); pd("""SELECT sum(comp_t1) comp_t1, sum(sem_biom_t1) sem_biom_t1, round(100.0*sum(sem_biom_t1)/sum(comp_t1),2) pct_t1,
  sum(comp_t2) comp_t2, sum(sem_biom_t2) sem_biom_t2, round(100.0*sum(sem_biom_t2)/sum(comp_t2),2) pct_t2,
  sum(sem_biom_2022) sem_biom_2022, round(100.0*sum(sem_biom_2022)/sum(comp_2022),2) pct_2022 FROM r_uf""")
print('\n=== Por UF'); pd("SELECT * EXCLUDE (lula_t1, flavio_t1, lula_t2, flavio_t2, comp_2022) FROM r_uf ORDER BY uf")
print('\n=== 20 cidades com mais votos sem biometria no 2º turno'); pd("SELECT uf, nm_municipio, secoes, comp_t2, sem_biom_t2, pct_sem_biom_t2, sem_biom_t1, pct_sem_biom_t1, var_sem_biom, pct_lula_t2 FROM r_cidade ORDER BY sem_biom_t2 DESC LIMIT 20")
print('\n=== 10 seções com mais votos sem biometria no 2º turno'); pd("SELECT uf, nm_municipio, nr_zona, nr_secao, aptos, comp_t2, sem_biom_t2, pct_sem_biom_t2, sem_biom_t1, lula_t2, flavio_t2 FROM r_secao ORDER BY sem_biom_t2 DESC LIMIT 10")
print('\n=== Distribuição por seção da % sem biometria no 2º turno'); pd("""SELECT round(quantile_cont(pct_sem_biom_t2, 0.1),1) p10, round(quantile_cont(pct_sem_biom_t2, 0.25),1) p25,
  round(median(pct_sem_biom_t2),1) mediana, round(quantile_cont(pct_sem_biom_t2, 0.75),1) p75, round(quantile_cont(pct_sem_biom_t2, 0.9),1) p90,
  round(quantile_cont(pct_sem_biom_t2, 0.99),1) p99, max(pct_sem_biom_t2) max, sum(sem_biom_t2 = 0) secoes_zero, sum(pct_sem_biom_t2 > 50) secoes_acima_50 FROM r_secao WHERE comp_t2 > 0""")
