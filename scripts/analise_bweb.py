"""Checagem das alegações sobre horário de encerramento das urnas e votos sem biometria no 2º turno de 2026,
com os Boletins de Urna Web do TSE (dados/parquet/bweb_*). Compara com 2022 e com o 1º turno de 2026
(mesmas seções). Uso: analise_bweb.py [> relatorios/analise_bweb.txt]"""
import duckdb, os
D = os.path.join(os.path.dirname(__file__), '..', 'dados', 'parquet')
con = duckdb.connect()
def faixa(col='enc_bsb'):
    return f"""CASE WHEN {col} IS NULL THEN 'sem hora'
      WHEN {col}::TIME < '17:01:00' THEN '1 ate 17h00'
      WHEN {col}::TIME < '17:05:00' THEN '2 17h01-17h04'
      WHEN {col}::TIME < '17:10:00' THEN '3 17h05-17h09'
      WHEN {col}::TIME < '17:15:00' THEN '4 17h10-17h14'
      WHEN {col}::TIME < '19:00:00' THEN '5 17h15-18h59'
      ELSE '6 apos 19h' END"""
def show(t, q): print(f'\n=== {t}'); print(con.sql(q).fetchdf().to_string(index=False))

con.execute(f"""CREATE TABLE s AS
  SELECT b.*, {faixa('b.enc_bsb')} faixa, {faixa('t1.enc_bsb')} faixa_t1,
         t1.v13 t1_13, t1.v22 t1_22, t1.total_votos - t1.brancos - t1.nulos t1_validos,
         t1.biom_nh t1_biom_nh, t1.comparecimento t1_comparecimento
  FROM '{D}/bweb_2026_t2_secao.parquet' b
  LEFT JOIN '{D}/bweb_2026_t1_secao.parquet' t1 USING (uf, cd_municipio, nr_zona, nr_secao)
  WHERE b.uf<>'ZZ' AND b.comparecimento>0""")
con.execute(f"""CREATE TABLE s22 AS SELECT *, {faixa()} faixa FROM '{D}/bweb_2022_t2_secao.parquet' WHERE uf<>'ZZ' AND comparecimento>0""")

for t, tb in (('2026 2T (Lula x Flávio) por faixa de encerramento, hora de Brasília', 's'),
              ('2022 2T (Lula x Bolsonaro) por faixa de encerramento, hora de Brasília', 's22')):
    show(t, f"""SELECT faixa, count(*) secoes, sum(comparecimento) comp,
        round(100.0*sum(comparecimento)/(SELECT sum(comparecimento) FROM {tb}),1) pct_comp,
        round(100.0*sum(v13)/sum(v13+v22),2) pct_lula, sum(v13-v22) vantagem_lula,
        round(100.0*sum(v13-v22)/(SELECT sum(v13-v22) FROM {tb}),1) pct_da_vantagem,
        round(avg(aptos),0) aptos_medio FROM {tb} GROUP BY 1 ORDER BY 1""")

show('2026: mesmas seções no 1T — % Lula T1 (13 x 22), swing T1->T2, por faixa de encerramento do T2', """
  SELECT faixa, count(*) secoes, round(100.0*sum(v13)/sum(v13+v22),2) lula_t2,
         round(100.0*sum(t1_13)/sum(t1_13+t1_22),2) lula_t1,
         round(100.0*sum(v13)/sum(v13+v22)-100.0*sum(t1_13)/sum(t1_13+t1_22),2) swing_pp,
         round(100.0*sum(biom_nh)/sum(comparecimento),2) pct_sem_biom_t2,
         round(100.0*sum(t1_biom_nh)/sum(t1_comparecimento),2) pct_sem_biom_t1
  FROM s WHERE t1_13 IS NOT NULL GROUP BY 1 ORDER BY 1""")

show('2026 1T (4/out, sem prorrogação): % Lula (13 x 22) por faixa de encerramento do 1T', """
  SELECT faixa_t1 faixa, count(*) secoes, sum(t1_comparecimento) comp,
         round(100.0*sum(t1_13)/sum(t1_13+t1_22),2) lula_t1_13x22, round(100.0*sum(t1_13)/sum(t1_validos),2) lula_t1_validos
  FROM s WHERE t1_13 IS NOT NULL GROUP BY 1 ORDER BY 1""")

show('Gap intra-município: seção tardia menos seções no horário (até 17h04) do mesmo município, T2 e T1', """
  WITH m AS (SELECT uf, cd_municipio,
      sum(v13) FILTER (faixa<'3')/NULLIF(sum(v13+v22) FILTER (faixa<'3'),0) ref_t2,
      sum(t1_13) FILTER (faixa<'3')/NULLIF(sum(t1_13+t1_22) FILTER (faixa<'3'),0) ref_t1 FROM s GROUP BY 1,2)
  SELECT faixa, count(*) secoes,
         round(100.0*sum(comparecimento*(v13/(v13+v22)-ref_t2))/sum(comparecimento),2) gap_t2_pp,
         round(100.0*sum(comparecimento*(t1_13/(t1_13+t1_22)-ref_t1))/sum(comparecimento),2) gap_t1_pp
  FROM s JOIN m USING (uf, cd_municipio)
  WHERE faixa>='3' AND v13+v22>0 AND t1_13+t1_22>0 AND ref_t2 IS NOT NULL GROUP BY 1 ORDER BY 1""")

show('Seções encerradas após 19h (prorrogação STF) por UF: T2 vs T1 nas mesmas seções e gap intra-município', """
  WITH m AS (SELECT uf, cd_municipio,
      sum(v13) FILTER (faixa<'3')/NULLIF(sum(v13+v22) FILTER (faixa<'3'),0) ref_t2,
      sum(t1_13) FILTER (faixa<'3')/NULLIF(sum(t1_13+t1_22) FILTER (faixa<'3'),0) ref_t1 FROM s GROUP BY 1,2)
  SELECT uf, count(*) secoes, sum(comparecimento) comp, round(100.0*sum(v13)/sum(v13+v22),2) lula_t2,
         round(100.0*sum(t1_13)/sum(t1_13+t1_22),2) lula_t1, round(100.0*sum(v13)/sum(v13+v22)-100.0*sum(t1_13)/sum(t1_13+t1_22),2) swing_pp,
         round(100.0*sum(comparecimento*(v13/(v13+v22)-ref_t2))/sum(comparecimento),2) gap_mun_t2,
         round(100.0*sum(comparecimento*(t1_13/(t1_13+t1_22)-ref_t1))/sum(comparecimento),2) gap_mun_t1
  FROM s JOIN m USING (uf, cd_municipio) WHERE faixa LIKE '6%' AND v13+v22>0 AND t1_13+t1_22>0 GROUP BY 1 ORDER BY 2 DESC""")

show('Taxa de encerramento tardio (>=17h05) por tamanho da seção', """
  SELECT CASE WHEN aptos<250 THEN 'a <250' WHEN aptos<350 THEN 'b 250-349' WHEN aptos<450 THEN 'c 350-449' ELSE 'd 450+' END tam,
         count(*) secoes, round(100.0*avg((faixa>='3' AND faixa<>'sem hora')::INT),1) pct_tardias_2026,
         round(100.0*sum(v13)/sum(v13+v22),1) lula_2026 FROM s GROUP BY 1 ORDER BY 1""")

for t, tb in (('2026', 's'), ('2022', 's22')):
    show(f'{t}: votos sem biometria por UF', f"""SELECT uf, sum(comparecimento) comp, sum(biom_nh) sem_biom,
        round(100.0*sum(biom_nh)/sum(comparecimento),2) pct_sem_biom, round(100.0*sum(v13)/sum(v13+v22),2) pct_lula
        FROM {tb} GROUP BY 1 ORDER BY 4 DESC""")
    show(f'{t}: correlação por seção entre % sem biometria e % Lula (nacional e dentro do município)', f"""
      WITH x AS (SELECT uf, cd_municipio, 100.0*biom_nh/comparecimento pb, 100.0*v13/(v13+v22) pl FROM {tb} WHERE v13+v22>0),
      m AS (SELECT *, pb-avg(pb) OVER (PARTITION BY uf,cd_municipio) dpb, pl-avg(pl) OVER (PARTITION BY uf,cd_municipio) dpl FROM x)
      SELECT round(corr(pb,pl),3) corr_nacional, round(corr(dpb,dpl),3) corr_intra_municipio, round(regr_slope(dpl,dpb),3) inclinacao_intra FROM m""")

show('2026: decis do % sem biometria no T2 por seção: % Lula T2, T1 e swing; % sem biometria no T1 das mesmas seções', """
  WITH x AS (SELECT *, 100.0*biom_nh/comparecimento pb FROM s WHERE v13+v22>0 AND t1_13+t1_22>0),
  d AS (SELECT *, ntile(10) OVER (ORDER BY pb) decil FROM x)
  SELECT decil, round(min(pb),1) pb_min, round(max(pb),1) pb_max, round(100.0*sum(t1_biom_nh)/sum(t1_comparecimento),2) pb_t1,
         round(100.0*sum(v13)/sum(v13+v22),2) lula_t2, round(100.0*sum(t1_13)/sum(t1_13+t1_22),2) lula_t1,
         round(100.0*sum(v13)/sum(v13+v22)-100.0*sum(t1_13)/sum(t1_13+t1_22),2) swing_pp
  FROM d GROUP BY 1 ORDER BY 1""")

show('2026: correlação por seção do % sem biometria T1 x T2, e da variação T1->T2 do % sem biometria com o swing', """
  SELECT round(corr(100.0*biom_nh/comparecimento, 100.0*t1_biom_nh/t1_comparecimento),3) corr_pb_t1_t2,
         round(corr(100.0*biom_nh/comparecimento - 100.0*t1_biom_nh/t1_comparecimento,
                    100.0*v13/(v13+v22) - 100.0*t1_13/(t1_13+t1_22)),3) corr_var_pb_swing
  FROM s WHERE v13+v22>0 AND t1_13+t1_22>0 AND t1_comparecimento>0""")

show('Aritmética: % Lula necessário entre os votos sem biometria para explicar toda a margem, com os demais empatados 50/50', """
  SELECT sum(v13) v13, sum(v22) v22, sum(v13-v22) margem, sum(biom_nh) sem_biom,
         round(100.0*(0.5*(sum(v13+v22)-sum(biom_nh)) + sum(biom_nh) - sum(v22))/sum(biom_nh),1) pct_lula_necessario FROM s""")
