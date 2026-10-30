"""Votos líquidos do 2º turno por faixa de % de eleitores habilitados sem biometria na urna (2º turno).
Mesma definição de votos_liquidos.py: líquidos = comp2 - (Lula T1 + Flávio T1) = ΔLula + ΔFlávio + brancos/nulos T2.
Grupos: BR, cada UF e cidades com >= MIN_SECOES seções. Referência 2022 (Lula x Bolsonaro) com a faixa de 2022.
Saída: dados/sem_biometria/faixas.json (consumido pela página) e faixas.csv"""
import os, json, duckdb
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
P, VL, OUT = f'{D}/parquet', f'{D}/votos_liquidos', f'{D}/sem_biometria'
MIN_SECOES = 150
FAIXAS = ['0%', '0-1%', '1-5%', '5-10%', '10-15%', '15-20%', '20-25%', '25-30%', '30-50%', '50%+']
con = duckdb.connect()
FX = """CASE WHEN comp2 = 0 THEN NULL WHEN nb2 = 0 THEN '0%' WHEN pb < 1 THEN '0-1%' WHEN pb < 5 THEN '1-5%' WHEN pb < 10 THEN '5-10%'
        WHEN pb < 15 THEN '10-15%' WHEN pb < 20 THEN '15-20%' WHEN pb < 25 THEN '20-25%' WHEN pb < 30 THEN '25-30%'
        WHEN pb < 50 THEN '30-50%' ELSE '50%+' END"""
con.execute(f"""CREATE TABLE s AS
  SELECT v.uf, v.cd_municipio, v.nm_municipio, v.nr_zona, v.nr_secao, v.comp2 - v.var_comparecimento comp1, v.comp2,
         v.lula_t1 l1, v.flavio_t1 f1, v.lula_t1 + v.ganho_lula l2, v.flavio_t1 + v.ganho_flavio f2,
         b.biom_nh nb2, 100.0 * b.biom_nh / nullif(v.comp2, 0) pb, {FX} faixa
  FROM '{VL}/secao.parquet' v JOIN '{P}/bweb_2026_t2_secao.parquet' b USING (uf, cd_municipio, nr_zona, nr_secao)
  WHERE v.uf <> 'ZZ' AND v.comp2 > 0""")
# 2022: T1 e T2 do arquivo oficial por seção (wide) + biometria do bweb 2022 (2º turno)
con.execute(f"""CREATE TABLE s22 AS
  SELECT w.uf, w.cd_municipio, w.nr_zona, w.nr_secao, w.t1_13 l1, w.t1_22 f1, w.t2_13 l2, w.t2_22 f2,
         w.t1_comparecimento comp1, w.t2_comparecimento comp2, b.biom_nh nb2, 100.0 * b.biom_nh / nullif(w.t2_comparecimento, 0) pb, {FX} faixa
  FROM '{P}/e2022_presidente_secao_wide.parquet' w JOIN '{P}/bweb_2022_t2_secao.parquet' b USING (uf, cd_municipio, nr_zona, nr_secao)
  WHERE w.uf <> 'ZZ' AND w.t2_comparecimento > 0 AND w.t1_comparecimento IS NOT NULL""")
print(con.execute("DESCRIBE s22").fetchall()[:3])
AGG = """count(*) n, sum(comp1)::BIGINT c1, sum(comp2)::BIGINT c2, sum(nb2)::BIGINT nb,
   round(100.0 * sum(nb2) / sum(comp2), 2) pct_nb,
   sum(l1)::BIGINT lt1, sum(f1)::BIGINT ft1, sum(l2)::BIGINT lt2, sum(f2)::BIGINT ft2,
   (sum(comp2) - sum(l1) - sum(f1))::BIGINT liq, (sum(l2) - sum(l1))::BIGINT gl, (sum(f2) - sum(f1))::BIGINT gf,
   (sum(comp2) - sum(l2) - sum(f2))::BIGINT bn, (sum(comp2) - sum(comp1))::BIGINT dcomp,
   round(1000.0 * (sum(l2) - sum(l1)) / nullif(sum(comp2) - sum(l1) - sum(f1), 0), 1) lula_mil,
   round(1000.0 * (sum(f2) - sum(f1)) / nullif(sum(comp2) - sum(l1) - sum(f1), 0), 1) flavio_mil,
   round(1000.0 * (sum(l2) - sum(l1) - sum(f2) + sum(f1)) / nullif(sum(comp2) - sum(l1) - sum(f1), 0), 1) saldo_mil,
   round(100.0 * sum(l2) / nullif(sum(l2 + f2), 0), 2) pl2, round(100.0 * sum(l1) / nullif(sum(l1 + f1), 0), 2) pl1,
   round(100.0 * (sum(l2) - sum(l1)) / nullif(sum(l2) - sum(l1) + sum(f2) - sum(f1), 0), 1) pct_dec"""
def grupos(tab, ano):
    out = {}
    for nome, where, key in [('Brasil', 'true', 'BR')] + \
            [(uf, f"uf = '{uf}'", uf) for (uf,) in con.execute(f"SELECT DISTINCT uf FROM {tab} ORDER BY uf").fetchall()]:
        rows = con.execute(f"SELECT faixa, {AGG} FROM {tab} WHERE {where} GROUP BY 1").fetchall()
        cols = [c[0] for c in con.description]
        out[key] = {'nome': nome, 'faixas': {r[0]: dict(zip(cols[1:], r[1:])) for r in rows}}
    return out
res = {'faixas': FAIXAS, 'min_secoes': MIN_SECOES, 'grupos2026': grupos('s', 2026), 'grupos2022': grupos('s22', 2022)}
# cidades 2026 (e 2022 das mesmas cidades quando houver)
cur = con.execute(f"""SELECT uf, cd_municipio, any_value(nm_municipio) nome, count(*) n FROM s GROUP BY 1,2 HAVING count(*) >= {MIN_SECOES} ORDER BY n DESC""")
cids = cur.fetchall()
res['cidades'] = []
for uf, cd, nome, n in cids:
    item = {'uf': uf, 'cd': cd, 'nome': nome, 'secoes': n}
    for tab, k in (('s', 'f2026'), ('s22', 'f2022')):
        rows = con.execute(f"SELECT faixa, {AGG} FROM {tab} WHERE uf = '{uf}' AND cd_municipio = {cd} GROUP BY 1").fetchall()
        cols = [c[0] for c in con.description]
        item[k] = {r[0]: dict(zip(cols[1:], r[1:])) for r in rows}
    res['cidades'].append(item)
json.dump(res, open(f'{OUT}/faixas.json', 'w'), ensure_ascii=False, separators=(',', ':'))
con.execute(f"COPY (SELECT faixa, {AGG} FROM s GROUP BY 1 ORDER BY 1) TO '{OUT}/faixas_brasil_2026.csv' (HEADER, DELIMITER ';')")
con.execute(f"COPY (SELECT uf, faixa, {AGG} FROM s GROUP BY 1, 2 ORDER BY 1, 2) TO '{OUT}/faixas_uf_2026.csv' (HEADER, DELIMITER ';')")
print(len(cids), 'cidades;', os.path.getsize(f'{OUT}/faixas.json') // 1024, 'KB')
pd = lambda q: print(con.execute(q).fetchdf().to_string(index=False))
print('\n=== Brasil 2026 por faixa'); pd(f"SELECT faixa, {AGG} FROM s GROUP BY 1 ORDER BY list_position({FAIXAS}, faixa)")
print('\n=== Brasil 2022 por faixa'); pd(f"SELECT faixa, {AGG} FROM s22 GROUP BY 1 ORDER BY list_position({FAIXAS}, faixa)")
