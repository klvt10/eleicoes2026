"""Votos por urna: quantas urnas cada candidato a presidente teve 0, 1, 2… votos, e quanto o outro teve nessas urnas.
Cada linha do bweb por seção é uma urna (seções agregadas já vêm somadas na seção principal).
Para cada turno (1T 2026, 2T 2026 e 2T 2022 como referência), candidato (13 / 22) e UF, grava o histograma
de urnas por número de votos do candidato, com as somas do outro candidato, comparecimento, aptos, brancos+nulos
e os votos dos dois no outro turno nas mesmas urnas. Grava também a lista das urnas em que algum dos dois teve
até LIM_LISTA votos. Saída: site/dados/votos_por_urna/{meta,hist_*,urnas_*}.json"""
import os, json, datetime, duckdb
R = os.path.join(os.path.dirname(__file__), '..')
P, OUT = f'{R}/dados/parquet', f'{R}/site/dados/votos_por_urna'
os.makedirs(OUT, exist_ok=True)
LIM_LISTA = 10
con = duckdb.connect()
# base por turno: uma linha por urna, com os votos do mesmo par no outro turno (mesma seção)
con.execute(f"""CREATE TABLE t2026_t2 AS
  SELECT b.uf, b.cd_municipio, b.nm_municipio, b.nr_zona, b.nr_secao, b.nr_local, b.agregadas, b.aptos, b.comparecimento comp,
         b.v13::INT v13, b.v22::INT v22, (b.brancos + b.nulos)::INT bn, b.biom_nh,
         a.v13::INT c13, a.v22::INT c22, a.comparecimento ccomp
  FROM '{P}/bweb_2026_t2_secao.parquet' b LEFT JOIN '{P}/bweb_2026_t1_secao.parquet' a USING (uf, cd_municipio, nr_zona, nr_secao)""")
con.execute(f"""CREATE TABLE t2026_t1 AS
  SELECT a.uf, a.cd_municipio, a.nm_municipio, a.nr_zona, a.nr_secao, a.nr_local, a.agregadas, a.aptos, a.comparecimento comp,
         a.v13::INT v13, a.v22::INT v22, (a.brancos + a.nulos)::INT bn, a.biom_nh,
         b.v13::INT c13, b.v22::INT c22, b.comparecimento ccomp
  FROM '{P}/bweb_2026_t1_secao.parquet' a LEFT JOIN '{P}/bweb_2026_t2_secao.parquet' b USING (uf, cd_municipio, nr_zona, nr_secao)""")
con.execute(f"""CREATE TABLE t2022_t2 AS
  SELECT b.uf, b.cd_municipio, b.nm_municipio, b.nr_zona, b.nr_secao, b.nr_local, b.agregadas, b.aptos, b.comparecimento comp,
         b.v13::INT v13, b.v22::INT v22, (b.brancos + b.nulos)::INT bn, b.biom_nh,
         w.t1_13 c13, w.t1_22 c22, w.t1_comparecimento ccomp
  FROM '{P}/bweb_2022_t2_secao.parquet' b LEFT JOIN '{P}/e2022_presidente_secao_wide.parquet' w USING (uf, cd_municipio, nr_zona, nr_secao)
  WHERE b.tipo_urna <> 'ANULADA'""")
TURNOS = {
  '2026_t2': {'nome': '2º turno de 2026', 'curto': '2T 2026', 'data': '25/10/2026', 'cands': {'13': 'Lula', '22': 'Flávio'}, 'cruz': '1º turno de 2026', 'cruz_curto': '1T 2026'},
  '2026_t1': {'nome': '1º turno de 2026', 'curto': '1T 2026', 'data': '04/10/2026', 'cands': {'13': 'Lula', '22': 'Flávio'}, 'cruz': '2º turno de 2026', 'cruz_curto': '2T 2026'},
  '2022_t2': {'nome': '2º turno de 2022', 'curto': '2T 2022', 'data': '30/10/2022', 'cands': {'13': 'Lula', '22': 'Bolsonaro'}, 'cruz': '1º turno de 2022', 'cruz_curto': '1T 2022'},
}
COLS_HIST = ['k', 'n', 'outro', 'comp', 'aptos', 'bn', 'biom', 'eu_cruz', 'outro_cruz', 'comp_cruz', 'n_cruz']
COLS_URNA = ['uf', 'mun', 'zona', 'secao', 'local', 'agreg', 'aptos', 'comp', 'v13', 'v22', 'bn', 'biom', 'c13', 'c22', 'ccomp']
meta = {'gerado': datetime.datetime.now().isoformat(timespec='minutes'), 'lim_lista': LIM_LISTA, 'cols_hist': COLS_HIST, 'cols_urna': COLS_URNA, 'turnos': {}}
for t, info in TURNOS.items():
    tab = f't{t}'
    tot = con.execute(f"SELECT count(*), sum(comp), sum(v13), sum(v22), sum(bn), count(c13) FROM {tab}").fetchone()
    meta['turnos'][t] = {**info, 'urnas': tot[0], 'comp': tot[1], 'v13': tot[2], 'v22': tot[3], 'bn': tot[4], 'urnas_com_cruz': tot[5]}
    hist = {}
    for cand, outro in (('13', '22'), ('22', '13')):
        rows = con.execute(f"""SELECT uf, v{cand} k, count(*) n, sum(v{outro}) outro, sum(comp) comp, sum(aptos) aptos, sum(bn) bn, sum(biom_nh) biom,
              sum(c{cand}) eu_cruz, sum(c{outro}) outro_cruz, sum(ccomp) comp_cruz, count(c{cand}) n_cruz
              FROM {tab} GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
        h = {}
        for r in rows: h.setdefault(r[0], []).append([int(x) if x is not None else 0 for x in r[1:]])
        hist[cand] = h
    json.dump(hist, open(f'{OUT}/hist_{t}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    urnas = con.execute(f"""SELECT uf, nm_municipio, nr_zona, nr_secao, nr_local, CASE WHEN agregadas = '#NULO#' THEN NULL ELSE agregadas END,
          aptos, comp, v13, v22, bn, biom_nh, c13, c22, ccomp FROM {tab} WHERE least(v13, v22) <= {LIM_LISTA} ORDER BY uf, nm_municipio, nr_zona, nr_secao""").fetchall()
    json.dump([list(r) for r in urnas], open(f'{OUT}/urnas_{t}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print(t, tot, 'urnas na lista:', len(urnas), 'hist KB:', os.path.getsize(f'{OUT}/hist_{t}.json') // 1024, 'urnas KB:', os.path.getsize(f'{OUT}/urnas_{t}.json') // 1024)
json.dump(meta, open(f'{OUT}/meta.json', 'w'), ensure_ascii=False, indent=1)
pd = lambda q: print(con.execute(q).fetchdf().to_string(index=False))
for t in TURNOS:
    print(f'\n=== {t}: urnas por faixa de votos de cada candidato (Brasil)')
    pd(f"""SELECT lim, count(*) FILTER (v13 <= lim) urnas_lula_ate, sum(v22) FILTER (v13 <= lim) flavio_nelas, sum(comp) FILTER (v13 <= lim) comp_nelas,
           count(*) FILTER (v22 <= lim) urnas_flavio_ate, sum(v13) FILTER (v22 <= lim) lula_nelas, sum(comp) FILTER (v22 <= lim) comp_nelas2
           FROM t{t}, (VALUES (0), (1), (2), (5), (10), (20), (50)) l(lim) GROUP BY 1 ORDER BY 1""")
