"""Estudos com o perfil do eleitorado por seção.

1. Continuidade: a seção 2026 tem o mesmo eleitorado da seção de mesmo número em 2022/2024?
   Distância de variação total (TVD) entre distribuições gênero x escolaridade x faixa etária,
   comparada com duas referências: outra seção do mesmo local e outra seção do mesmo município.
2. Virada T1->T2 de 2026 (Lula % de 13+22) contra perfil da seção, dentro do município.
"""
import os, json, duckdb, numpy as np, pandas as pd

D = os.path.join(os.path.dirname(__file__), '..', 'dados')
P = f'{D}/parquet'
OUT = os.path.join(os.path.dirname(__file__), '..', 'estudo', 'ds')
con = duckdb.connect()
con.execute("SET memory_limit='8GB'")

# Células: gênero (2) x escolaridade (4 grupos) x idade (5 grupos)
con.execute(f"""
CREATE TABLE cel AS
SELECT ano, uf, cd_municipio, nr_zona, nr_secao, any_value(nr_local) nr_local,
       cd_genero || '-' || CASE WHEN cd_escolaridade <= 3 THEN 'a' WHEN cd_escolaridade <= 5 THEN 'b'
                                WHEN cd_escolaridade <= 7 THEN 'c' ELSE 'd' END
       || '-' || CASE WHEN cd_faixa_etaria < 2500 THEN 1 WHEN cd_faixa_etaria < 3500 THEN 2
                      WHEN cd_faixa_etaria < 4500 THEN 3 WHEN cd_faixa_etaria < 6000 THEN 4 ELSE 5 END cel,
       sum(qt_eleitores) n
FROM read_parquet('{P}/perfil/*/*.parquet', hive_partitioning=false)
WHERE cd_faixa_etaria > 0 AND cd_genero IN (2, 4)
GROUP BY ALL""")
con.execute("""CREATE TABLE sec AS SELECT ano, uf, cd_municipio, nr_zona, nr_secao, any_value(nr_local) nr_local,
               sum(n) tot FROM cel GROUP BY ALL""")
con.execute("""CREATE TABLE p AS SELECT c.ano, c.uf, c.cd_municipio, c.nr_zona, c.nr_secao, cel, n / tot s
               FROM cel c JOIN sec USING (ano, uf, cd_municipio, nr_zona, nr_secao)""")


def tvd(pares, nome):
    """pares: tabela (uf, cd_municipio, z26, s26, za, sa, ano_ant). Retorna TVD por par."""
    return con.execute(f"""
    WITH a AS (SELECT x.*, p.cel, p.s FROM {pares} x JOIN p ON p.ano = 2026 AND p.uf = x.uf
                 AND p.cd_municipio = x.cd_municipio AND p.nr_zona = x.z26 AND p.nr_secao = x.s26),
         b AS (SELECT x.*, p.cel, p.s FROM {pares} x JOIN p ON p.ano = x.ano_ant AND p.uf = x.uf
                 AND p.cd_municipio = x.cd_municipio AND p.nr_zona = x.za AND p.nr_secao = x.sa)
    SELECT ano_ant, '{nome}' ref, uf, cd_municipio, z26, s26,
           0.5 * sum(abs(coalesce(a.s, 0) - coalesce(b.s, 0))) tvd
    FROM a FULL JOIN b USING (ano_ant, uf, cd_municipio, z26, s26, za, sa, cel)
    GROUP BY ALL""").df()


res = []
for ant in (2022, 2024):
    # mesma zona/seção
    con.execute(f"""CREATE OR REPLACE TABLE par_mesma AS
      SELECT n.uf, n.cd_municipio, n.nr_zona z26, n.nr_secao s26, o.nr_zona za, o.nr_secao sa, {ant} ano_ant
      FROM sec n JOIN sec o USING (uf, cd_municipio, nr_zona, nr_secao) WHERE n.ano = 2026 AND o.ano = {ant}""")
    # referência 1: outra seção do mesmo local no ano anterior (seção vizinha)
    con.execute(f"""CREATE OR REPLACE TABLE par_local AS
      SELECT * FROM (
        SELECT n.uf, n.cd_municipio, n.nr_zona z26, n.nr_secao s26, o.nr_zona za, o.nr_secao sa, {ant} ano_ant,
               row_number() OVER (PARTITION BY n.uf, n.cd_municipio, n.nr_zona, n.nr_secao ORDER BY abs(o.nr_secao - n.nr_secao)) r
        FROM sec n JOIN sec o ON n.uf = o.uf AND n.cd_municipio = o.cd_municipio AND n.nr_zona = o.nr_zona
             AND n.nr_local = o.nr_local AND n.nr_secao <> o.nr_secao
        WHERE n.ano = 2026 AND o.ano = {ant}) WHERE r = 1""")
    # referência 2: seção sorteada do mesmo município
    con.execute(f"""CREATE OR REPLACE TABLE par_mun AS
      WITH o AS (SELECT *, row_number() OVER (PARTITION BY uf, cd_municipio ORDER BY hash(nr_zona, nr_secao, 7)) k,
                        count(*) OVER (PARTITION BY uf, cd_municipio) m FROM sec WHERE ano = {ant}),
           n AS (SELECT *, 1 + hash(nr_zona, nr_secao, 11) % 1000000 h FROM sec WHERE ano = 2026)
      SELECT n.uf, n.cd_municipio, n.nr_zona z26, n.nr_secao s26, o.nr_zona za, o.nr_secao sa, {ant} ano_ant
      FROM n JOIN o ON n.uf = o.uf AND n.cd_municipio = o.cd_municipio AND o.k = 1 + n.h % o.m
      WHERE NOT (o.nr_zona = n.nr_zona AND o.nr_secao = n.nr_secao)""")
    for t, nome in (('par_mesma', 'mesma seção'), ('par_local', 'outra seção do mesmo local'),
                    ('par_mun', 'seção qualquer do município')):
        res.append(tvd(t, nome))
r = pd.concat(res)
tab = (r.groupby(['ano_ant', 'ref']).tvd.describe(percentiles=[.1, .5, .9])
       [['count', '10%', '50%', '90%']].round(3))
print(tab)

# Mesmas seções com confiança do cruzamento por local/aptos
conf = con.execute(f"SELECT uf, cd_municipio, nr_zona z26, nr_secao s26, confianca_2022, confianca_2024 FROM '{P}/secao_2026_confianca.parquet'").df()
m = r[r.ref == 'mesma seção'].merge(conf, on=['uf', 'cd_municipio', 'z26', 's26'])
m['conf'] = np.where(m.ano_ant == 2022, m.confianca_2022, m.confianca_2024)
print(m.groupby(['ano_ant', 'conf']).tvd.describe(percentiles=[.5, .9])[['count', '50%', '90%']].round(3))

# 2. Virada T1 -> T2 x perfil (2026). Usa só seções não agregadas (perfil == aptos ±1%).
v = con.execute(f"""
WITH t AS (SELECT 1 turno, * FROM '{P}/t1_votos_secao.parquet' UNION ALL BY NAME
           SELECT 2 turno, * FROM '{P}/t2_votos_secao.parquet'),
     w AS (SELECT uf, cd_municipio, nr_zona, nr_secao,
             sum(votos) FILTER (turno = 1 AND nr_votavel = 13) l1, sum(votos) FILTER (turno = 1 AND nr_votavel = 22) f1,
             sum(votos) FILTER (turno = 2 AND nr_votavel = 13) l2, sum(votos) FILTER (turno = 2 AND nr_votavel = 22) f2
           FROM t WHERE nr_votavel IN (13, 22) GROUP BY ALL),
     d AS (SELECT uf, cd_municipio, nr_zona, nr_secao, aptos FROM '{P}/t1_detalhe_secao.parquet')
SELECT w.*, d.aptos, ps.* EXCLUDE (ano, uf, cd_municipio, nr_zona, nr_secao, nr_local)
FROM w JOIN d USING (uf, cd_municipio, nr_zona, nr_secao)
JOIN '{P}/perfil_secao.parquet' ps ON ps.ano = 2026 AND ps.uf = w.uf AND ps.cd_municipio = w.cd_municipio
     AND ps.nr_zona = w.nr_zona AND ps.nr_secao = w.nr_secao
WHERE abs(ps.eleitores - d.aptos) <= 0.01 * d.aptos AND w.l1 + w.f1 > 20 AND w.l2 + w.f2 > 20 AND w.uf <> 'ZZ'
""").df()
v['lula1'] = v.l1 / (v.l1 + v.f1) * 100
v['lula2'] = v.l2 / (v.l2 + v.f2) * 100
v['virada'] = v.lula2 - v.lula1
print('seções na análise 2:', len(v), 'de', con.execute(f"SELECT count(*) FROM '{P}/t1_detalhe_secao.parquet'").fetchone()[0])

X = ['p_mulher', 'p_16_17', 'p_18_29', 'p_60mais', 'p_ate_fund_incompleto', 'p_superior', 'lula1']
nomes = {'p_mulher': '% mulheres', 'p_16_17': '% 16-17 anos', 'p_18_29': '% 18-29 anos', 'p_60mais': '% 60+ anos',
         'p_ate_fund_incompleto': '% até fundamental incompleto', 'p_superior': '% superior completo',
         'lula1': 'Lula no 1º turno (%)'}
for c in X[:-1]:
    v[c] *= 100
# decis de cada variável (dentro do Brasil) x virada média ponderada
decis = []
for c in X:
    q = pd.qcut(v[c].rank(method='first'), 10, labels=False) + 1
    g = v.assign(q=q).groupby('q').apply(lambda d: pd.Series({
        'x': np.average(d[c], weights=d.aptos), 'virada': np.average(d.virada, weights=d.aptos)}), include_groups=False)
    for k, row in g.iterrows():
        decis.append({'var': nomes[c], 'decil': int(k), 'x': round(row.x, 2), 'virada': round(row.virada, 3)})
print(pd.DataFrame(decis).pivot(index='decil', columns='var', values='virada').round(2))

# Regressão com efeito fixo de município (demeaning ponderado)
w = v.aptos.values.astype(float)
g = v.uf + '-' + v.cd_municipio.astype(str)
def dm(s):
    mu = (s * w).groupby(g).sum() / pd.Series(w, index=v.index).groupby(g).sum()
    return s - g.map(mu)
Y = dm(v.virada).values
Z = np.column_stack([dm(v[c]).values for c in X])
sw = np.sqrt(w)
beta, *_ = np.linalg.lstsq(Z * sw[:, None], Y * sw, rcond=None)
res_ = Y - Z @ beta
r2 = 1 - (w * res_**2).sum() / (w * Y**2).sum()
dp = v[X].std().values
efeito = [{'var': nomes[c], 'coef_por_pp': round(b, 4), 'efeito_1dp': round(b * s, 3)}
          for c, b, s in zip(X, beta, dp)]
print(pd.DataFrame(efeito), 'R2 dentro do município:', round(r2, 3))

os.makedirs(OUT, exist_ok=True)
json.dump({'tvd': tab.reset_index().to_dict('records'),
           'decis': decis, 'regressao': efeito, 'r2_intra_municipio': round(r2, 3), 'n_secoes': len(v)},
          open(f'{OUT}/perfil_estudos.json', 'w'), ensure_ascii=False, indent=1, default=float)
