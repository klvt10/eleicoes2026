"""Votos líquidos em disputa no 2º turno 2026 e quanto cada lado capturou, por seção, bairro, cidade e UF.

Votos líquidos = outros candidatos T1 + brancos T1 + nulos T1 + (comparecimento T2 - comparecimento T1)
               = comparecimento T2 - (Lula T1 + Flávio T1)
Identidade: líquidos = ΔLula + ΔFlávio + (brancos + nulos T2).

Candidato 28 (Leonardo Alves de Araujo) no 1º turno: os arquivos por seção do TSE trazem os votos dele como nominais
(5.246 no país), mas a totalização oficial os conta como nulos (resultado oficial: nulos 3.674.249 = 3.669.003 + 5.246).
Aqui eles entram em brancos/nulos do 1º turno, não em outros candidatos.
Por 1000 líquidos: lula_mil, flavio_mil, bn_mil (somam 1000); saldo_mil = lula_mil - flavio_mil.
"""
import os, duckdb

ANULADOS_T1 = (28,)  # votos nominais que a totalização oficial anulou (ver acima)

D = os.path.join(os.path.dirname(__file__), '..', 'dados')
P = f'{D}/parquet'
OUT = f'{D}/votos_liquidos'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()

anul = ', '.join(map(str, ANULADOS_T1))
con.execute(f"""
CREATE TABLE s AS
WITH v AS (
  SELECT 1 turno, uf, cd_municipio, nr_zona, nr_secao, nr_votavel, votos FROM '{P}/t1_votos_secao.parquet'
  UNION ALL
  SELECT 2, uf, cd_municipio, nr_zona, nr_secao, nr_votavel, votos FROM '{P}/t2_votos_secao.parquet'),
vv AS (
  SELECT uf, cd_municipio, nr_zona, nr_secao,
    coalesce(sum(votos) FILTER (turno = 1 AND nr_votavel = 13), 0) l1,
    coalesce(sum(votos) FILTER (turno = 1 AND nr_votavel = 22), 0) f1,
    coalesce(sum(votos) FILTER (turno = 1 AND nr_votavel NOT IN (13, 22, 95, 96, {anul})), 0) outros1,
    coalesce(sum(votos) FILTER (turno = 1 AND nr_votavel IN ({anul})), 0) anulados1,
    coalesce(sum(votos) FILTER (turno = 2 AND nr_votavel = 13), 0) l2,
    coalesce(sum(votos) FILTER (turno = 2 AND nr_votavel = 22), 0) f2
  FROM v GROUP BY ALL),
d AS (
  SELECT 1 turno, * FROM '{P}/t1_detalhe_secao.parquet' UNION ALL BY NAME
  SELECT 2 turno, * FROM '{P}/t2_detalhe_secao.parquet'),
dd AS (
  SELECT uf, cd_municipio, any_value(nm_municipio) nm_municipio, nr_zona, nr_secao,
    any_value(nr_local) FILTER (turno = 2) nr_local, any_value(nm_local) FILTER (turno = 2) nm_local,
    sum(aptos) FILTER (turno = 1) aptos,
    sum(comparecimento) FILTER (turno = 1) comp1, sum(comparecimento) FILTER (turno = 2) comp2,
    sum(brancos + nulos) FILTER (turno = 1) bn1, sum(brancos + nulos) FILTER (turno = 2) bn2
  FROM d GROUP BY uf, cd_municipio, nr_zona, nr_secao)
SELECT dd.uf, dd.cd_municipio, dd.nm_municipio, coalesce(nullif(trim(b.bairro), ''), '(sem bairro)') bairro,
       dd.nr_zona, dd.nr_secao, dd.nr_local, dd.nm_local, dd.aptos, dd.comp1, dd.comp2,
       vv.l1, vv.f1, vv.outros1, dd.bn1 + vv.anulados1 bn1, vv.l2, vv.f2, dd.bn2
FROM dd JOIN vv USING (uf, cd_municipio, nr_zona, nr_secao)
LEFT JOIN '{P}/local_2026_historico.parquet' b USING (uf, cd_municipio, nr_zona, nr_local)
WHERE dd.comp1 IS NOT NULL AND dd.comp2 IS NOT NULL""")

# Checagem da identidade: líquidos = ΔL + ΔF + bn2 e outros1 + bn1 + Δcomp = comp2 - l1 - f1
print(con.execute("""SELECT count(*),
  sum((comp2 - l1 - f1) <> (l2 - l1) + (f2 - f1) + bn2) quebra_identidade_t2,
  sum(comp1 <> l1 + f1 + outros1 + bn1) quebra_identidade_t1 FROM s""").fetchone())

NIVEIS = {
    'secao': 'uf, cd_municipio, nm_municipio, bairro, nr_zona, nr_secao, nr_local, nm_local',
    'bairro': 'uf, cd_municipio, nm_municipio, bairro',
    'cidade': 'uf, cd_municipio, nm_municipio',
    'uf': 'uf',
}
for nivel, chave in NIVEIS.items():
    con.execute(f"""
    CREATE OR REPLACE TABLE r_{nivel} AS
    WITH a AS (
      SELECT {chave}, count(*) secoes, sum(aptos) aptos,
        sum(l1) lula_t1, sum(f1) flavio_t1, sum(outros1) outros_t1, sum(bn1) branco_nulo_t1,
        sum(comp2) - sum(comp1) var_comparecimento, sum(comp2) comp2,
        sum(comp2) - sum(l1) - sum(f1) liquidos,
        sum(l2) - sum(l1) ganho_lula, sum(f2) - sum(f1) ganho_flavio, sum(bn2) branco_nulo_t2
      FROM s GROUP BY ALL)
    SELECT *,
      round(1000.0 * ganho_lula / nullif(liquidos, 0), 1) lula_mil,
      round(1000.0 * ganho_flavio / nullif(liquidos, 0), 1) flavio_mil,
      round(1000.0 * branco_nulo_t2 / nullif(liquidos, 0), 1) branco_nulo_mil,
      round(1000.0 * (ganho_lula - ganho_flavio) / nullif(liquidos, 0), 1) saldo_mil,
      -- Onde o comparecimento caiu, os líquidos quase se anulam e a escala por mil explode.
      liquidos < 0.25 * (outros_t1 + branco_nulo_t1) base_instavel,
      round(1000.0 * (ganho_lula - ganho_flavio) / nullif(comp2, 0), 1) saldo_mil_comparecimento
    FROM a ORDER BY base_instavel, saldo_mil DESC NULLS LAST""")
    con.execute(f"COPY r_{nivel} TO '{OUT}/{nivel}.csv' (HEADER, DELIMITER ';')")
    con.execute(f"COPY r_{nivel} TO '{OUT}/{nivel}.parquet' (FORMAT parquet)")

print(con.execute("""SELECT sum(liquidos), sum(ganho_lula), sum(ganho_flavio), sum(branco_nulo_t2),
  round(1000.0 * sum(ganho_lula) / sum(liquidos), 1), round(1000.0 * sum(ganho_flavio) / sum(liquidos), 1),
  round(1000.0 * sum(branco_nulo_t2) / sum(liquidos), 1) FROM r_uf""").fetchone())
