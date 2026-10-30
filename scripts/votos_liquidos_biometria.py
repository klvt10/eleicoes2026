"""Votos líquidos x eleitores habilitados sem biometria (campo QT_ELEI_BIOM_SEM_HABILITACAO do boletim de urna).

O boletim diz QUANTOS eleitores de cada seção votaram sem a digital ser reconhecida, não EM QUEM votaram.
Não existe, portanto, "voto líquido dos sem biometria"; tentar estimá-lo por regressão entre seções dá
valores impossíveis (ver relatorios/analise_bweb_2026.txt). O que é exato e está aqui:

  1. Por seção, bairro, cidade e UF: o contingente sem biometria no 1º e no 2º turno (nb1, nb2),
     a fração do comparecimento (pct_nb1, pct_nb2) e a variação entre turnos (dnb), ao lado dos
     votos líquidos já calculados em votos_liquidos.py (liquidos, ganho_lula, ganho_flavio, saldo_mil).
  2. Por cidade e UF: os votos líquidos calculados só nas seções do quartil com MAIS votos sem biometria
     (quartil dentro da UF, pelo 2º turno) e nas demais, lado a lado (sufixos _alto e _resto), e a diferença
     de saldo por mil entre os dois estratos (dif_saldo_mil). Se a liberação sem biometria favorecesse um lado,
     o estrato alto teria saldo sistematicamente deslocado em relação ao resto da mesma cidade.

Saída: dados/votos_liquidos/biometria_<nivel>.csv e .parquet
"""
import os, duckdb
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
P, VL = f'{D}/parquet', f'{D}/votos_liquidos'
con = duckdb.connect()
con.execute(f"""
CREATE TABLE s AS
SELECT v.*, coalesce(b1.biom_nh, 0) nb1, coalesce(b2.biom_nh, 0) nb2,
       b1.comparecimento comp1_bu, b2.comparecimento comp2_bu
FROM '{VL}/secao.parquet' v
LEFT JOIN '{P}/bweb_2026_t1_secao.parquet' b1 USING (uf, cd_municipio, nr_zona, nr_secao)
LEFT JOIN '{P}/bweb_2026_t2_secao.parquet' b2 USING (uf, cd_municipio, nr_zona, nr_secao)""")
print('seções:', con.execute("SELECT count(*), count(comp2_bu), sum(comp2 <> comp2_bu) FROM s").fetchone())
# estrato: quartil de % sem biometria no 2º turno, dentro da UF (exterior fica fora: não tem biometria)
con.execute("""CREATE TABLE q AS
  SELECT *, CASE WHEN uf = 'ZZ' THEN NULL ELSE ntile(4) OVER (PARTITION BY uf ORDER BY 1.0*nb2/nullif(comp2,0)) END quartil FROM s""")

NIVEIS = {'secao': 'uf, cd_municipio, nm_municipio, bairro, nr_zona, nr_secao, nr_local, nm_local',
          'bairro': 'uf, cd_municipio, nm_municipio, bairro', 'cidade': 'uf, cd_municipio, nm_municipio', 'uf': 'uf'}
def agg(filtro, suf):
    return f"""
      count(*) FILTER ({filtro}) secoes{suf}, sum(comp2) FILTER ({filtro}) comp2{suf},
      sum(nb2) FILTER ({filtro}) nb2{suf},
      round(100.0 * sum(nb2) FILTER ({filtro}) / nullif(sum(comp2) FILTER ({filtro}), 0), 2) pct_nb2{suf},
      (sum(comp2) - sum(l1) - sum(f1)) FILTER ({filtro}) liquidos{suf},
      (sum(l2) - sum(l1)) FILTER ({filtro}) ganho_lula{suf}, (sum(f2) - sum(f1)) FILTER ({filtro}) ganho_flavio{suf},
      round(1000.0 * (sum(l2) - sum(l1) - sum(f2) + sum(f1)) FILTER ({filtro}) / nullif((sum(comp2) - sum(l1) - sum(f1)) FILTER ({filtro}), 0), 1) saldo_mil{suf},
      round(1000.0 * (sum(l2) - sum(l1) - sum(f2) + sum(f1)) FILTER ({filtro}) / nullif(sum(comp2) FILTER ({filtro}), 0), 1) saldo_mil_comp{suf},
      round(100.0 * sum(l2) FILTER ({filtro}) / nullif(sum(l2 + f2) FILTER ({filtro}), 0), 2) pct_lula_t2{suf},
      round(100.0 * sum(l1) FILTER ({filtro}) / nullif(sum(l1 + f1) FILTER ({filtro}), 0), 2) pct_lula_13x22_t1{suf}"""
for nivel, chave in NIVEIS.items():
    extra = f", {agg('quartil = 4', '_alto')}, {agg('quartil < 4', '_resto')}" if nivel in ('cidade', 'uf') else ''
    con.execute(f"""
    CREATE OR REPLACE TABLE r_{nivel} AS
    WITH a AS (
      SELECT {chave}, count(*) secoes, sum(aptos) aptos, sum(comp1) comp_t1, sum(comp2) comp_t2,
        sum(nb1) nb1, sum(nb2) nb2, sum(nb2) - sum(nb1) dnb,
        round(100.0 * sum(nb1) / nullif(sum(comp1), 0), 2) pct_nb1, round(100.0 * sum(nb2) / nullif(sum(comp2), 0), 2) pct_nb2,
        sum(l1) lula_t1, sum(f1) flavio_t1, sum(l2) lula_t2, sum(f2) flavio_t2,
        sum(comp2) - sum(l1) - sum(f1) liquidos, sum(l2) - sum(l1) ganho_lula, sum(f2) - sum(f1) ganho_flavio, sum(bn2) branco_nulo_t2
        {extra}
      FROM q GROUP BY ALL)
    SELECT *, round(1000.0 * ganho_lula / nullif(liquidos, 0), 1) lula_mil, round(1000.0 * ganho_flavio / nullif(liquidos, 0), 1) flavio_mil,
      round(1000.0 * (ganho_lula - ganho_flavio) / nullif(liquidos, 0), 1) saldo_mil,
      liquidos < 0.25 * (comp_t1 - lula_t1 - flavio_t1) base_instavel,
      round(1000.0 * (ganho_lula - ganho_flavio) / nullif(comp_t2, 0), 1) saldo_mil_comparecimento
      {", saldo_mil_alto - saldo_mil_resto dif_saldo_mil, saldo_mil_comp_alto - saldo_mil_comp_resto dif_saldo_mil_comp" if extra else ''}
    FROM a ORDER BY pct_nb2 DESC NULLS LAST""")
    con.execute(f"COPY r_{nivel} TO '{VL}/biometria_{nivel}.csv' (HEADER, DELIMITER ';')")
    con.execute(f"COPY r_{nivel} TO '{VL}/biometria_{nivel}.parquet' (FORMAT parquet)")

pd = lambda sql: print(con.sql(sql).fetchdf().to_string(index=False))
print('\n=== Brasil: contingente sem biometria e votos líquidos, estrato alto x resto')
pd("""SELECT sum(nb1) nb1, sum(nb2) nb2, round(100.0*sum(nb1)/sum(comp_t1),2) pct_nb1, round(100.0*sum(nb2)/sum(comp_t2),2) pct_nb2,
   round(1000.0*sum(ganho_lula)/sum(liquidos),1) saldo_lula_mil, round(1000.0*sum(ganho_flavio)/sum(liquidos),1) saldo_flavio_mil,
   round(1000.0*(sum(ganho_lula_alto)-sum(ganho_flavio_alto))/sum(liquidos_alto),1) saldo_mil_alto,
   round(1000.0*(sum(ganho_lula_resto)-sum(ganho_flavio_resto))/sum(liquidos_resto),1) saldo_mil_resto,
   round(100.0*sum(nb2_alto)/sum(comp2_alto),2) pct_nb2_alto, round(100.0*sum(nb2_resto)/sum(comp2_resto),2) pct_nb2_resto FROM r_uf""")
print('\n=== Por UF: % sem biometria nos dois turnos, saldo por mil geral, no estrato alto e no resto')
pd("""SELECT uf, pct_nb1, pct_nb2, dnb, saldo_mil, saldo_mil_alto, saldo_mil_resto, dif_saldo_mil, pct_nb2_alto, pct_nb2_resto,
      round(pct_lula_t2_alto - pct_lula_13x22_t1_alto, 2) swing_alto, round(pct_lula_t2_resto - pct_lula_13x22_t1_resto, 2) swing_resto
   FROM r_uf ORDER BY uf""")
print('\n=== Cidades com 100+ seções: diferença de saldo/mil (estrato alto - resto), distribuição e extremos')
pd("""SELECT count(*) cidades, round(avg(dif_saldo_mil),1) media, round(median(dif_saldo_mil),1) mediana,
      round(quantile_cont(dif_saldo_mil, 0.1),1) p10, round(quantile_cont(dif_saldo_mil, 0.9),1) p90,
      sum(dif_saldo_mil > 0) alto_mais_lula, sum(dif_saldo_mil < 0) alto_mais_flavio
   FROM r_cidade WHERE secoes >= 100 AND NOT base_instavel""")
pd("""SELECT uf, nm_municipio, secoes, pct_nb2, saldo_mil, saldo_mil_alto, saldo_mil_resto, dif_saldo_mil
   FROM r_cidade WHERE secoes >= 100 AND NOT base_instavel ORDER BY dif_saldo_mil DESC LIMIT 10""")
pd("""SELECT uf, nm_municipio, secoes, pct_nb2, saldo_mil, saldo_mil_alto, saldo_mil_resto, dif_saldo_mil
   FROM r_cidade WHERE secoes >= 100 AND NOT base_instavel ORDER BY dif_saldo_mil ASC LIMIT 10""")
print('\n=== Correlação entre cidades (ponderada por comparecimento): % sem biometria e saldo/mil; variação de sem biometria e saldo/mil')
pd("""SELECT round(corr(pct_nb2, saldo_mil_comparecimento),3) corr_pct_nb_saldo,
      round(corr(100.0*dnb/comp_t2, saldo_mil_comparecimento),3) corr_var_nb_saldo,
      round(regr_slope(saldo_mil_comparecimento, pct_nb2),2) slope FROM r_cidade WHERE secoes >= 20 AND uf <> 'ZZ'""")
print('\n=== Capitais e maiores cidades')
pd("""SELECT uf, nm_municipio, secoes, nb1, nb2, pct_nb1, pct_nb2, saldo_mil, saldo_mil_alto, saldo_mil_resto, dif_saldo_mil
   FROM r_cidade WHERE uf <> 'ZZ' ORDER BY comp_t2 DESC LIMIT 20""")
