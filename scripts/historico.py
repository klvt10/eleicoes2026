"""Histórico de cada seção/cidade/UF de 2026: presidente 2022 e municipais 2024, e posicionamento político.

Saídas em dados/historico/:
  partidos.csv              nota de cada partido por UF (método a) e bloco fixo (método b)
  secao.parquet, cidade.parquet, uf.parquet

Presidente 2022 (Lula 13 x Bolsonaro 22), mesmas contas de votos_liquidos.py:
  l22 = Lula no 2º turno (% dos válidos); liq22 = comparecimento T2 - (Lula T1 + Bolsonaro T1);
  gl22 / gb22 = ganho de Lula / de Bolsonaro entre os turnos; pct22 = gl22 / (gl22 + gb22).
  Seções: a de mesmo número em 2022 (secao_2026_historico), com a confiança do cruzamento; cidades e UFs: soma direta de 2022.

Posicionamento pelo voto em vereador 2024 (1º turno; voto no candidato conta para o partido dele, voto de legenda também):
  (a) nota do partido na UF = média do Lula 2º turno 2022 das seções onde o partido teve votos, ponderada pelos votos
      (partido com menos de 2000 votos na UF usa a nota nacional). Índice municipal do lugar = média das notas
      ponderada pelos votos de vereador: "pelo voto em vereador, o lugar parece X% Lula".
  (b) blocos fixos esquerda/centro/direita (BLOCO abaixo, para ajustar): % dos votos de vereador em cada bloco.
"""
import os, duckdb

R = os.path.join(os.path.dirname(__file__), '..')
P = f'{R}/dados/parquet'
OUT = f'{R}/dados/historico'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()

BLOCO = {  # método (b): classificação editorial, para revisar
    'esquerda': ['PT', 'PC do B', 'PV', 'PSOL', 'REDE', 'PSB', 'PDT', 'PCB', 'PSTU', 'PCO', 'UP'],
    'centro': ['MDB', 'PSD', 'PSDB', 'CIDADANIA', 'PODE', 'AVANTE', 'SOLIDARIEDADE', 'PMB', 'AGIR', 'MOBILIZA', 'PRD'],
    'direita': ['PL', 'PP', 'REPUBLICANOS', 'UNIÃO', 'NOVO', 'PRTB', 'DC'],
}
con.execute("CREATE TABLE bloco (sg_partido VARCHAR, bloco VARCHAR)")
con.executemany("INSERT INTO bloco VALUES (?, ?)", [(p, b) for b, ps in BLOCO.items() for p in ps])
con.execute(f"CREATE TABLE partido AS SELECT DISTINCT nr_partido, sg_partido FROM '{P}/e2024_candidatos.parquet'")

# 2022 por seção de 2022 (Lula 2º turno), para dar nota aos partidos
con.execute(f"""CREATE TABLE s22 AS SELECT uf, cd_municipio, nr_zona, nr_secao, t2_13, t2_22
                FROM '{P}/e2022_presidente_secao_wide.parquet' WHERE t2_13 + t2_22 > 0""")
# vereador 2024 por seção e partido
con.execute(f"""
CREATE TABLE ver AS
SELECT uf, cd_municipio, nr_zona, nr_secao,
       CASE WHEN nr_votavel >= 10000 THEN nr_votavel // 1000 ELSE nr_votavel END nr_partido, sum(votos) votos
FROM '{P}/e2024_vereador_votos_secao.parquet'
WHERE turno = 1 AND nr_votavel NOT IN (95, 96, 97, 98)
GROUP BY ALL""")
con.execute("""
CREATE TABLE nota AS
WITH j AS (SELECT v.uf, v.nr_partido, v.votos, 100.0 * s.t2_13 / (s.t2_13 + s.t2_22) l22
           FROM ver v JOIN s22 s USING (uf, cd_municipio, nr_zona, nr_secao)),
     nac AS (SELECT nr_partido, sum(votos * l22) / sum(votos) nota_br, sum(votos) votos_br FROM j GROUP BY 1),
     est AS (SELECT uf, nr_partido, sum(votos * l22) / sum(votos) nota_uf, sum(votos) votos_uf FROM j GROUP BY ALL)
SELECT est.uf, est.nr_partido, p.sg_partido, coalesce(b.bloco, 'centro') bloco, votos_uf, nota_uf, nota_br,
       CASE WHEN votos_uf >= 2000 THEN nota_uf ELSE nota_br END nota
FROM est JOIN nac USING (nr_partido) LEFT JOIN partido p USING (nr_partido) LEFT JOIN bloco b USING (sg_partido)""")
con.execute(f"COPY (SELECT * FROM nota ORDER BY uf, nota DESC) TO '{OUT}/partidos.csv' (HEADER)")
print(con.execute("""SELECT sg_partido, bloco, round(sum(votos_uf * nota_br) / sum(votos_uf), 1) nota_br, sum(votos_uf) votos
                     FROM nota GROUP BY ALL ORDER BY nota_br DESC""").df().to_string())

# vereador agregado por qualquer chave
def vereador(chave):
    return f"""
    SELECT {chave}, sum(votos) ver_votos,
      round(sum(votos * n.nota) / sum(votos), 1) i24,
      round(100.0 * sum(votos) FILTER (n.bloco = 'esquerda') / sum(votos), 1) esq24,
      round(100.0 * sum(votos) FILTER (n.bloco = 'centro') / sum(votos), 1) cen24,
      round(100.0 * sum(votos) FILTER (n.bloco = 'direita') / sum(votos), 1) dir24
    FROM ver v JOIN nota n USING (uf, nr_partido) GROUP BY ALL"""

# prefeito 2024: partido mais votado na seção (1º turno) e eleito na cidade
con.execute(f"""
CREATE TABLE pref_sec AS
SELECT uf, cd_municipio, nr_zona, nr_secao, arg_max(c.sg_partido, v.votos) pref24_partido_secao
FROM (SELECT uf, cd_municipio, nr_zona, nr_secao, sq_candidato, sum(votos) votos FROM '{P}/e2024_prefeito_votos_secao.parquet'
      WHERE turno = 1 AND nr_votavel NOT IN (95, 96, 97, 98) GROUP BY ALL) v
JOIN (SELECT DISTINCT sq_candidato, sg_partido FROM '{P}/e2024_candidatos.parquet') c USING (sq_candidato)
GROUP BY ALL""")
# Eleitos 2024: arquivo de candidatos mais recente do TSE (dados/2024/raw/consulta_cand_2024_BRASIL.csv, versão de
# 27/10/2026), pegando em cada município a eleição mais recente (inclui as suplementares de 2025-2026).
# Governador 2022 continua da tabela montada antes.
con.execute(f"""
CREATE TABLE eleitos AS
SELECT ano, cargo, uf, cd_municipio, nm_urna, sg_partido, NULL::DATE dt_eleicao
FROM '{P}/eleitos_gov2022_pref_ver2024.parquet' WHERE ano = 2022
UNION ALL
SELECT 2024, cargo, uf, cd_municipio, nm_urna, sg_partido, dt_eleicao FROM (
  SELECT CASE CD_CARGO WHEN '11' THEN 'prefeito' ELSE 'vereador' END cargo, SG_UF uf, SG_UE::INT cd_municipio,
         NM_URNA_CANDIDATO nm_urna, SG_PARTIDO sg_partido, strptime(DT_ELEICAO, '%d/%m/%Y')::DATE dt_eleicao,
         max(strptime(DT_ELEICAO, '%d/%m/%Y')::DATE) OVER (PARTITION BY SG_UE, CD_CARGO) ultima
  FROM read_csv('{R}/dados/2024/raw/consulta_cand_2024_BRASIL.csv', delim=';', header=true, encoding='latin-1', all_varchar=true)
  WHERE CD_CARGO IN ('11', '13') AND (DS_SIT_TOT_TURNO = 'ELEITO' OR DS_SIT_TOT_TURNO LIKE 'ELEITO POR%'))
WHERE dt_eleicao = ultima""")
print(con.execute("SELECT cargo, count(DISTINCT cd_municipio), count(*) FROM eleitos WHERE ano = 2024 GROUP BY 1").fetchall())

CAT = """CASE WHEN l22 IS NULL OR l26 IS NULL THEN NULL
              WHEN l22 >= 50 AND l26 >= 50 THEN 'lula_lula' WHEN l22 < 50 AND l26 >= 50 THEN 'virou_lula'
              WHEN l22 >= 50 AND l26 < 50 THEN 'virou_contra' ELSE 'direita_direita' END categoria"""
P22 = """round(100.0 * {a}t2_13 / nullif({a}t2_13 + {a}t2_22, 0), 1) l22,
         ({a}t2_comparecimento - {a}t1_13 - {a}t1_22)::INT liq22, ({a}t2_13 - {a}t1_13)::INT gl22, ({a}t2_22 - {a}t1_22)::INT gb22,
         ({a}t2_brancos + {a}t2_nulos)::INT bn22"""

# 2026 por seção
con.execute(f"""
CREATE TABLE s26 AS
SELECT uf, cd_municipio, nr_zona, nr_secao, sum(votos) FILTER (nr_votavel = 13) l2, sum(votos) FILTER (nr_votavel = 22) f2
FROM '{P}/t2_votos_secao.parquet' WHERE nr_votavel IN (13, 22) GROUP BY ALL""")

# ---- seções (2022: a de mesmo número, só quando existe; confiança do cruzamento ao lado)
con.execute(f"""
COPY (
  WITH h AS (SELECT uf, cd_municipio, nr_zona, nr_secao, match_2022, match_2024,
               CASE WHEN match_2022 THEN p22_t1_13 END t1_13, CASE WHEN match_2022 THEN p22_t1_22 END t1_22,
               CASE WHEN match_2022 THEN p22_t2_13 END t2_13, CASE WHEN match_2022 THEN p22_t2_22 END t2_22,
               CASE WHEN match_2022 THEN p22_t2_comparecimento END t2_comparecimento,
               CASE WHEN match_2022 THEN p22_t2_brancos END t2_brancos, CASE WHEN match_2022 THEN p22_t2_nulos END t2_nulos
             FROM '{P}/secao_2026_historico.parquet'),
       v AS ({vereador('uf, cd_municipio, nr_zona, nr_secao')}),
       a AS (
         SELECT h.uf, h.cd_municipio, h.nr_zona, h.nr_secao, {P22.format(a='h.')},
                c.confianca_2022 conf22, c.confianca_2024 conf24,
                round(100.0 * s.l2 / nullif(s.l2 + s.f2, 0), 1) l26,
                CASE WHEN h.match_2024 THEN v.i24 END i24, CASE WHEN h.match_2024 THEN v.esq24 END esq24,
                CASE WHEN h.match_2024 THEN v.cen24 END cen24, CASE WHEN h.match_2024 THEN v.dir24 END dir24,
                CASE WHEN h.match_2024 THEN ps.pref24_partido_secao END pref24_partido_secao
         FROM h LEFT JOIN s26 s USING (uf, cd_municipio, nr_zona, nr_secao)
         LEFT JOIN '{P}/secao_2026_confianca.parquet' c USING (uf, cd_municipio, nr_zona, nr_secao)
         LEFT JOIN v USING (uf, cd_municipio, nr_zona, nr_secao)
         LEFT JOIN pref_sec ps USING (uf, cd_municipio, nr_zona, nr_secao))
  SELECT *, {CAT} FROM a
) TO '{OUT}/secao.parquet' (FORMAT parquet)""")

# ---- cidades e UFs: 2022 somado direto
for nivel, chave in (('cidade', 'uf, cd_municipio'), ('uf', 'uf')):
    extra = ("""(SELECT any_value(e.sg_partido) FROM eleitos e WHERE e.ano = 2024 AND e.cargo = 'prefeito' AND e.uf = a.uf AND e.cd_municipio = a.cd_municipio) pref24_partido,
                (SELECT any_value(e.nm_urna) FROM eleitos e WHERE e.ano = 2024 AND e.cargo = 'prefeito' AND e.uf = a.uf AND e.cd_municipio = a.cd_municipio) pref24_nome"""
             if nivel == 'cidade' else
             """(SELECT any_value(e.sg_partido) FROM eleitos e WHERE e.ano = 2022 AND e.cargo = 'governador' AND e.uf = a.uf) gov22_partido,
                (SELECT any_value(e.nm_urna) FROM eleitos e WHERE e.ano = 2022 AND e.cargo = 'governador' AND e.uf = a.uf) gov22_nome""")
    con.execute(f"""
    COPY (
      WITH w AS (SELECT {chave}, sum(t1_13) t1_13, sum(t1_22) t1_22, sum(t2_13) t2_13, sum(t2_22) t2_22,
                        sum(t2_comparecimento) t2_comparecimento, sum(t2_brancos) t2_brancos, sum(t2_nulos) t2_nulos
                 FROM '{P}/e2022_presidente_secao_wide.parquet' GROUP BY ALL),
           s AS (SELECT {chave}, round(100.0 * sum(l2) / nullif(sum(l2) + sum(f2), 0), 1) l26 FROM s26 GROUP BY ALL),
           v AS ({vereador(chave)}),
           a AS (SELECT s.*, {P22.format(a='w.')}, v.i24, v.esq24, v.cen24, v.dir24
                 FROM s LEFT JOIN w USING ({chave}) LEFT JOIN v USING ({chave}))
      SELECT a.*, {CAT}, {extra} FROM a
    ) TO '{OUT}/{nivel}.parquet' (FORMAT parquet)""")

for nivel in ('secao', 'cidade', 'uf'):
    print(nivel, con.execute(f"""SELECT count(*), count(l22), count(i24), round(avg(l22), 1), round(avg(i24), 1)
                                 FROM '{OUT}/{nivel}.parquet'""").fetchone())
print(con.execute(f"SELECT categoria, count(*) FROM '{OUT}/cidade.parquet' GROUP BY 1 ORDER BY 2 DESC").fetchall())
print(con.execute(f"SELECT * FROM '{OUT}/uf.parquet' WHERE uf IN ('SP', 'BA', 'SC')").df().to_string())
print(con.execute(f"SELECT * FROM '{OUT}/cidade.parquet' WHERE cd_municipio IN (58190, 58033)").df().to_string())

# ---- cidade: prefeito 2024 (votos válidos, 2º colocado, coligação) e Câmara eleita por partido
con.execute(f"""
COPY (
  WITH v AS (SELECT p.uf, p.cd_municipio, p.turno, p.sq_candidato, sum(p.votos) votos
             FROM '{P}/e2024_prefeito_votos_secao.parquet' p WHERE p.nr_votavel NOT IN (95, 96, 97, 98) GROUP BY ALL),
       fim AS (SELECT uf, cd_municipio, max(turno) turno FROM v GROUP BY ALL),
       r AS (SELECT v.*, c.nm_urna, c.sg_partido, c.composicao_coligacao,
                    100.0 * v.votos / sum(v.votos) OVER (PARTITION BY v.uf, v.cd_municipio) pct,
                    row_number() OVER (PARTITION BY v.uf, v.cd_municipio ORDER BY v.votos DESC) pos
             FROM v JOIN fim USING (uf, cd_municipio, turno)
             JOIN (SELECT DISTINCT sq_candidato, nm_urna, sg_partido, composicao_coligacao FROM '{P}/e2024_candidatos.parquet') c USING (sq_candidato)),
       cam AS (SELECT uf, cd_municipio, sum(n)::INT ver24_total,
                      string_agg(sg_partido || ':' || n, ',' ORDER BY n DESC, sg_partido) ver24_partidos
               FROM (SELECT uf, cd_municipio, sg_partido, count(*) n FROM eleitos WHERE cargo = 'vereador' GROUP BY ALL) GROUP BY ALL)
  , sup AS (SELECT uf, cd_municipio, max(dt_eleicao) pref24_suplementar FROM eleitos
             WHERE ano = 2024 AND cargo = 'prefeito' AND dt_eleicao > DATE '2024-10-27' GROUP BY ALL)
  SELECT f.uf, f.cd_municipio, f.turno pref24_turno, any_value(sup.pref24_suplementar) pref24_suplementar,
         CASE WHEN any_value(sup.pref24_suplementar) IS NULL THEN round(any_value(r.pct) FILTER (pos = 1), 1) END pref24_pct,
         any_value(r.composicao_coligacao) FILTER (pos = 1) pref24_colig,
         any_value(r.nm_urna) FILTER (pos = 1) pref24_1nome, any_value(r.sg_partido) FILTER (pos = 1) pref24_1partido,
         any_value(r.nm_urna) FILTER (pos = 2) pref24_2nome, any_value(r.sg_partido) FILTER (pos = 2) pref24_2partido,
         round(any_value(r.pct) FILTER (pos = 2), 1) pref24_2pct,
         any_value(cam.ver24_total) ver24_total, any_value(cam.ver24_partidos) ver24_partidos
  FROM fim f LEFT JOIN r USING (uf, cd_municipio) LEFT JOIN cam USING (uf, cd_municipio) LEFT JOIN sup USING (uf, cd_municipio)
  GROUP BY ALL
) TO '{OUT}/cidade_municipal.parquet' (FORMAT parquet)""")
print(con.execute(f"SELECT * FROM '{OUT}/cidade_municipal.parquet' WHERE cd_municipio IN (58190, 71072)").df().to_string())
