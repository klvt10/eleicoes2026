"""Comparativo presidente x governador x deputados (1º turno 2026) por UF e cidade, para a página site/comparativo.html.

Votos válidos (nominais + legenda) de cada cargo na cidade:
  presidente: % Lula, % Flávio, % outros (1º turno) e % Lula no 2º turno (só Lula e Flávio)
  governador e senador: % do campo Lula, do campo Flávio e dos demais (campo de cada candidato: campo_cargos_2026.py;
    senador tem dois votos por eleitor, a soma dos votos válidos é a base)
  deputado federal e estadual: % dos blocos esquerda / centro / direita (partido do candidato ou da legenda)
Discrepância: Lula no 1º turno menos a referência (campo Lula no governo, ou esquerda nos deputados), comparada com a
média do estado: desvio = (Lula − ref) da cidade − (Lula − ref) do estado, em pontos. Quem está muito acima deu a Lula
mais do que o resto do estado dado o voto local para os outros cargos.

Saídas: site/dados/comparativo/uf.json, cidades.json, partidos.json
"""
import os, json, duckdb
R = os.path.join(os.path.dirname(__file__), '..')
P, OUT = f'{R}/dados/parquet', f'{R}/site/dados/comparativo'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()
BLOCO = {
    'esquerda': ['PT', 'PC do B', 'PCDOB', 'PV', 'PSOL', 'REDE', 'PSB', 'PDT', 'PCB', 'PSTU', 'PCO', 'UP'],
    'centro': ['MDB', 'PSD', 'PSDB', 'CIDADANIA', 'PODE', 'AVANTE', 'SOLIDARIEDADE', 'PMB', 'DEMOCRATA', 'AGIR', 'MOBILIZA', 'PRD'],
    'direita': ['PL', 'PP', 'REPUBLICANOS', 'UNIÃO', 'NOVO', 'PRTB', 'DC', 'MISSÃO'],
}
con.execute("CREATE TABLE bloco (sg_partido VARCHAR, bloco VARCHAR)")
con.executemany("INSERT INTO bloco VALUES (?, ?)", [(p, b) for b, ps in BLOCO.items() for p in ps])
con.execute(f"""CREATE TABLE c AS SELECT t.*, coalesce(b.bloco, 'centro') bloco, b.bloco IS NULL sem_bloco
  FROM '{P}/t1_cargos_cidade.parquet' t LEFT JOIN bloco b ON upper(t.sg_partido) = upper(b.sg_partido)
  WHERE uf <> 'ZZ' AND tipo_votavel IN ('Nominal', 'Legenda')""")
con.execute("UPDATE c SET cd_cargo = 7 WHERE cd_cargo = 8")  # deputado distrital (DF) conta como estadual
faltam = con.execute("SELECT DISTINCT sg_partido, sum(votos) v FROM c WHERE sem_bloco AND sg_partido IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall()
if faltam: print('PARTIDOS SEM BLOCO (contados como centro):', faltam)
con.execute(f"""CREATE TABLE gov AS SELECT uf, nr_votavel, nome, partido, campo FROM '{R}/dados/gov2026/candidatos_gov.parquet'""")
con.execute(f"""CREATE TABLE sen AS SELECT uf, nr_votavel, nome, partido, campo FROM '{R}/dados/sen2026/candidatos_sen.parquet'""")

# por cidade: uma linha com todas as métricas
con.execute(f"""
CREATE TABLE cid AS
WITH pres AS (
  SELECT uf, cd_municipio, any_value(nm_municipio) nome, sum(votos) vp,
    sum(votos) FILTER (nr_votavel = 13) l1, sum(votos) FILTER (nr_votavel = 22) f1
  FROM c WHERE cd_cargo = 1 GROUP BY 1, 2),
t2 AS (SELECT uf, cd_municipio, sum(v13) l2, sum(v22) f2 FROM '{P}/bweb_2026_t2_secao.parquet' GROUP BY 1, 2),
g AS (
  SELECT c.uf, cd_municipio, sum(votos) vg,
    coalesce(sum(votos) FILTER (campo = 'lula'), 0) gl, coalesce(sum(votos) FILTER (campo = 'flavio'), 0) gf,
    arg_max(gov.nome || ' (' || gov.partido || ')', votos) gov_lider, max(votos) gov_lider_votos
  FROM c LEFT JOIN gov ON gov.uf = c.uf AND gov.nr_votavel = c.nr_votavel WHERE cd_cargo = 3 GROUP BY 1, 2),
sn AS (
  SELECT c.uf, cd_municipio, sum(votos) vs,
    coalesce(sum(votos) FILTER (campo = 'lula'), 0) sl, coalesce(sum(votos) FILTER (campo = 'flavio'), 0) sf,
    arg_max(sen.nome || ' (' || sen.partido || ')', votos) sen_lider, max(votos) sen_lider_votos
  FROM c LEFT JOIN sen ON sen.uf = c.uf AND sen.nr_votavel = c.nr_votavel WHERE cd_cargo = 5 GROUP BY 1, 2),
d AS (
  SELECT uf, cd_municipio, cd_cargo, sum(votos) v,
    coalesce(sum(votos) FILTER (bloco = 'esquerda'), 0) esq, coalesce(sum(votos) FILTER (bloco = 'centro'), 0) cen, coalesce(sum(votos) FILTER (bloco = 'direita'), 0) dir
  FROM c WHERE cd_cargo IN (6, 7) GROUP BY 1, 2, 3),
pt AS (SELECT uf, cd_municipio, cd_cargo, coalesce(sum(votos) FILTER (upper(sg_partido) = 'PT'), 0) pt, coalesce(sum(votos) FILTER (upper(sg_partido) = 'PL'), 0) pl
  FROM c WHERE cd_cargo IN (6, 7) GROUP BY 1, 2, 3)
SELECT p.uf, p.cd_municipio cd, p.nome, p.vp::BIGINT votos,
  round(100.0 * p.l1 / p.vp, 2) l1, round(100.0 * p.f1 / p.vp, 2) f1, round(100.0 * (p.vp - p.l1 - p.f1) / p.vp, 2) o1,
  round(100.0 * t2.l2 / nullif(t2.l2 + t2.f2, 0), 2) l2,
  round(100.0 * g.gl / nullif(g.vg, 0), 2) gl, round(100.0 * g.gf / nullif(g.vg, 0), 2) gf, round(100.0 * (g.vg - g.gl - g.gf) / nullif(g.vg, 0), 2) go,
  g.gov_lider, round(100.0 * g.gov_lider_votos / nullif(g.vg, 0), 1) gov_lider_pct,
  round(100.0 * sn.sl / nullif(sn.vs, 0), 2) sl, round(100.0 * sn.sf / nullif(sn.vs, 0), 2) sf, round(100.0 * (sn.vs - sn.sl - sn.sf) / nullif(sn.vs, 0), 2) so,
  sn.sen_lider, round(100.0 * sn.sen_lider_votos / nullif(sn.vs, 0), 1) sen_lider_pct,
  round(100.0 * df.esq / nullif(df.v, 0), 2) df_esq, round(100.0 * df.cen / nullif(df.v, 0), 2) df_cen, round(100.0 * df.dir / nullif(df.v, 0), 2) df_dir,
  round(100.0 * de.esq / nullif(de.v, 0), 2) de_esq, round(100.0 * de.cen / nullif(de.v, 0), 2) de_cen, round(100.0 * de.dir / nullif(de.v, 0), 2) de_dir,
  round(100.0 * ptf.pt / nullif(df.v, 0), 2) df_pt, round(100.0 * ptf.pl / nullif(df.v, 0), 2) df_pl,
  round(100.0 * pte.pt / nullif(de.v, 0), 2) de_pt, round(100.0 * pte.pl / nullif(de.v, 0), 2) de_pl
FROM pres p
LEFT JOIN t2 USING (uf, cd_municipio) LEFT JOIN g USING (uf, cd_municipio) LEFT JOIN sn USING (uf, cd_municipio)
LEFT JOIN d df ON df.uf = p.uf AND df.cd_municipio = p.cd_municipio AND df.cd_cargo = 6
LEFT JOIN d de ON de.uf = p.uf AND de.cd_municipio = p.cd_municipio AND de.cd_cargo = 7
LEFT JOIN pt ptf ON ptf.uf = p.uf AND ptf.cd_municipio = p.cd_municipio AND ptf.cd_cargo = 6
LEFT JOIN pt pte ON pte.uf = p.uf AND pte.cd_municipio = p.cd_municipio AND pte.cd_cargo = 7""")

# por UF e Brasil: mesmas contas sobre os totais
def agreg(chave, nome):
    return f"""
    WITH pres AS (SELECT {chave} k, sum(votos) vp, sum(votos) FILTER (nr_votavel = 13) l1, sum(votos) FILTER (nr_votavel = 22) f1 FROM c WHERE cd_cargo = 1 GROUP BY 1),
    t2 AS (SELECT {chave.replace('uf', 'uf')} k, sum(v13) l2, sum(v22) f2 FROM '{P}/bweb_2026_t2_secao.parquet' WHERE uf <> 'ZZ' GROUP BY 1),
    g AS (SELECT {chave.replace('uf', 'c.uf')} k, sum(votos) vg, coalesce(sum(votos) FILTER (campo = 'lula'), 0) gl, coalesce(sum(votos) FILTER (campo = 'flavio'), 0) gf
          FROM c LEFT JOIN gov ON gov.uf = c.uf AND gov.nr_votavel = c.nr_votavel WHERE cd_cargo = 3 GROUP BY 1),
    sn AS (SELECT {chave.replace('uf', 'c.uf')} k, sum(votos) vs, coalesce(sum(votos) FILTER (campo = 'lula'), 0) sl, coalesce(sum(votos) FILTER (campo = 'flavio'), 0) sf
          FROM c LEFT JOIN sen ON sen.uf = c.uf AND sen.nr_votavel = c.nr_votavel WHERE cd_cargo = 5 GROUP BY 1),
    d AS (SELECT {chave} k, cd_cargo, sum(votos) v, coalesce(sum(votos) FILTER (bloco = 'esquerda'), 0) esq, coalesce(sum(votos) FILTER (bloco = 'centro'), 0) cen,
          coalesce(sum(votos) FILTER (bloco = 'direita'), 0) dir, coalesce(sum(votos) FILTER (upper(sg_partido) = 'PT'), 0) pt, coalesce(sum(votos) FILTER (upper(sg_partido) = 'PL'), 0) pl
          FROM c WHERE cd_cargo IN (6, 7) GROUP BY 1, 2)
    SELECT p.k uf, {nome} nome, p.vp::BIGINT votos,
      round(100.0 * p.l1 / p.vp, 2) l1, round(100.0 * p.f1 / p.vp, 2) f1, round(100.0 * (p.vp - p.l1 - p.f1) / p.vp, 2) o1,
      round(100.0 * t2.l2 / (t2.l2 + t2.f2), 2) l2,
      round(100.0 * g.gl / g.vg, 2) gl, round(100.0 * g.gf / g.vg, 2) gf, round(100.0 * (g.vg - g.gl - g.gf) / g.vg, 2) go,
      round(100.0 * sn.sl / sn.vs, 2) sl, round(100.0 * sn.sf / sn.vs, 2) sf, round(100.0 * (sn.vs - sn.sl - sn.sf) / sn.vs, 2) so,
      round(100.0 * df.esq / df.v, 2) df_esq, round(100.0 * df.cen / df.v, 2) df_cen, round(100.0 * df.dir / df.v, 2) df_dir,
      round(100.0 * de.esq / de.v, 2) de_esq, round(100.0 * de.cen / de.v, 2) de_cen, round(100.0 * de.dir / de.v, 2) de_dir,
      round(100.0 * df.pt / df.v, 2) df_pt, round(100.0 * df.pl / df.v, 2) df_pl, round(100.0 * de.pt / de.v, 2) de_pt, round(100.0 * de.pl / de.v, 2) de_pl
    FROM pres p JOIN t2 USING (k) JOIN g USING (k) JOIN sn USING (k)
    JOIN d df ON df.k = p.k AND df.cd_cargo = 6 JOIN d de ON de.k = p.k AND de.cd_cargo = 7"""
con.execute(f"CREATE TABLE ufs AS SELECT * FROM ({agreg('uf', 'p.k')}) UNION ALL SELECT * FROM ({agreg(chr(39) + 'BR' + chr(39), chr(39) + 'Brasil' + chr(39))})")
# governador por UF: campo de cada candidato principal, para a legenda
govtxt = con.execute("""SELECT uf, list(struct_pack(nome := nome, partido := partido, campo := campo, votos := votos_t1, pct := round(100.0 * votos_t1 / tot, 1)) ORDER BY votos_t1 DESC)
  FILTER (votos_t1 >= 0.02 * tot) FROM (SELECT *, sum(votos_t1) OVER (PARTITION BY uf) tot FROM read_parquet(?)) GROUP BY 1""",
  [f'{R}/dados/gov2026/candidatos_gov.parquet']).fetchall()
govtxt = {u: [dict(x) for x in l] for u, l in govtxt}
sentxt = con.execute("""SELECT uf, list(struct_pack(nome := nome, partido := partido, campo := campo, votos := votos_t1, pct := round(100.0 * votos_t1 / tot, 1)) ORDER BY votos_t1 DESC)
  FILTER (votos_t1 >= 0.03 * tot) FROM (SELECT *, sum(votos_t1) OVER (PARTITION BY uf) tot FROM read_parquet(?)) GROUP BY 1""",
  [f'{R}/dados/sen2026/candidatos_sen.parquet']).fetchall()
sentxt = {u: [dict(x) for x in l] for u, l in sentxt}

def rows(sql):
    cur = con.execute(sql); cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
dump = lambda o, p: json.dump(o, open(p, 'w'), separators=(',', ':'), ensure_ascii=False, default=str)
ufs = rows("SELECT * FROM ufs ORDER BY (uf = 'BR') DESC, uf")
for u in ufs: u['gov'] = govtxt.get(u['uf'], []); u['sen'] = sentxt.get(u['uf'], [])
# detalhe da presidencial por UF e Brasil: candidatos do 1º turno, brancos, nulos, válidos, comparecimento, abstenções, aptos, nos dois turnos
cands = con.execute(f"""SELECT k, nr_votavel, any_value(nm_votavel) nome, any_value(sg_partido) partido, sum(votos)::BIGINT votos
  FROM (SELECT uf k, * FROM '{P}/t1_cargos_cidade.parquet' UNION ALL SELECT 'BR' k, * FROM '{P}/t1_cargos_cidade.parquet')
  WHERE cd_cargo = 1 AND uf <> 'ZZ' AND tipo_votavel IN ('Nominal', 'Legenda') GROUP BY 1, 2 ORDER BY 1, 5 DESC""").fetchall()
tot = {}
for t in (1, 2):
    for k, l, f, b, n, comp, aptos, val in con.execute(f"""SELECT k, sum(v13), sum(v22), sum(brancos), sum(nulos), sum(comparecimento), sum(aptos), sum(total_votos - brancos - nulos)
        FROM (SELECT uf k, * FROM '{P}/bweb_2026_t{t}_secao.parquet' UNION ALL SELECT 'BR' k, * FROM '{P}/bweb_2026_t{t}_secao.parquet') WHERE uf <> 'ZZ' GROUP BY 1""").fetchall():
        tot.setdefault(k, {})[f't{t}'] = {'l': int(l), 'f': int(f), 'brancos': int(b), 'nulos': int(n), 'validos': int(val), 'comp': int(comp), 'aptos': int(aptos), 'abst': int(aptos - comp)}
gov_el = {r[0]: {'nome': r[1], 'partido': r[2], 'turno': r[3], 'pct': r[4]} for r in con.execute(f"SELECT uf, gov26_nome, gov26_partido, gov26_turno, gov26_pct FROM '{R}/dados/gov2026/governador.parquet'").fetchall()}
for u in ufs:
    u['pres'] = {'cands': [{'nr': c[1], 'nome': c[2], 'partido': c[3], 'votos': c[4]} for c in cands if c[0] == u['uf']], **tot.get(u['uf'], {})}
    u['gov_eleito'] = gov_el.get(u['uf'])
dump(ufs, f'{OUT}/uf.json')
dump(rows("SELECT * FROM cid ORDER BY uf, nome"), f'{OUT}/cidades.json')
dump(rows("""SELECT upper(sg_partido) partido, any_value(bloco) bloco, sum(votos) FILTER (cd_cargo = 6)::BIGINT dep_federal,
             sum(votos) FILTER (cd_cargo = 7)::BIGINT dep_estadual FROM c WHERE cd_cargo IN (6, 7) GROUP BY 1 ORDER BY 3 DESC"""), f'{OUT}/partidos.json')
print(con.execute("SELECT count(*) FROM cid").fetchone(), 'cidades')
print(con.execute("SELECT uf, nome, votos, l1, f1, l2, gl, gf, go, sl, sf, so, df_esq, df_dir, de_esq, de_dir FROM ufs ORDER BY (uf='BR') DESC, uf").fetchdf().to_string(index=False))
