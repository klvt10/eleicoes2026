"""Gera estudo/dados.json com as agregações do estudo T1 (+ T2 parcial)."""
import duckdb, json, os, numpy as np
from scipy.optimize import nnls
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
con = duckdb.connect()
P = 'dados/parquet'
REG = {'N':'AC AM AP PA RO RR TO','NE':'AL BA CE MA PB PE PI RN SE','CO':'DF GO MS MT','SE':'ES MG RJ SP','S':'PR RS SC','EX':'ZZ'}
reg = {u:r for r,us in REG.items() for u in us.split()}
con.create_function('regiao', lambda u: reg.get(u,'?'), ['VARCHAR'], 'VARCHAR')
con.execute(f"""CREATE TABLE s AS
  SELECT d.*, regiao(d.uf) regiao,
    COALESCE(sum(v.votos) FILTER (nr_votavel=13),0) c13, COALESCE(sum(v.votos) FILTER (nr_votavel=22),0) c22,
    COALESCE(sum(v.votos) FILTER (nr_votavel=70),0) c70, COALESCE(sum(v.votos) FILTER (nr_votavel=14),0) c14,
    COALESCE(sum(v.votos) FILTER (nr_votavel=55),0) c55,
    COALESCE(sum(v.votos) FILTER (nr_votavel NOT IN (13,22,70,14,55,95,96)),0) cout,
    COALESCE(sum(v.votos) FILTER (nr_votavel<95),0) val
  FROM '{P}/t1_detalhe_secao.parquet' d LEFT JOIN '{P}/t1_votos_secao.parquet' v USING (uf,cd_municipio,nr_zona,nr_secao)
  GROUP BY ALL""")
out = {}
def rows(q): 
    r = con.execute(q); cols = [c[0] for c in r.description]
    return [dict(zip(cols, [float(x) if isinstance(x,(int,float)) and not isinstance(x,bool) else x for x in t])) for t in r.fetchall()]
agg = """sum(aptos) aptos, sum(comparecimento) comp, sum(val) val, sum(brancos) b, sum(nulos) n,
  sum(c13) c13, sum(c22) c22, sum(c70) c70, sum(c14) c14, sum(c55) c55, sum(cout) cout"""
out['nacional'] = rows(f"SELECT {agg}, count(*) secoes, count(DISTINCT (uf,cd_municipio)) municipios FROM s")[0]
out['uf'] = rows(f"SELECT uf, regiao, {agg} FROM s GROUP BY ALL ORDER BY aptos DESC")
out['regiao'] = rows(f"SELECT regiao, {agg} FROM s GROUP BY ALL ORDER BY aptos DESC")
# distribuição por seção da % do 13 nos votos 13+22 (bins de 2pp), ponderada por nº de seções
out['hist_secao'] = rows("""SELECT floor(100*c13/(c13+c22)/2)*2 bin, count(*) n FROM s WHERE c13+c22>=30 GROUP BY 1 ORDER BY 1""")
out['hist_abst'] = rows("""SELECT floor(100*(aptos-comparecimento)/aptos) bin, count(*) n FROM s WHERE aptos>=50 GROUP BY 1 ORDER BY 1""")
# municípios: maiores votações relativas de cada um dos 5 principais (mín. 5 mil aptos)
mun = f"SELECT uf, nm_municipio, {agg} FROM s WHERE uf<>'ZZ' GROUP BY ALL HAVING sum(aptos)>=5000"
out['top_mun'] = {c: rows(f"SELECT uf, nm_municipio, aptos, {c}/val pct FROM ({mun}) ORDER BY pct DESC LIMIT 10") for c in ['c13','c22','c70','c14','c55']}
out['capitais_maiores'] = rows(f"SELECT uf, nm_municipio, aptos, c13/val p13, c22/val p22, (c70+c14+c55)/val p3 FROM ({mun}) ORDER BY aptos DESC LIMIT 15")
# abstenção x voto (decis de abstenção da seção)
out['abst_decil'] = rows("""SELECT dec, avg(abst) abst, sum(c13)/sum(c13+c22) p13 FROM (
  SELECT *, (aptos-comparecimento)/aptos abst, ntile(10) OVER (ORDER BY (aptos-comparecimento)/aptos) dec FROM s WHERE aptos>=50) GROUP BY 1 ORDER BY 1""")
# modelo de urna: bruto vs. dentro do mesmo município (efeito fixo)
out['urna'] = rows("""WITH x AS (SELECT *, c13/(c13+c22) p FROM s WHERE c13+c22>=30 AND modelo_urna LIKE 'UE%'),
  m AS (SELECT uf, cd_municipio, avg(p) pm FROM x GROUP BY ALL)
  SELECT modelo_urna, count(*) secoes, sum(c13)/sum(c13+c22) p13_bruto, avg(p - pm) desvio_mesmo_mun
  FROM x JOIN m USING (uf, cd_municipio) GROUP BY 1 ORDER BY 1""")
# ---- 2º turno parcial
con.execute(f"""CREATE TABLE j AS SELECT s.*, t.aptos a2, t.comparecimento comp2, v.v13, v.v22, t.brancos+t.nulos bn2
  FROM s JOIN '{P}/t2_detalhe_secao.parquet' t USING (uf, cd_municipio, nr_zona, nr_secao)
  JOIN (SELECT uf, cd_municipio, nr_zona, nr_secao, COALESCE(sum(votos) FILTER (nr_votavel=13),0) v13,
               COALESCE(sum(votos) FILTER (nr_votavel=22),0) v22
        FROM '{P}/t2_votos_secao.parquet' GROUP BY ALL) v USING (uf, cd_municipio, nr_zona, nr_secao)""")
out['t2_uf'] = rows("""SELECT uf, count(*) secoes, sum(aptos) aptos, sum(c13)/sum(c13+c22) t1_p13, sum(v13)/sum(v13+v22) t2_p13,
  1-sum(comparecimento)/sum(aptos) t1_abst, 1-sum(comp2)/sum(a2) t2_abst FROM j GROUP BY 1 ORDER BY aptos DESC""")
out['t2_scatter'] = rows("""SELECT round(100*c13/(c13+c22),1) x, round(100*v13/(v13+v22),1) y, uf FROM j
  WHERE c13+c22>=30 AND v13+v22>=30 USING SAMPLE 3000 ROWS (reservoir, 7)""")
# transferência: NNLS seção a seção, origem T1 -> destino T2 (13, 22, branco/nulo, abstenção)
X = con.execute("SELECT c13, c22, c70, c14, c55, cout, brancos+nulos, aptos-comparecimento FROM j").fetchnumpy()
X = np.column_stack(list(X.values())).astype(float)
Y = con.execute("SELECT v13, v22, bn2, a2-comp2 FROM j").fetchnumpy(); Y = np.column_stack(list(Y.values())).astype(float)
orig = ['Lula (13)','Flávio (22)','Cury (70)','Renan (14)','Caiado (55)','Outros','Branco/Nulo','Abstenção']
dest = ['Lula (13)','Flávio (22)','Branco/Nulo','Abstenção']
B = np.column_stack([nnls(X, Y[:, k])[0] for k in range(4)])
B = B / B.sum(1, keepdims=True)  # normaliza: cada origem distribui 100%
out['transfer'] = {'origem': orig, 'destino': dest, 'matriz': B.round(4).tolist(), 'secoes': int(len(X)),
                   'ufs': sorted({r['uf'] for r in out['t2_uf']})}
json.dump(out, open('estudo/dados.json','w'), ensure_ascii=False, default=float)
print(json.dumps(out['nacional']), '\n', json.dumps(out['t2_uf']), '\n', json.dumps(out['urna']), '\n', json.dumps(out['abst_decil']))
for o,r in zip(orig,B): print(f'{o:14s}', ' '.join(f'{x:6.1%}' for x in r))

# ---------- exporta um arquivo por conjunto de dados (para o painel)
import datetime
E = 'estudo/ds'; os.makedirs(E, exist_ok=True)
def w(name, rows): json.dump(rows, open(f'{E}/{name}.json', 'w'), ensure_ascii=False, default=float)
CURTO = {13:'Lula', 22:'Flávio Bolsonaro', 70:'Augusto Cury', 14:'Renan Santos', 55:'Ronaldo Caiado', 30:'Romeu Zema',
         80:'Samara Martins', 16:'Hertz Dias', 27:'Clariana Barão', 21:'Edmilson Costa', 35:'Wilson Grassi', 29:'Rui Costa Pimenta', 28:'Leonardo Araújo'}
cand = rows(f"SELECT nr_votavel numero, sum(votos) votos FROM '{P}/t1_votos_secao.parquet' WHERE nr_votavel<95 GROUP BY 1 ORDER BY 2 DESC")
tv = sum(c['votos'] for c in cand)
w('t1_candidatos', [{'numero': int(c['numero']), 'candidato': CURTO.get(int(c['numero']), str(c['numero'])),
                     'votos': int(c['votos']), 'pct_validos': c['votos']/tv} for c in cand])
n = out['nacional']
w('t1_nacional', [{'aptos': int(n['aptos']), 'comparecimento': int(n['comp']), 'abstencao_pct': 1-n['comp']/n['aptos'],
   'validos': int(n['val']), 'brancos': int(n['b']), 'nulos': int(n['n']), 'secoes': int(n['secoes']),
   'municipios': int(n['municipios']), 'dif_22_13': int(n['c22']-n['c13'])}])
w('t1_uf', [{'uf': u['uf'], 'regiao': u['regiao'], 'aptos': int(u['aptos']), 'abstencao_pct': 1-u['comp']/u['aptos'],
   'pct_13': u['c13']/u['val'], 'pct_22': u['c22']/u['val'], 'pct_terceira_via': (u['c70']+u['c14']+u['c55'])/u['val'],
   'pct_13_no_par': u['c13']/(u['c13']+u['c22'])} for u in out['uf']])
w('t1_hist_secao', [{'faixa_pct_13': int(h['bin']), 'secoes': int(h['n'])} for h in out['hist_secao']])
w('t1_abstencao_decil', [{'decil': int(d['dec']), 'abstencao_media': d['abst'], 'pct_13_no_par': d['p13']} for d in out['abst_decil']])
w('t1_modelo_urna', [{'modelo': u['modelo_urna'], 'secoes': int(u['secoes']), 'pct_13_bruto': u['p13_bruto'],
   'desvio_mesmo_municipio_pp': 100*u['desvio_mesmo_mun']} for u in out['urna']])
red = []
for c, num in [('c70',70),('c14',14),('c55',55),('c13',13),('c22',22)]:
    for k, r in enumerate(out['top_mun'][c], 1):
        red.append({'candidato': CURTO[num], 'posicao': k, 'municipio': f"{r['nm_municipio'].title()} ({r['uf']})",
                    'chave': f"{num}-{k}", 'aptos': int(r['aptos']), 'pct_validos': r['pct']})
w('t1_redutos', red)
w('t2_uf_parcial', [{'uf': u['uf'], 'secoes': int(u['secoes']), 'aptos': int(u['aptos']), 'pct_13_t1': u['t1_p13'],
   'pct_13_t2': u['t2_p13'], 'swing_pp': 100*(u['t2_p13']-u['t1_p13']), 'abst_t1': u['t1_abst'], 'abst_t2': u['t2_abst']} for u in out['t2_uf']])
w('t2_dispersao', [{'pct_13_t1': p['x'], 'pct_13_t2': p['y'], 'uf': p['uf']} for p in out['t2_scatter']])
T = out['transfer']
w('t2_transferencia', [{'origem': o, 'destino': d, 'pct': T['matriz'][i][j], 'chave': f'{i}-{j}'}
   for i, o in enumerate(T['origem']) for j, d in enumerate(T['destino'])])
tot = con.execute("SELECT count(*), count(DISTINCT uf) FROM j").fetchone()
w('t2_progresso', [{'secoes_coletadas': int(tot[0]), 'secoes_total': 499248, 'ufs': int(tot[1]),
   'secoes_transferencia': T['secoes'], 'atualizado': 'arquivo oficial TSE, 26/10'}])
print('exportado:', sorted(os.listdir(E)))

# 2º turno oficial: totais nacionais e por UF
c2 = rows(f"SELECT nr_votavel numero, sum(votos) votos FROM '{P}/t2_votos_secao.parquet' WHERE nr_votavel<95 GROUP BY 1 ORDER BY 2 DESC")
tv2 = sum(c['votos'] for c in c2)
w('t2_candidatos', [{'numero': int(c['numero']), 'candidato': CURTO[int(c['numero'])], 'votos': int(c['votos']), 'pct_validos': c['votos']/tv2} for c in c2])
n2 = rows(f"SELECT sum(aptos) aptos, sum(comparecimento) comp, sum(brancos) b, sum(nulos) n FROM '{P}/t2_detalhe_secao.parquet'")[0]
w('t2_nacional', [{'aptos': int(n2['aptos']), 'comparecimento': int(n2['comp']), 'abstencao_pct': 1-n2['comp']/n2['aptos'],
   'brancos': int(n2['b']), 'nulos': int(n2['n']), 'dif_13_22': int(c2[0]['votos']-c2[1]['votos']) if int(c2[0]['numero'])==13 else int(c2[1]['votos']-c2[0]['votos'])}])
print('t2 oficial exportado')
