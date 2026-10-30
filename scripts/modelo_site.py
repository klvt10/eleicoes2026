"""Modelo de previsão da fatia dos votos líquidos (ganho de Lula ÷ (ganho de Lula + ganho de Flávio) entre os turnos de 2026)
a partir do voto para governador, senador e deputados no 1º turno de 2026, por cidade; e o detalhe por cidade para o card.

Modelo: perfil do lugar pela proporção em que ele votou no 1º turno de 2026, para presidente (Lula ÷ (Lula + Flávio)) e
para os outros cargos (campo Lula ÷ (campo Lula + campo Flávio) em governador e senador; esquerda ÷ (esquerda + direita) em
deputados), metade do peso em cada parte. Previsão = perfil × votos líquidos. Previsão por estado = soma das cidades.

Saídas em site/dados/comparativo/:
  modelo.json            coeficientes, R², n; por UF e Brasil: líquidos, real, previsto, diferença (p.p. e votos)
  cidades_modelo.json    por cidade: líquidos, ganhos, real, previsto, diferença e os preditores
  detalhe/<UF>.json      por cidade: candidatos a presidente no 1º turno, totais dos dois turnos, candidatos a governador e senador
"""
import os, json, duckdb
R = os.path.join(os.path.dirname(__file__), '..')
P, OUT = f'{R}/dados/parquet', f'{R}/site/dados/comparativo'
os.makedirs(f'{OUT}/detalhe', exist_ok=True)
con = duckdb.connect()
cid = {(c['uf'], c['cd']): c for c in json.load(open(f'{OUT}/cidades.json'))}

# totais por cidade nos dois turnos (bweb)
tot = {}
for t in (1, 2):
    for uf, cd, l, f, b, n, comp, aptos, val in con.execute(f"""SELECT uf, cd_municipio, sum(v13), sum(v22), sum(brancos), sum(nulos), sum(comparecimento), sum(aptos),
        sum(total_votos - brancos - nulos) FROM '{P}/bweb_2026_t{t}_secao.parquet' WHERE uf <> 'ZZ' GROUP BY 1, 2""").fetchall():
        tot.setdefault((uf, cd), {})[f't{t}'] = {'l': int(l), 'f': int(f), 'brancos': int(b), 'nulos': int(n), 'validos': int(val), 'comp': int(comp), 'aptos': int(aptos), 'abst': int(aptos - comp)}

# MODELO: perfil do lugar pela proporção em que ele votou no 1º turno de 2026, para presidente e para os outros cargos.
# Para cada cidade:
#   pres  = Lula ÷ (Lula + Flávio) no 1º turno
#   gov   = campo Lula ÷ (campo Lula + campo Flávio) para governador   (campo pela coligação: PT = Lula, PL = Flávio)
#   sen   = idem para senador
#   dfed  = esquerda ÷ (esquerda + direita) para deputado federal   (bloco pelo partido)
#   dest  = idem para deputado estadual
#   perfil = PESO_PRES × pres + (1 − PESO_PRES) × média(gov, sen, dfed, dest disponíveis)
# Previsão: ganho de Lula = perfil × entradas + proporção do 1º turno × saídas; ganho de Flávio = o resto. Entradas = eliminados +
# quedas de brancos/nulos, abstenção e aptos; saídas = altas dessas três (negativas). Votos líquidos = entradas + saídas = outros candidatos no 1º turno
# + queda de brancos/nulos + queda da abstenção (+ variação de aptos) = ganho de Lula + ganho de Flávio. Nada do 2º turno
# entra, exceto o total de votos líquidos de cada cidade (o tamanho, não a direção). Estado = soma das cidades.
PESO_PRES = 0.5
CARGOS = (('gov', 'gl', 'gf'), ('sen', 'sl', 'sf'), ('dfed', 'df_esq', 'df_dir'), ('dest', 'de_esq', 'de_dir'))
def razao(a, b):
    a, b = (float(a) if a is not None else None), (float(b) if b is not None else None)
    return a / (a + b) if a is not None and b is not None and a + b > 0 else None
elim = {}
for uf, cd, v in con.execute(f"""SELECT uf, cd_municipio, sum(votos) FROM '{P}/t1_cargos_cidade.parquet'
    WHERE cd_cargo = 1 AND uf <> 'ZZ' AND tipo_votavel IN ('Nominal', 'Legenda') AND nr_votavel NOT IN (13, 22) GROUP BY 1, 2""").fetchall():
    elim[(uf, cd)] = int(v)
rows = []
for k, c in cid.items():
    t = tot.get(k)
    if not t or 't1' not in t or 't2' not in t or t['t1']['validos'] <= 0: continue
    t1, t2 = t['t1'], t['t2']
    gl, gf = t2['l'] - t1['l'], t2['f'] - t1['f']
    dbn = (t1['brancos'] + t1['nulos']) - (t2['brancos'] + t2['nulos']); dabst = t1['abst'] - t2['abst']; dapt = t2['aptos'] - t1['aptos']
    outros1 = elim.get(k, 0); liq = outros1 + dbn + dabst + dapt
    pres = razao(t1['l'], t1['f'])
    if pres is None: continue
    x = {'dbn': dbn, 'dabst': dabst, 'dapt': dapt, 'outros1': outros1, 'pres': round(100 * pres, 2)}
    outros = []
    for nome, kl, kf in CARGOS:
        r = razao(c.get(kl), c.get(kf))
        if r is None: continue
        outros.append(r); x[nome] = round(100 * r, 2)
    media_outros = sum(outros) / len(outros) if outros else pres
    x['outros'] = round(100 * media_outros, 2)
    perfil = PESO_PRES * pres + (1 - PESO_PRES) * media_outros
    x['perfil'] = round(100 * perfil, 2)
    # entradas (eliminados; brancos/nulos, abstenção e aptos a menos) seguem o perfil; saídas (brancos/nulos, abstenção ou aptos
    # a mais, que tiram votos dos dois) seguem a proporção do 1º turno entre Lula e Flávio
    entradas = outros1 + max(dbn, 0) + max(dabst, 0) + max(dapt, 0); saidas = min(dbn, 0) + min(dabst, 0) + min(dapt, 0)
    x['entradas'] = entradas; x['saidas'] = saidas
    prev_gl = perfil * entradas + pres * saidas; prev_gf = liq - prev_gl
    x['prev_gl'] = int(round(prev_gl))
    base = liq if liq > 0 else entradas   # com votos líquidos negativos, as porcentagens usam as entradas como base
    pc = lambda v: round(100.0 * v / base, 2) if base > 0 else None
    rows.append({'uf': k[0], 'cd': k[1], 'nome': c['nome'], 'liq': liq, 'gl': gl, 'gf': gf, 'pool': t2['comp'] - t1['l'] - t1['f'], 'bn2': t2['brancos'] + t2['nulos'],
                 'l1': t1['l'], 'f1': t1['f'], 'l2': t2['l'], 'f2': t2['f'], 'votos': int(c['votos']),
                 'prev_gl': int(round(prev_gl)), 'prev_gf': int(round(prev_gf)),
                 'real_l': pc(gl), 'real_f': pc(gf), 'prev_l': pc(prev_gl), 'prev_f': pc(prev_gf),
                 'dif_l': round(pc(gl) - pc(prev_gl), 2) if base > 0 else None, 'dif_f': round(pc(gf) - pc(prev_gf), 2) if base > 0 else None,
                 'dif_gl': int(round(gl - prev_gl)), 'dif_gf': int(round(gf - prev_gf)), 'base': base, 'x': x})
XSOMA = ['dbn', 'dabst', 'dapt', 'outros1', 'prev_gl', 'entradas', 'saidas']
assert abs(sum(r['liq'] for r in rows) - sum(r['gl'] + r['gf'] for r in rows)) < 1e-6 * max(1, sum(r['liq'] for r in rows)), 'identidade dos líquidos'

def agrega(rs):
    liq = sum(r['liq'] for r in rs); gl = sum(r['gl'] for r in rs); gf = sum(r['gf'] for r in rs)
    pgl = sum(r['prev_gl'] for r in rs); pgf = sum(r['prev_gf'] for r in rs)
    x = {k: sum(r['x'][k] for r in rs) for k in XSOMA}
    w = [abs(r['liq']) for r in rs]
    for key in ('pres', 'gov', 'sen', 'dfed', 'dest', 'outros', 'perfil'):
        vals = [(r['x'][key], wi) for r, wi in zip(rs, w) if r['x'].get(key) is not None]
        if vals: x[key] = round(sum(v * wi for v, wi in vals) / (sum(wi for _, wi in vals) or 1), 2)
    base = liq if liq > 0 else x['entradas']
    pc = lambda v: round(100.0 * v / base, 2) if base > 0 else None
    return {'liq': liq, 'gl': gl, 'gf': gf, 'pool': sum(r['pool'] for r in rs), 'bn2': sum(r['bn2'] for r in rs), 'prev_gl': pgl, 'prev_gf': pgf, 'base': base,
            'l1': sum(r['l1'] for r in rs), 'f1': sum(r['f1'] for r in rs), 'l2': sum(r['l2'] for r in rs), 'f2': sum(r['f2'] for r in rs),
            'real_l': pc(gl), 'real_f': pc(gf), 'prev_l': pc(pgl), 'prev_f': pc(pgf),
            'dif_l': round(pc(gl) - pc(pgl), 2) if base > 0 else None, 'dif_f': round(pc(gf) - pc(pgf), 2) if base > 0 else None,
            'dif_gl': gl - pgl, 'dif_gf': gf - pgf, 'cidades': len(rs), 'x': x}
ufs = sorted({r['uf'] for r in rows})
modelo = {'regra': 'perfil_lugar_2026', 'n': len(rows), 'peso_pres': PESO_PRES, 'brasil': agrega(rows), 'ufs': {u: agrega([r for r in rows if r['uf'] == u]) for u in ufs}}
print('Brasil', {k: v for k, v in modelo['brasil'].items() if k != 'x'}); print('  origens', modelo['brasil']['x'])
dump = lambda o, p: json.dump(o, open(p, 'w'), separators=(',', ':'), ensure_ascii=False)
dump(modelo, f'{OUT}/modelo.json')
dump(rows, f'{OUT}/cidades_modelo.json')

# detalhe por cidade para o card: candidatos a presidente (1º turno), totais, candidatos a governador e senador (>= 3% na cidade)
nomes = {}
cands = {}
for uf, cd, nr, nome, partido, votos in con.execute(f"""SELECT uf, cd_municipio, nr_votavel, any_value(nm_votavel), any_value(sg_partido), sum(votos)::BIGINT
    FROM '{P}/t1_cargos_cidade.parquet' WHERE cd_cargo = 1 AND uf <> 'ZZ' AND tipo_votavel IN ('Nominal', 'Legenda') GROUP BY 1, 2, 3""").fetchall():
    nomes[nr] = [nome, partido]; cands.setdefault((uf, cd), []).append([nr, int(votos)])
camp = {}
for cargo, pasta, arq in ((3, 'gov2026', 'candidatos_gov'), (5, 'sen2026', 'candidatos_sen')):
    for uf, cd, nr, nome, partido, campo, votos, tot_c in con.execute(f"""
        WITH v AS (SELECT uf, cd_municipio, nr_votavel, sum(votos) votos, sum(sum(votos)) OVER (PARTITION BY uf, cd_municipio) tot
                   FROM '{P}/t1_cargos_cidade.parquet' WHERE cd_cargo = {cargo} AND uf <> 'ZZ' AND tipo_votavel IN ('Nominal', 'Legenda') GROUP BY 1, 2, 3)
        SELECT v.uf, v.cd_municipio, v.nr_votavel, c.nome, c.partido, c.campo, v.votos::BIGINT, v.tot::BIGINT
        FROM v JOIN '{R}/dados/{pasta}/{arq}.parquet' c ON c.uf = v.uf AND c.nr_votavel = v.nr_votavel WHERE v.votos >= 0.03 * v.tot""").fetchall():
        camp.setdefault((uf, cd), {}).setdefault('gov' if cargo == 3 else 'sen', []).append({'nome': nome, 'partido': partido, 'campo': campo, 'pct': round(100.0 * votos / tot_c, 1), 'votos': int(votos)})
for u in ufs:
    det = {}
    for (uf, cd), t in tot.items():
        if uf != u or 't1' not in t or 't2' not in t: continue
        cs = sorted(cands.get((uf, cd), []), key=lambda x: -x[1])
        det[str(cd)] = {'cands': cs, 't1': t['t1'], 't2': t['t2'],
                        'gov': sorted(camp.get((uf, cd), {}).get('gov', []), key=lambda x: -x['votos']),
                        'sen': sorted(camp.get((uf, cd), {}).get('sen', []), key=lambda x: -x['votos'])}
    dump({'nomes': {str(k): v for k, v in nomes.items()}, 'cidades': det}, f'{OUT}/detalhe/{u}.json')
print(len(rows), 'cidades no modelo;', len(ufs), 'arquivos de detalhe')
print('Brasil', modelo['brasil'])
for u in ufs: m = modelo['ufs'][u]; print(u, 'Lula real/prev', m['real_l'], m['prev_l'], m['dif_l'], m['dif_gl'], '| Flávio', m['real_f'], m['prev_f'], m['dif_f'], m['dif_gf'])
