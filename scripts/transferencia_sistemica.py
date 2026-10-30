"""Análise sistêmica da transferência de votos entre turnos: 2006, 2010, 2014, 2018, 2022 e 2026.

Pergunta: é anormal um candidato vencer a transferência (ganho no 2º turno maior que o do adversário) em quase todos os
municípios, inclusive em estados que o adversário venceu? O relatório de anomalias por cidade não responde isso, porque
o modelo dele é treinado nos próprios dados de 2026 e absorve qualquer movimento que aconteça no país inteiro.

Parte A (histórico, por município): para cada 2º turno presidencial, D = votos em disputa (outros + brancos/nulos +
  abstenções do 1º turno), saldo = (ganho do PT − ganho do adversário) / D. Mede-se: % de municípios vencidos por cada
  lado, UFs com 100%, dispersão entre municípios (total e dentro da UF) e se o % de municípios vencidos é o previsto por
  um modelo de "maré uniforme" (normal com média e desvio da UF).
Parte B (inferência ecológica, por seção, 2022 e 2026): regressão de Goodman com efeito fixo de município, nas
  proporções do eleitorado da seção: para onde foram, no 2º turno, os eleitores de cada candidato do 1º turno, dos
  brancos/nulos e das abstenções. Erros-padrão agrupados por município.

Fontes: TSE (votacao_candidato_munzona e detalhe_votacao_munzona 2006-2018; arquivos por seção de 2022 e 2026).
Saída: dados/historicos/sistemica.json e site/dados/sistemica.json
"""
import os, json
import numpy as np, pandas as pd, duckdb
from scipy import stats

R = os.path.join(os.path.dirname(__file__), '..')
HD = f'{R}/dados/historicos'
P = f'{R}/dados/parquet'
con = duckdb.connect()

# PT × adversário em cada 2º turno; vencedor do 2º turno
PARES = {2006: (13, 45, 'Lula', 'Alckmin', 'Lula'), 2010: (13, 45, 'Dilma', 'Serra', 'Dilma'), 2014: (13, 45, 'Dilma', 'Aécio', 'Dilma'),
         2018: (13, 17, 'Haddad', 'Bolsonaro', 'Bolsonaro'), 2022: (13, 22, 'Lula', 'Bolsonaro', 'Lula'), 2026: (13, 22, 'Lula', 'Flávio', 'Lula')}


def municipios(ano):
    a, b = PARES[ano][:2]
    if ano <= 2018:
        v = f"read_csv('{HD}/pres_votacao_candidato_{ano}.csv', delim=';', quote='\"', header=true, all_varchar=true)"
        dt = f"read_csv('{HD}/pres_detalhe_votacao_{ano}.csv', delim=';', quote='\"', header=true, all_varchar=true)"
        return con.execute(f"""
        WITH v AS (SELECT SG_UF uf, CD_MUNICIPIO::INT cd, NR_TURNO::INT t, NR_CANDIDATO::INT n, sum(QT_VOTOS_NOMINAIS::BIGINT) votos FROM {v} GROUP BY ALL),
             d AS (SELECT SG_UF uf, CD_MUNICIPIO::INT cd, NR_TURNO::INT t, sum(QT_APTOS::BIGINT) aptos, sum(QT_COMPARECIMENTO::BIGINT) comp,
                          sum(QT_ABSTENCOES::BIGINT) abst FROM {dt} GROUP BY ALL)
        SELECT uf, cd,
          sum(votos) FILTER (v.t = 1 AND n = {a}) a1, sum(votos) FILTER (v.t = 1 AND n = {b}) b1,
          sum(votos) FILTER (v.t = 2 AND n = {a}) a2, sum(votos) FILTER (v.t = 2 AND n = {b}) b2,
          any_value(d1.comp) comp1, any_value(d1.abst) abst1, any_value(d2.comp) comp2, any_value(d2.abst) abst2
        FROM v JOIN d d1 USING (uf, cd) JOIN d d2 USING (uf, cd)
        WHERE d1.t = 1 AND d2.t = 2 AND uf NOT IN ('ZZ', 'VT') GROUP BY ALL""").df()
    if ano == 2022:
        return con.execute(f"""SELECT uf, cd_municipio cd, sum(t1_13) a1, sum(t1_22) b1, sum(t2_13) a2, sum(t2_22) b2,
                                      sum(t1_comparecimento) comp1, sum(t1_aptos - t1_comparecimento) abst1, sum(t2_comparecimento) comp2, sum(t2_aptos - t2_comparecimento) abst2
                               FROM '{P}/e2022_presidente_secao_wide.parquet' WHERE uf <> 'ZZ' GROUP BY ALL""").df()
    c = pd.DataFrame(json.load(open(f'{R}/site/dados/cidades.json')))
    c = c[c.uf != 'ZZ']
    return pd.DataFrame({'uf': c.uf, 'cd': c.cd, 'a1': c.lv1, 'b1': c.fv1, 'a2': c.lv1 + c.gl, 'b2': c.fv1 + c.gf,
                         'comp1': c.comp2 - c.dcomp, 'abst1': c.abst1, 'comp2': c.comp2, 'abst2': c.abst2})


hist, por_uf = {}, {}
mun = {}
for ano, (a, b, na, nb, venc) in PARES.items():
    d = municipios(ano).dropna()
    d = d[(d.a1 + d.b1) > 0]
    d['D'] = d.comp1 - d.a1 - d.b1 + d.abst1
    d['ga'], d['gb'] = d.a2 - d.a1, d.b2 - d.b1
    d['s'] = (d.ga - d.gb) / d.D
    d = d[d.D > 0]
    mun[ano] = d.set_index(['uf', 'cd']).s
    tot = d[['a1', 'b1', 'a2', 'b2', 'ga', 'gb', 'D', 'comp1', 'abst1', 'comp2', 'abst2']].sum()
    lado = 1 if tot.ga > tot.gb else -1        # quem venceu a transferência no país
    vencT = na if lado == 1 else nb
    d['venceu'] = np.sign(d.s) == lado
    # dispersão dentro da UF (desvio da média da UF), ponderada igualmente por município
    d['dev'] = d.s - d.groupby('uf').s.transform('mean')
    g = d.groupby('uf').agg(n=('s', 'size'), m=('s', 'mean'), sd=('s', 'std'), obs=('venceu', 'mean'),
                            a2=('a2', 'sum'), b2=('b2', 'sum'))
    g['normal'] = stats.norm.cdf(lado * g.m / g.sd)
    g['venc2t'] = np.where(g.a2 > g.b2, na, nb)
    cem = g[(g.obs == 1) & (g.n > 1)]
    hist[ano] = {
        'pt': na, 'adv': nb, 'vencedor_2t': venc, 'vencedor_transferencia': vencT,
        'pt1': float(tot.a1 / (tot.comp1)), 'adv1': float(tot.b1 / tot.comp1),
        'pt2_validos': float(tot.a2 / (tot.a2 + tot.b2)),
        'ganho_pt': int(tot.ga), 'ganho_adv': int(tot.gb), 'D': int(tot.D),
        'saldo_nacional_D': float((tot.ga - tot.gb) / tot.D),
        'decididos_pt': float(tot.ga / (tot.ga + tot.gb)) if tot.ga > 0 and tot.gb > 0 else None,
        'adv_perdeu': bool(tot.gb < 0), 'pt_perdeu': bool(tot.ga < 0),
        'n_mun': int(len(d)), 'pct_mun_vencedor_transf': float(d.venceu.mean()), 'pct_mun_pt': float((d.s > 0).mean()),
        'media_s': float(d.s.mean()), 'dp_s': float(d.s.std()), 'dp_dentro_uf': float(d.dev.std()),
        'ufs_100': cem.index.tolist(), 'ufs_100_venc2t_outro': [u for u in cem.index if cem.loc[u, 'venc2t'] != vencT],
        'erro_medio_modelo_normal': float(np.nanmean(np.abs(g.obs - g.normal)[g.n >= 10])),
        'curtose': float(stats.kurtosis(d.dev)), 'assimetria': float(stats.skew(d.dev)),
    }
    por_uf[ano] = g.reset_index().assign(ano=ano).round(4).to_dict('records')
    print(ano, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in hist[ano].items()})

# correlação entre eleições (mesmo município: códigos TSE estáveis)
anos = list(PARES)
corr = {}
for i in range(len(anos) - 1):
    j = pd.concat([mun[anos[i]], mun[anos[i + 1]]], axis=1, join='inner').dropna()
    corr[f'{anos[i]}-{anos[i + 1]}'] = {'n': len(j), 'pearson': float(j.corr().iloc[0, 1])}
print(corr)

# ---------- Parte B: inferência ecológica por seção (Goodman com efeito fixo de município)
def goodman(df, fontes, alvos, peso='aptos'):
    """Matriz de transição por regressão de Goodman com limites: y_k/aptos = Σ_j β_jk · x_j/aptos, 0 ≤ β ≤ 1.
    As fontes somam o eleitorado da seção, então não há intercepto. Estimada dentro de cada UF (reduz o viés de agregação
    de misturar regiões) e combinada pelo peso de cada fonte na UF. Erro-padrão: bootstrap de municípios (50 réplicas)."""
    from scipy.optimize import lsq_linear
    def ajusta(d):
        sw = np.sqrt(d[peso].to_numpy(float))
        X = d[fontes].div(d[peso], axis=0).to_numpy() * sw[:, None]
        return np.column_stack([lsq_linear(X, (d[k] / d[peso]).to_numpy() * sw, bounds=(0, 1)).x for k in alvos])
    def nacional(d):
        acc, peso_f = np.zeros((len(fontes), len(alvos))), np.zeros(len(fontes))
        for uf, g in d.groupby('uf'):
            if len(g) < 200:
                continue
            b = ajusta(g); v = g[fontes].sum().to_numpy(float)
            acc += b * v[:, None]; peso_f += v
        return acc / peso_f[:, None]
    B = nacional(df)
    rng = np.random.default_rng(1)
    chaves = df.cd_key.unique()
    grupos = df.groupby('cd_key').indices
    boot = []
    for _ in range(50):
        amostra = rng.choice(chaves, len(chaves))
        idx = np.concatenate([grupos[c] for c in amostra])
        boot.append(nacional(df.iloc[idx]))
    SE = np.std(boot, axis=0)
    return {k: {f: [round(float(B[i, j]), 3), round(float(SE[i, j]), 3)] for i, f in enumerate(fontes)} for j, k in enumerate(alvos)}


s26 = con.execute(f"""
WITH v1 AS (SELECT uf, cd_municipio, nr_zona, nr_secao,
              sum(votos) FILTER (nr_votavel = 13) l1, sum(votos) FILTER (nr_votavel = 22) f1,
              sum(votos) FILTER (nr_votavel = 70) cury, sum(votos) FILTER (nr_votavel = 14) renan, sum(votos) FILTER (nr_votavel = 55) caiado,
              sum(votos) FILTER (nr_votavel = 30) zema, sum(votos) FILTER (nr_votavel NOT IN (13, 22, 70, 14, 55, 30, 95, 96, 28)) peq
            FROM '{P}/t1_votos_secao.parquet' GROUP BY ALL),
     v2 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, sum(votos) FILTER (nr_votavel = 13) l2, sum(votos) FILTER (nr_votavel = 22) f2
            FROM '{P}/t2_votos_secao.parquet' GROUP BY ALL),
     d1 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, aptos, abstencoes abst1, comparecimento c1 FROM '{P}/t1_detalhe_secao.parquet'),
     d2 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, abstencoes abst2, comparecimento c2 FROM '{P}/t2_detalhe_secao.parquet')
SELECT * FROM v1 JOIN v2 USING (uf, cd_municipio, nr_zona, nr_secao) JOIN d1 USING (uf, cd_municipio, nr_zona, nr_secao) JOIN d2 USING (uf, cd_municipio, nr_zona, nr_secao)
WHERE uf <> 'ZZ' AND aptos > 0 AND c1 > 0 AND c2 > 0""").df().fillna(0)
s26['bn1'] = s26.c1 - s26[['l1', 'f1', 'cury', 'renan', 'caiado', 'zema', 'peq']].sum(axis=1)
s26['bn2'] = s26.c2 - s26.l2 - s26.f2
s26['cd_key'] = s26.uf + s26.cd_municipio.astype(str)
F26 = ['l1', 'f1', 'cury', 'renan', 'caiado', 'zema', 'peq', 'bn1', 'abst1']
ei26 = goodman(s26, F26, ['l2', 'f2', 'bn2', 'abst2'])

s22 = con.execute(f"""SELECT uf, cd_municipio, t1_aptos aptos, t1_13 l1, t1_22 b1, t1_12 ciro, t1_15 tebet, t1_outros outros, t1_brancos + t1_nulos bn1,
                             t1_aptos - t1_comparecimento abst1, t2_13 l2, t2_22 b2, t2_brancos + t2_nulos bn2, t2_aptos - t2_comparecimento abst2
                      FROM '{P}/e2022_presidente_secao_wide.parquet' WHERE uf <> 'ZZ' AND t1_aptos > 0 AND t1_comparecimento > 0 AND t2_comparecimento > 0""").df()
s22['cd_key'] = s22.uf + s22.cd_municipio.astype(str)
ei22 = goodman(s22, ['l1', 'b1', 'ciro', 'tebet', 'outros', 'bn1', 'abst1'], ['l2', 'b2', 'bn2', 'abst2'])
for nm, ei in (('2026', ei26), ('2022', ei22)):
    print(nm)
    print(pd.DataFrame({k: {f: v[0] for f, v in d.items()} for k, d in ei.items()}).assign(soma=lambda x: x.sum(axis=1)).to_string())

# votos nacionais de cada fonte (para converter as taxas em votos)
tot26 = s26[F26 + ['l2', 'f2']].sum().astype(int).to_dict()
tot22 = s22[['l1', 'b1', 'ciro', 'tebet', 'outros', 'bn1', 'abst1', 'l2', 'b2']].sum().astype(int).to_dict()

out = {'historico': hist, 'por_uf': por_uf, 'correlacao': corr, 'ei': {'2026': ei26, '2022': ei22}, 'totais_secoes': {'2026': tot26, '2022': tot22},
       'n_secoes': {'2026': int(len(s26)), '2022': int(len(s22))},
       'candidatos_2026': {'cury': 'Augusto Cury (Avante, 70)', 'renan': 'Renan Santos (Missão, 14)', 'caiado': 'Ronaldo Caiado (PSD, 55)', 'zema': 'Romeu Zema (Novo, 30)', 'peq': 'demais candidatos'}}
json.dump(out, open(f'{HD}/sistemica.json', 'w'), ensure_ascii=False, indent=1, default=float)
json.dump(out, open(f'{R}/site/dados/sistemica.json', 'w'), ensure_ascii=False, separators=(',', ':'), default=float)
