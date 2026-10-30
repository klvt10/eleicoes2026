"""Dados estáticos do site do mapa de transferências (site/dados/).

  uf.json             totais por UF (votos líquidos e ganhos)
  cidades.json        totais por município, com o código IBGE
  geo/br.json         GeoJSON das UFs
  geo/<UF>.json       GeoJSON dos municípios da UF (propriedades: cd = código TSE, nome)
  secoes/<UF>.json    {cols, rows}: uma linha por seção, ordenada da que mais transferiu para Lula à que mais transferiu para Flávio
  brasil.json         totais nacionais de 2022 e 2026
  partidos.json       nota de cada partido (método a, nacional e por UF) e bloco fixo (método b)

Governador eleito em 2026 vem de governador_2026.py (baixa_governador_2026.sh).
Histórico (presidente 2022, vereador/prefeito 2024, posicionamento) vem de historico.py (dados/historico);
só de cidade para cima (as seções levam só a transferência).

Transferência líquida = ganho de Lula - ganho de Flávio entre os turnos (votos); ver votos_liquidos.py.
Reusa estudo/ds/mapa (mapa_transferencias.py) para as seções e a malha.
"""
import os, json, duckdb

R = os.path.join(os.path.dirname(__file__), '..')
MAPA = f'{R}/estudo/ds/mapa'
OUT = f'{R}/site/dados'
for d in ('geo', 'secoes'):
    os.makedirs(f'{OUT}/{d}', exist_ok=True)
con = duckdb.connect()
VL = f'{R}/dados/votos_liquidos'
H = f'{R}/dados/historico'
HCOLS = "l22, l26, liq22, gl22, gb22, i24, esq24, cen24, dir24, categoria cat"


def dump(obj, path):
    json.dump(obj, open(path, 'w'), separators=(',', ':'), ensure_ascii=False, default=str)  # datas viram AAAA-MM-DD


def rows(sql):
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# 1º turno 2026 (abst1/abst2 = abstenções do 1º/2º turno, como o TSE) e origem dos votos líquidos: outros candidatos (ov1) + brancos/nulos do 1º turno (bn1) + variação do comparecimento (dcomp)
COLS = """lula_t1::INT lv1, flavio_t1::INT fv1, outros_t1::INT ov1, branco_nulo_t1::INT bn1, var_comparecimento::INT dcomp, comp2::INT comp2,
          liquidos::INT liq, ganho_lula::INT gl, ganho_flavio::INT gf, branco_nulo_t2::INT bn,
          (ganho_lula - ganho_flavio)::INT saldo, saldo_mil mil, base_instavel::INT inst, secoes::INT n,
          a.abst1::INT abst1, a.abst2::INT abst2"""
# abstenção do 1º turno de todas as seções do detalhe, como o TSE soma (inclui seção instalada sem nenhum voto; seção não instalada não tem abstenção)
APTOS = f"""(SELECT uf, cd_municipio, sum(abstencoes) FILTER (t = 1) abst1, sum(abstencoes) FILTER (t = 2) abst2
             FROM (SELECT 1 t, uf, cd_municipio, abstencoes FROM '{R}/dados/parquet/t1_detalhe_secao.parquet' UNION ALL
                   SELECT 2, uf, cd_municipio, abstencoes FROM '{R}/dados/parquet/t2_detalhe_secao.parquet') GROUP BY ALL)"""
dump(rows(f"""SELECT v.uf, {COLS}, {HCOLS}, gov22_nome, gov22_partido, lv22, bv22, g.* EXCLUDE (uf) FROM '{VL}/uf.parquet' v
              JOIN (SELECT uf, sum(abst1) abst1, sum(abst2) abst2 FROM {APTOS} GROUP BY uf) a USING (uf)
              LEFT JOIN '{H}/uf.parquet' h USING (uf)
              LEFT JOIN '{R}/dados/gov2026/governador.parquet' g USING (uf)
              LEFT JOIN (SELECT uf, sum(t2_13)::INT lv22, sum(t2_22)::INT bv22
                         FROM '{R}/dados/parquet/e2022_presidente_secao_wide.parquet' GROUP BY ALL) w USING (uf)
              ORDER BY saldo DESC"""), f'{OUT}/uf.json')
dump(rows(f"""SELECT round(100.0 * sum(t2_13) / sum(t2_13 + t2_22), 1) l22, (sum(t2_comparecimento) - sum(t1_13) - sum(t1_22))::INT liq22,
                     (sum(t2_13) - sum(t1_13))::INT gl22, (sum(t2_22) - sum(t1_22))::INT gb22
              FROM '{R}/dados/parquet/e2022_presidente_secao_wide.parquet'""")[0]
     | rows(f"""SELECT round(100.0 * sum(votos) FILTER (nr_votavel = 13) / sum(votos), 1) l26
                FROM '{R}/dados/parquet/t2_votos_secao.parquet' WHERE nr_votavel IN (13, 22)""")[0]
     # blocos de vereador 2024 no Brasil, com a mesma conta de historico.py (vereador(): votos x bloco de partidos.csv)
     | rows(f"""WITH ver AS (SELECT uf, CASE WHEN nr_votavel >= 10000 THEN nr_votavel // 1000 ELSE nr_votavel END nr_partido, sum(votos) votos
                              FROM '{R}/dados/parquet/e2024_vereador_votos_secao.parquet' WHERE turno = 1 AND nr_votavel NOT IN (95, 96, 97, 98) GROUP BY ALL)
                SELECT round(100.0 * sum(votos) FILTER (bloco = 'esquerda') / sum(votos), 1) esq24, round(100.0 * sum(votos) FILTER (bloco = 'centro') / sum(votos), 1) cen24,
                       round(100.0 * sum(votos) FILTER (bloco = 'direita') / sum(votos), 1) dir24
                FROM ver JOIN read_csv('{H}/partidos.csv') USING (uf, nr_partido)""")[0], f'{OUT}/brasil.json')
dump(rows(f"""SELECT sg_partido partido, any_value(bloco) bloco, round(sum(votos_uf * nota_br) / sum(votos_uf), 1) nota, sum(votos_uf)::INT votos
              FROM read_csv('{H}/partidos.csv') GROUP BY 1 ORDER BY nota DESC"""), f'{OUT}/partidos.json')

geo = json.load(open(f'{MAPA}/mapa_geo.json'))
ibge = {r['cd_municipio']: r['ibge'] for r in geo if r['nivel'] == 'mun'}
cid = rows(f"""SELECT v.uf, v.cd_municipio cd, nm_municipio nome, {COLS}, {HCOLS}, pref24_nome, pref24_partido,
                     m.* EXCLUDE (uf, cd_municipio), w.lv22, w.bv22
              FROM '{VL}/cidade.parquet' v JOIN {APTOS} a USING (uf, cd_municipio)
              LEFT JOIN '{H}/cidade.parquet' h USING (uf, cd_municipio)
              LEFT JOIN '{H}/cidade_municipal.parquet' m USING (uf, cd_municipio)
              LEFT JOIN (SELECT uf, cd_municipio, sum(t2_13)::INT lv22, sum(t2_22)::INT bv22
                         FROM '{R}/dados/parquet/e2022_presidente_secao_wide.parquet' GROUP BY ALL) w USING (uf, cd_municipio)
              ORDER BY uf, nome""")
for c in cid:
    c['ibge'] = ibge.get(c['cd'])
dump(cid, f'{OUT}/cidades.json')

feat = lambda r, props: {'type': 'Feature', 'properties': props, 'geometry': {'type': 'MultiPolygon', 'coordinates': r['coords']}}
dump({'type': 'FeatureCollection', 'features': [feat(r, {'uf': r['uf']}) for r in geo if r['nivel'] == 'uf']}, f'{OUT}/geo/br.json')
for uf in sorted({r['uf'] for r in geo if r['nivel'] == 'mun'}):
    dump({'type': 'FeatureCollection', 'features': [feat(r, {'cd': r['cd_municipio'], 'nome': r['nome']})
                                                    for r in geo if r['nivel'] == 'mun' and r['uf'] == uf]}, f'{OUT}/geo/{uf}.json')

# Seções: SP volta a ser um arquivo só (aqui não há limite de tamanho por arquivo)
for uf in sorted({f[5:7] for f in os.listdir(MAPA) if f.endswith('.csv')}):
    cur = con.execute(f"""SELECT m.cd_municipio cd, m.nr_zona z, m.nr_secao s, nr_local l, local, bairro, lat, lon,
                                 liquidos liq, ganho_lula gl, ganho_flavio gf, saldo, instavel inst
                          FROM read_csv('{MAPA}/mapa_{uf}*.csv', union_by_name=true) m
                          ORDER BY saldo DESC, cd, z, s""")
    dump({'cols': [c[0] for c in cur.description], 'rows': cur.fetchall()}, f'{OUT}/secoes/{uf}.json')
print(len(cid), 'cidades;', sum(1 for _ in os.scandir(f'{OUT}/secoes')), 'arquivos de seções')
