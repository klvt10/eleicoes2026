"""Uma linha de status da coleta do 2º turno."""
import duckdb, os
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
con = duckdb.connect()
r = con.execute("""
WITH t2 AS (
  SELECT uf, cd_municipio::INT m, nr_zona::INT z, nr_secao::INT s, status,
         votos_13::INT v13, votos_22::INT v22, erro
  FROM read_csv('dados/t2/secoes_*.csv', header=true, all_varchar=true, union_by_name=true)),
t1 AS (
  SELECT uf, cd_municipio m, nr_zona z, nr_secao s,
         sum(votos) FILTER (nr_votavel=13) a13, sum(votos) FILTER (nr_votavel=22) a22
  FROM 'dados/parquet/t1_votos_secao.parquet' GROUP BY ALL)
SELECT count(*) n, count(*) FILTER (erro IS NOT NULL) err, count(DISTINCT uf) ufs,
       sum(v13) v13, sum(v22) v22, sum(a13) a13, sum(a22) a22
FROM t2 LEFT JOIN t1 USING (uf, m, z, s)""").fetchone()
n, err, ufs, v13, v22, a13, a22 = r
v13, v22, a13, a22 = (x or 0 for x in (v13, v22, a13, a22))
log = open('logs/supervisor.log').read().strip().splitlines()[-1][9:] if os.path.exists('logs/supervisor.log') else ''
p2 = 100 * v13 / max(v13 + v22, 1); p1 = 100 * a13 / max(a13 + a22, 1)
print(f"{n:,}/499.248 seções ({100*n/499248:.1f}%) | {ufs} UFs | erros {err} | "
      f"2T nas seções coletadas: 13={p2:.2f}% 22={100-p2:.2f}% | mesmas seções no 1T (só 13×22): 13={p1:.2f}% "
      f"→ swing {p2-p1:+.2f} p.p. | {log}".replace(',', '.'))
