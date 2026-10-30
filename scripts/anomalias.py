"""Anomalias estatísticas de transferência de votos entre o 1º e o 2º turno de 2026, por cidade.

Ideia: prever, para cada cidade, como os votos em disputa (outros + brancos/nulos + abstenções do 1º turno)
se dividiram no 2º turno, usando TUDO o que se sabia antes do 2º turno:
  - 1º turno 2026 (Lula, Flávio, outros, brancos/nulos, abstenção, tamanho do eleitorado)
  - 2022: 1º turno (Lula, Bolsonaro, Ciro, Tebet, outros, brancos/nulos, abstenção), 2º turno e a transferência de 2022
  - 2024: voto em vereador por bloco e índice municipal, bloco/partido e votação do prefeito eleito
  - estado (efeito fixo: governador no 2º turno, campanha estadual etc.)
e medir o quanto o resultado real se afasta da previsão, em unidades estatísticas.

Desfecho (3 componentes, frações dos votos em disputa D):
  y_l = ganho de Lula / D,  y_f = ganho de Flávio / D,  y_b = brancos e nulos do 2º turno / D
  (o resto é abstenção do 2º turno; os 4 somam ~1).

Passos:
  1. Previsão fora da amostra (validação cruzada em 10 partes): cada cidade é prevista por um modelo que não a viu.
     Dois modelos: gradient boosting (não linear, com interações) e regressão linear ponderada com efeito fixo de UF.
  2. Resíduo e = y - ŷ. A variância do resíduo depende do tamanho: Var(e | D) = τ² + σ²/D
     (τ² = heterogeneidade real entre cidades, σ²/D = ruído de amostragem). Ajustado por faixas de D.
     z = e / sqrt(τ² + σ²/D): resíduo padronizado que já desconta o ruído de cidade pequena.
  3. As 3 componentes são correlacionadas: distância de Mahalanobis robusta (MCD, determinante mínimo de covariância)
     d² ~ χ²(3) sob normalidade; p-valor e q-valor de Benjamini-Hochberg (controle da taxa de falsas descobertas).
  4. Persistência: o mesmo modelo para a transferência de 2022 (só com dados até o 1º turno de 2022).
  5. Para as cidades mais anômalas: heterogeneidade entre seções (superdispersão em relação ao binomial, comparada com
     a de todas as cidades) e concentração (quanto do excesso vem de 10% das seções).

Saída: dados/anomalias/cidades.parquet e site/dados/anomalias.json
"""
import os, json
import numpy as np, pandas as pd, duckdb
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

R = os.path.join(os.path.dirname(__file__), '..')
P = f'{R}/dados/parquet'
H = f'{R}/dados/historico'
OUT = f'{R}/dados/anomalias'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()
SEED = 20261025

# ---------- base por cidade
cid = pd.DataFrame(json.load(open(f'{R}/site/dados/cidades.json')))
cid = cid[cid.uf != 'ZZ'].copy()
w22 = con.execute(f"""SELECT uf, cd_municipio cd, sum(t1_aptos) a1, sum(t1_comparecimento) c1, sum(t1_13) l1, sum(t1_22) b1, sum(t1_12) ciro1, sum(t1_15) tebet1,
                             sum(t1_outros) o1, sum(t1_brancos + t1_nulos) bn1, sum(t2_aptos) a2, sum(t2_comparecimento) c2, sum(t2_13) l2, sum(t2_22) b2,
                             sum(t2_brancos + t2_nulos) bn2
                      FROM '{P}/e2022_presidente_secao_wide.parquet' WHERE uf <> 'ZZ' GROUP BY ALL""").df()
w22 = w22.add_prefix('x22_').rename(columns={'x22_uf': 'uf', 'x22_cd': 'cd'})
d = cid.merge(w22, on=['uf', 'cd'], how='left')
d['cd'] = d.cd.astype(int)

# 2026
d['comp1'] = d.comp2 - d.dcomp
d['aptos1'] = d.comp1 + d.abst1
d['D'] = d.ov1 + d.bn1 + d.abst1                      # votos em disputa
d['y_l'] = d.gl / d.D
d['y_f'] = d.gf / d.D
d['y_b'] = d.bn / d.D
for k, col in (('l', 'lv1'), ('f', 'fv1'), ('o', 'ov1'), ('bn', 'bn1'), ('ab', 'abst1')):
    d[f'r26_{k}'] = d[col] / d.aptos1
d['log_aptos'] = np.log(d.aptos1)
d['ov_frac'] = d.ov1 / d.D                            # composição dos votos em disputa
d['bn_frac'] = d.bn1 / d.D

# 2022
a1 = d.x22_a1
for k in ('l1', 'b1', 'ciro1', 'tebet1', 'o1', 'bn1'):
    d[f'r22_{k}'] = d[f'x22_{k}'] / a1
d['r22_ab1'] = (a1 - d.x22_c1) / a1
d['D22'] = (d.x22_ciro1 + d.x22_tebet1 + d.x22_o1 + d.x22_bn1) + (a1 - d.x22_c1)
d['y22_l'] = (d.x22_l2 - d.x22_l1) / d.D22
d['y22_b'] = (d.x22_b2 - d.x22_b1) / d.D22
d['y22_n'] = d.x22_bn2 / d.D22
d['l22_2t'] = d.x22_l2 / (d.x22_l2 + d.x22_b2)

# 2024
blk = {r['partido']: r['bloco'] for r in json.load(open(f'{R}/site/dados/partidos.json'))}
d['pref_part'] = d.pref24_partido.fillna(d.pref24_1partido)
d['pref_bloco'] = d.pref_part.map(blk).fillna('sem')
for b in ('esquerda', 'centro', 'direita'):
    d[f'pref_{b}'] = (d.pref_bloco == b).astype(float)
d['pref_PT'] = (d.pref_part == 'PT').astype(float)
d['pref_PL'] = (d.pref_part == 'PL').astype(float)
d['pref_pct'] = pd.to_numeric(d.pref24_pct, errors='coerce')
for c in ('i24', 'esq24', 'cen24', 'dir24'):
    d[c] = pd.to_numeric(d[c], errors='coerce')
d['uf_cod'] = d.uf.astype('category').cat.codes

F26 = ['r26_l', 'r26_f', 'r26_o', 'r26_bn', 'r26_ab', 'log_aptos', 'ov_frac', 'bn_frac']
F22 = ['r22_l1', 'r22_b1', 'r22_ciro1', 'r22_tebet1', 'r22_o1', 'r22_bn1', 'r22_ab1', 'y22_l', 'y22_b', 'y22_n', 'l22_2t']
F24 = ['i24', 'esq24', 'dir24', 'pref_esquerda', 'pref_direita', 'pref_PT', 'pref_PL', 'pref_pct']
FEAT = F26 + F22 + F24 + ['uf_cod']
Y = ['y_l', 'y_f', 'y_b']

base = d[(d.D >= 50) & d.x22_a1.notna()].reset_index(drop=True)   # cidade com 2022 e um mínimo de votos em disputa
print('cidades no modelo:', len(base), 'de', len(d))


def oof(df, feats, ys, wcol):
    """Previsões fora da amostra (10 partes) de gradient boosting e de regressão linear ponderada com efeito fixo de UF."""
    kf = KFold(10, shuffle=True, random_state=SEED)
    X = df[feats].to_numpy(float)
    cat = [feats.index('uf_cod')]
    # linear: variáveis numéricas (faltantes = média) + dummies de UF
    num = [f for f in feats if f != 'uf_cod']
    XL = df[num].copy()
    XL = XL.fillna(XL.mean())
    XL = np.column_stack([np.ones(len(df)), XL.to_numpy(float), pd.get_dummies(df.uf, drop_first=True).to_numpy(float)])
    w = df[wcol].to_numpy(float)
    res = {}
    for y in ys:
        yv = df[y].to_numpy(float)
        pg, pl = np.zeros(len(df)), np.zeros(len(df))
        for tr, te in kf.split(X):
            m = HistGradientBoostingRegressor(max_iter=600, learning_rate=0.04, max_leaf_nodes=31, min_samples_leaf=25,
                                              l2_regularization=1.0, categorical_features=cat, random_state=SEED)
            m.fit(X[tr], yv[tr], sample_weight=w[tr])
            pg[te] = m.predict(X[te])
            sw = np.sqrt(w[tr])
            beta = np.linalg.lstsq(XL[tr] * sw[:, None], yv[tr] * sw, rcond=None)[0]
            pl[te] = XL[te] @ beta
        res[y] = (pg, pl)
    return res


def r2w(y, p, w):
    return 1 - np.sum(w * (y - p) ** 2) / np.sum(w * (y - np.average(y, weights=w)) ** 2)


def var_modelo(e, D, nb=40):
    """Var(e | D) = τ² + σ²/D, ajustado por mínimos quadrados nas médias de e² por faixa de D (robusto: média aparada)."""
    q = pd.qcut(D, nb, labels=False, duplicates='drop')
    g = pd.DataFrame({'e2': e ** 2, 'inv': 1 / D, 'q': q}).groupby('q')
    m = g.e2.apply(lambda s: stats.trim_mean(s, 0.1)).to_numpy()
    inv = g.inv.mean().to_numpy()
    A = np.column_stack([np.ones_like(inv), inv])
    tau2, sig2 = np.linalg.lstsq(A, m, rcond=None)[0]
    tau2, sig2 = max(tau2, 1e-8), max(sig2, 0.0)
    return tau2, sig2


def mcd(Z, h_frac=0.75, iters=50):
    """Covariância robusta por determinante mínimo (C-steps a partir de mediana/MAD), com fator de consistência."""
    n, p = Z.shape
    h = int(h_frac * n)
    mu = np.median(Z, axis=0)
    S = np.diag((stats.median_abs_deviation(Z, axis=0, scale='normal')) ** 2)
    for _ in range(iters):
        dd = np.einsum('ij,jk,ik->i', Z - mu, np.linalg.inv(S), Z - mu)
        idx = np.argsort(dd)[:h]
        mu2, S2 = Z[idx].mean(0), np.cov(Z[idx].T)
        if np.allclose(mu2, mu) and np.allclose(S2, S):
            break
        mu, S = mu2, S2
    dd = np.einsum('ij,jk,ik->i', Z - mu, np.linalg.inv(S), Z - mu)
    S = S * np.median(dd) / stats.chi2.ppf(0.5, p)     # consistência: mediana de d² = mediana de χ²(p)
    dd = np.einsum('ij,jk,ik->i', Z - mu, np.linalg.inv(S), Z - mu)
    return mu, S, dd


def bh(p):
    n = len(p); o = np.argsort(p); q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def anomalia(df, ys, wcol, feats, pref):
    pr = oof(df, feats, ys, wcol)
    w = df[wcol].to_numpy(float)
    info, Zs = {}, []
    for y in ys:
        yv = df[y].to_numpy(float)
        pg, pl = pr[y]
        e = yv - pg
        tau2, sig2 = var_modelo(e, w)
        z = e / np.sqrt(tau2 + sig2 / w)
        el = yv - pl
        t2l, s2l = var_modelo(el, w)
        zl = el / np.sqrt(t2l + s2l / w)
        df[f'{pref}pred_{y}'], df[f'{pref}e_{y}'], df[f'{pref}z_{y}'], df[f'{pref}zlin_{y}'] = pg, e, z, zl
        info[y] = {'r2_gb': r2w(yv, pg, w), 'r2_lin': r2w(yv, pl, w), 'tau': float(np.sqrt(tau2)), 'sigma': float(np.sqrt(sig2)),
                   'corr_z_gb_lin': float(np.corrcoef(z, zl)[0, 1])}
        Zs.append(z)
    Z = np.column_stack(Zs)
    df[f'{pref}d2_bruto'] = mcd(Z)[2]
    # A dispersão não é igual em todo o país (ex.: municípios ribeirinhos da Amazônia oscilam mais entre turnos).
    # Escala robusta de z por UF (MAD), encolhida para 1 com peso de 30 cidades: s² = (n·MAD² + 30) / (n + 30).
    esc = {}
    for j in range(Z.shape[1]):
        for uf, idx in df.groupby('uf').indices.items():
            n = len(idx)
            mad = stats.median_abs_deviation(Z[idx, j], scale='normal') if n >= 5 else 1.0
            sc = np.sqrt((n * mad ** 2 + 30) / (n + 30))
            Z[idx, j] /= sc
            esc.setdefault(uf, []).append(round(float(sc), 2))
    for j, y in enumerate(ys):
        df[f'{pref}z_{y}'] = Z[:, j]
    info['escala_uf'] = esc
    mu, S, dd = mcd(Z)
    df[f'{pref}d2'] = dd
    df[f'{pref}p'] = stats.chi2.sf(dd, len(ys))
    df[f'{pref}q'] = bh(df[f'{pref}p'].to_numpy())
    # o mesmo com o modelo linear (robustez)
    ZL = np.column_stack([df[f'{pref}zlin_{y}'] for y in ys])
    _, _, ddl = mcd(ZL)
    df[f'{pref}d2_lin'] = ddl
    info['cov_z'] = S.round(3).tolist()
    return info


info26 = anomalia(base, Y, 'D', FEAT, '')
# 2022 com o que se sabia antes do 2º turno de 2022 (1º turno 2022 + UF)
base22 = base[base.D22 >= 50].copy()
F22pre = ['r22_l1', 'r22_b1', 'r22_ciro1', 'r22_tebet1', 'r22_o1', 'r22_bn1', 'r22_ab1', 'uf_cod']
base22['x22_log'] = np.log(base22.x22_a1)
info22 = anomalia(base22, ['y22_l', 'y22_b', 'y22_n'], 'D22', F22pre + ['x22_log'], 'a22_')
base = base.merge(base22[['uf', 'cd', 'a22_d2', 'a22_p', 'a22_z_y22_l', 'a22_z_y22_b']], on=['uf', 'cd'], how='left')

# direção principal: saldo líquido (Lula − Flávio) acima do esperado, em votos e em z
base['exc_l'] = base.e_y_l * base.D
base['exc_f'] = base.e_y_f * base.D
base['exc_b'] = base.e_y_b * base.D
base['exc_saldo'] = base.exc_l - base.exc_f
base['rank'] = base.d2.rank(ascending=False, method='first').astype(int)
ROT = {'y_l': ('Lula ganhou mais que o esperado', 'Lula ganhou menos que o esperado'),
       'y_f': ('Flávio ganhou mais que o esperado', 'Flávio ganhou menos que o esperado'),
       'y_b': ('brancos e nulos acima do esperado', 'brancos e nulos abaixo do esperado')}
def tipo(r):
    zs = sorted(((abs(r[f'z_{y}']), y, r[f'z_{y}']) for y in Y), reverse=True)
    return ' + '.join(ROT[y][0 if z > 0 else 1] for a, y, z in zs if a >= 3) or ROT[zs[0][1]][0 if zs[0][2] > 0 else 1]
base['tipo'] = base.apply(tipo, axis=1)
base['lula_perdeu'] = base.gl < 0
# controle positivo: eleição suplementar para prefeito no mesmo dia do 2º turno (25/10/2026) leva gente às urnas
# só pela eleição local; o modelo não sabe disso, então essas cidades DEVEM aparecer como anômalas (brancos e nulos)
base['sup_mesmo_dia'] = base.pref24_suplementar.astype(str) == '2026-10-25'
def explic(r):
    if r.sup_mesmo_dia:
        return 'Eleição suplementar para prefeito no mesmo dia do 2º turno'
    if r.inst:
        return 'Comparecimento caiu muito no 2º turno (base instável)'
    return ''
base['explicacao'] = base.apply(explic, axis=1)
base['flavio_perdeu'] = base.gf < 0

# ---------- seções: heterogeneidade e concentração (todas as cidades, para ter a distribuição de referência)
sec = con.execute(f"""SELECT uf, cd_municipio cd, nr_zona z, nr_secao s, nm_local local, bairro,
                             outros_t1 + branco_nulo_t1 + (aptos - (comp2 - var_comparecimento)) D, ganho_lula gl, ganho_flavio gf, branco_nulo_t2 bn
                      FROM '{R}/dados/votos_liquidos/secao.parquet' WHERE uf <> 'ZZ'""").df()
sec = sec[sec.D > 0]
sec = sec.merge(base[['uf', 'cd', 'pred_y_l', 'pred_y_f', 'y_l', 'y_f']], on=['uf', 'cd'], how='inner')


def hetero(g):
    D, gl, gf = g.D.to_numpy(float), g.gl.to_numpy(float), g.gf.to_numpy(float)
    k = len(g)
    if k < 5:
        return pd.Series({'k': k, 'phi': np.nan, 'top10': np.nan, 'neg_l': np.nan})
    # superdispersão do saldo (gl − gf)/D entre seções: χ² de Pearson com variância binomial-multinomial aproximada
    s = (gl - gf) / D
    m = (gl.sum() - gf.sum()) / D.sum()
    pl, pf = max(gl.sum() / D.sum(), 1e-4), max(gf.sum() / D.sum(), 1e-4)
    v = (pl + pf - (pl - pf) ** 2) / D        # Var de (L − F)/D para sorteio multinomial
    phi = np.sum((s - m) ** 2 / np.maximum(v, 1e-9)) / (k - 1)
    # concentração: parte do excesso (sobre o previsto para a cidade) que vem dos 10% de seções que mais contribuem
    # concentração: parte do desvio absoluto (saldo da seção − média da cidade) que vem dos 10% de seções que mais se desviam
    dev = np.abs((gl - gf) - m * D)
    n10 = max(1, int(np.ceil(0.1 * k)))
    top = np.sort(dev)[::-1][:n10].sum() / dev.sum() if dev.sum() else np.nan
    return pd.Series({'k': k, 'phi': phi, 'top10': top, 'neg_l': float(np.mean(gl < 0))})


het = sec.groupby(['uf', 'cd']).apply(hetero, include_groups=False).reset_index()
base = base.merge(het, on=['uf', 'cd'], how='left')
# φ esperado cresce com o tamanho da seção/cidade; percentil de φ entre cidades de porte parecido (quintis de nº de seções)
base['k_q'] = pd.qcut(base.k.fillna(0), 5, labels=False, duplicates='drop')
base['phi_pct'] = base.groupby('k_q').phi.rank(pct=True)
base['top10_pct'] = base.top10.rank(pct=True)

base.to_parquet(f'{OUT}/cidades.parquet')

# ---------- resumo para o relatório
N = len(base)
p = base.p.to_numpy()
calib = {str(a): {'obs': int((p < a).sum()), 'esp': round(a * N, 1)} for a in (0.05, 0.01, 0.001, 1e-4, 1e-6)}
# QQ: quantis de d² observados × χ²(3)
qs = np.linspace(0.005, 0.995, 120)
qq = [[round(float(stats.chi2.ppf(x, 3)), 3), round(float(np.quantile(base.d2, x)), 3)] for x in qs]
qq += [[round(float(stats.chi2.ppf(1 - 1 / (N + 1) * (i + 0.5), 3)), 3), round(float(v), 3)] for i, v in enumerate(np.sort(base.d2)[::-1][:15])]
sig = base[base.q < 0.01]
pers = base.dropna(subset=['a22_d2'])
r_pers = stats.spearmanr(pers.d2, pers.a22_d2)
dir_pers = stats.pearsonr(pers.z_y_l - pers.z_y_f, pers.a22_z_y22_l - pers.a22_z_y22_b)

# importância: correlação de cada variável com o resíduo de 2026 (o que NÃO explica) e R² do modelo
num = lambda v: None if v is None or (isinstance(v, float) and not np.isfinite(v)) else v
cols_top = ['uf', 'cd', 'nome', 'rank', 'd2', 'p', 'q', 'd2_lin', 'd2_bruto', 'tipo', 'explicacao', 'sup_mesmo_dia', 'lula_perdeu', 'flavio_perdeu', 'D', 'aptos1', 'n', 'lv1', 'fv1', 'ov1', 'bn1', 'abst1', 'gl', 'gf', 'bn', 'abst2',
            'y_l', 'y_f', 'y_b', 'pred_y_l', 'pred_y_f', 'pred_y_b', 'z_y_l', 'z_y_f', 'z_y_b', 'zlin_y_l', 'zlin_y_f', 'zlin_y_b',
            'exc_l', 'exc_f', 'exc_b', 'exc_saldo', 'a22_d2', 'a22_p', 'a22_z_y22_l', 'a22_z_y22_b', 'y22_l', 'y22_b', 'l22_2t', 'l22', 'l26',
            'r26_l', 'r26_f', 'r26_ab', 'i24', 'esq24', 'cen24', 'dir24', 'pref_part', 'pref_bloco', 'pref24_nome', 'pref_pct', 'pref24_suplementar',
            'k', 'phi', 'phi_pct', 'top10', 'top10_pct', 'neg_l', 'inst', 'x22_l1', 'x22_l2', 'x22_b1', 'x22_b2']
top = base.sort_values('d2', ascending=False).head(100)[cols_top]

# seções que mais pesam nas 25 primeiras
det = {}
for _, r in top.head(40).iterrows():
    g = sec[(sec.uf == r.uf) & (sec.cd == r.cd)].copy()
    g['exc'] = (g.gl - g.gf) - (r.pred_y_l - r.pred_y_f) * g.D
    sgn = 1 if r.exc_saldo >= 0 else -1
    g = g.sort_values('exc', ascending=sgn < 0).head(5)
    det[f'{r.uf}-{r.cd}'] = [{'z': int(x.z), 's': int(x.s), 'local': x.local, 'bairro': x.bairro, 'D': int(x.D), 'gl': int(x.gl), 'gf': int(x.gf), 'exc': round(float(x.exc))}
                            for x in g.itertuples()]

# por UF: quantas cidades significativas
por_uf = base.assign(sig=base.q < 0.01, lula=(base.q < 0.01) & (base.exc_saldo > 0)).groupby('uf').agg(n=('cd', 'size'), sig=('sig', 'sum'), lula=('lula', 'sum')).reset_index()

r_lin = stats.spearmanr(base.d2, base.d2_lin).statistic
sup = base[base.sup_mesmo_dia]
K, n_top = int(len(sup)), int(sup['rank'].max())
p_sup = float(stats.hypergeom.sf(K - 1, N, K, n_top))   # P(as K cidades caírem todas entre as n_top primeiras por acaso)
controle = {'n': K, 'ranks': sorted(int(x) for x in sup['rank']), 'cidades': sup.sort_values('rank')[['uf', 'nome', 'rank']].to_dict('records'), 'p_hipergeom': p_sup}
t50 = set(base.nlargest(50, 'd2').cd); t100l = set(base.nlargest(100, 'd2_lin').cd)
saida = {
    'meta': {'n_modelo': N, 'n_total': int(len(d)), 'excluidas': int(len(d) - N), 'modelo26': info26, 'modelo22': info22,
             'calibracao': calib, 'n_q01': int((base.q < 0.01).sum()), 'n_q001': int((base.q < 0.001).sum()), 'n_q05': int((base.q < 0.05).sum()),
             'n_q01_lula': int(((base.q < 0.01) & (base.exc_saldo > 0)).sum()), 'n_q01_flavio': int(((base.q < 0.01) & (base.exc_saldo < 0)).sum()),
             'persistencia_spearman_d2': [round(r_pers.statistic, 3), float(r_pers.pvalue)], 'persistencia_direcao_pearson': [round(dir_pers.statistic, 3), float(dir_pers.pvalue)],
             'pers_ambos': int(((pers.q < 0.01) & (pers.a22_p < 0.001)).sum()), 'pers_n': int(len(pers)),
             'controle_positivo': controle,
             'n_q01_sem_explicacao': int(((base.q < 0.01) & (base.explicacao == '')).sum()),
             'robustez_spearman_gb_lin': round(float(r_lin), 3), 'top50_no_top100_linear': len(t50 & t100l),
             'n_lula_perdeu': int(base.lula_perdeu.sum()), 'n_flavio_perdeu': int(base.flavio_perdeu.sum()),
             'phi_mediana': round(float(base.phi.median()), 2), 'top10_mediana': round(float(base.top10.median()), 3),
             'features': {'2026': F26, '2022': F22, '2024': F24}},
    'qq': qq,
    'funil': [[int(r.D), round(float(r.z_y_l - r.z_y_f), 2), round(float(r.d2), 1), r.uf, r.nome, int(r.cd), round(float(r.q), 4)] for r in base.itertuples()],
    'top': [{k: (num(float(v)) if isinstance(v, (float, np.floating)) else (int(v) if isinstance(v, (np.integer,)) else v)) for k, v in r.items()} for r in top.to_dict('records')],
    'secoes': det,
    'por_uf': por_uf.to_dict('records'),
}
json.dump(saida, open(f'{R}/site/dados/anomalias.json', 'w'), ensure_ascii=False, separators=(',', ':'), default=lambda o: None if o is pd.NA else (o.item() if hasattr(o, 'item') else str(o)))
print(json.dumps(saida['meta'], ensure_ascii=False, indent=1, default=str)[:3500])
print(top.head(40)[['uf', 'nome', 'd2', 'q', 'd2_lin', 'd2_bruto', 'tipo', 'D', 'y_l', 'pred_y_l', 'y_f', 'pred_y_f', 'y_b', 'pred_y_b', 'exc_saldo', 'a22_p', 'phi_pct', 'top10', 'pref_part']].to_string())
