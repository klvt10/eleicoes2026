"""Confere nossos totais de presidente 2026 (1º e 2º turno) contra o resultado oficial por UF do portal de resultados do TSE.
Baixa .../ele2026/<eleição>/dados/<uf>/<uf>-c0001-e<eleição>-u.json para cada UF (e br) e compara
Lula, Flávio, outros candidatos, brancos, nulos (total, com anulados), comparecimento e abstenção."""
import os, json, urllib.request, duckdb

R = os.path.join(os.path.dirname(__file__), '..')
RAW = f'{R}/dados/oficial_portal'
UFS = 'ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz br'.split()
ELE = {1: 6257, 2: 6258}


def baixa(t, uf):
    f = f'{RAW}/t{t}_{uf}.json'
    if not os.path.exists(f):
        url = f'https://resultados.tse.jus.br/oficial/ele2026/{ELE[t]}/dados/{uf}/{uf}-c0001-e{ELE[t]:06d}-u.json'
        req = urllib.request.Request(url, headers={'User-Agent': 'pesquisa-eleicoes/1.0'})
        open(f, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
    return json.load(open(f))


def oficial(t, uf):
    d = baixa(t, uf)
    cand = {c['n']: int(c['vap']) for ag in d['carg'][0].get('agr', []) for p in ag['par'] for c in p['cand']}
    v = d['v']
    return {'lula': cand.get('13', 0), 'flavio': cand.get('22', 0), 'outros': int(v['vv']) - cand.get('13', 0) - cand.get('22', 0),
            'brancos_nulos': int(v['vb']) + int(v['tvn']), 'comparecimento': int(d['e']['c']) if 'c' in d['e'] else int(v['tv']),
            'abstencao': int(d['e']['a'])}


con = duckdb.connect()
uf_tab = con.execute(f"""SELECT uf, lula_t1, flavio_t1, outros_t1, branco_nulo_t1, comp2 - var_comparecimento comp1,
                                lula_t1 + ganho_lula lula_t2, flavio_t1 + ganho_flavio flavio_t2, branco_nulo_t2, comp2, abst1, abst2
                         FROM '{R}/dados/votos_liquidos/uf.parquet'
                         JOIN (SELECT uf, sum(abstencoes) FILTER (t = 1) abst1, sum(abstencoes) FILTER (t = 2) abst2
                               FROM (SELECT 1 t, uf, abstencoes FROM '{R}/dados/parquet/t1_detalhe_secao.parquet' UNION ALL
                                     SELECT 2, uf, abstencoes FROM '{R}/dados/parquet/t2_detalhe_secao.parquet') GROUP BY uf) USING (uf)""").df().set_index('uf')
erros = 0
for uf in UFS:
    o1, o2 = oficial(1, uf), oficial(2, uf)
    r = uf_tab.sum() if uf == 'br' else uf_tab.loc[uf.upper()]
    nosso = {1: {'lula': r.lula_t1, 'flavio': r.flavio_t1, 'outros': r.outros_t1, 'brancos_nulos': r.branco_nulo_t1, 'comparecimento': r.comp1, 'abstencao': r.abst1},
             2: {'lula': r.lula_t2, 'flavio': r.flavio_t2, 'outros': 0, 'brancos_nulos': r.branco_nulo_t2, 'comparecimento': r.comp2, 'abstencao': r.abst2}}
    for t, o in ((1, o1), (2, o2)):
        dif = {k: int(nosso[t][k]) - o[k] for k in o if int(nosso[t][k]) != o[k]}
        if dif:
            erros += 1
            print(f'{uf.upper()} {t}º turno: diferenças (nosso − oficial) {dif}')
print('UFs x turnos com diferença:', erros, 'de', 2 * len(UFS))
