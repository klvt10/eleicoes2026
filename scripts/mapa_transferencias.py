"""Arquivos do mapa de transferências (votos líquidos) para o painel.

Transferência de uma seção = ganho de Lula - ganho de Flávio do 1º para o 2º turno (votos), ver votos_liquidos.py.

Saídas em estudo/ds/mapa/:
  mapa_geo.json          contornos (malha IBGE, qualidade mínima): nivel 'uf' para cada estado e
                         nivel 'mun' para cada município, com o código TSE
  mapa_<UF>.csv          uma linha por seção: local, coordenadas e transferências (SP em SP1 capital / SP2 interior);
                         brancos/nulos do 2º turno = liquidos - ganho_lula - ganho_flavio
"""
import os, json, re, unicodedata, duckdb

R = os.path.join(os.path.dirname(__file__), '..')
GEO = f'{R}/dados/geo/raw'
OUT = f'{R}/estudo/ds/mapa'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()

norm = lambda s: re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper())
# Grafias que diferem entre TSE e IBGE além de acento/pontuação: (UF, nome TSE normalizado) -> nome IBGE normalizado
APELIDO = {
    ('SP', norm('SÃO LUÍS DO PARAITINGA')): norm("São Luiz do Paraitinga"),
    ('PR', norm('MUNHOZ DE MELLO')): norm("Munhoz de Melo"),
    ('RN', norm('BOA SAÚDE')): norm("Januário Cicco"),
    ('SE', norm('AMPARO DE SÃO FRANCISCO')): norm("Amparo do São Francisco"),
    ('PA', norm('ELDORADO DOS CARAJÁS')): norm("Eldorado do Carajás"),
    ('MG', norm('BARÃO DE MONTE ALTO')): norm("Barão do Monte Alto"),
    ('RO', norm('ESPIGÃO DO OESTE')): norm("Espigão D'Oeste"),
    ('MG', norm('DONA EUSÉBIA')): norm("Dona Euzébia"),
    ('MG', norm('SÃO THOMÉ DAS LETRAS')): norm("São Tomé das Letras"),
    ('RR', norm('SÃO LUIZ')): norm("São Luiz do Anauá"),
    ('MT', norm('SANTO ANTÔNIO DO LEVERGER')): norm("Santo Antônio de Leverger"),
    ('RO', norm('ALVORADA DO OESTE')): norm("Alvorada D'Oeste"),
    ('GO', norm('BOM JESUS')): norm("Bom Jesus de Goiás"),
}  # Boa Saúde (TSE) = Januário Cicco (IBGE)

ibge = json.load(open(f'{GEO}/municipios.json'))
uf_sigla = {str(m['UF-id']): m['UF-sigla'] for m in ibge}
ibge_nome = {(m['UF-sigla'], norm(m['municipio-nome'])): (m['municipio-id'], m['municipio-nome']) for m in ibge}

tse = con.execute(f"""SELECT DISTINCT uf, cd_municipio, nm_municipio FROM '{R}/dados/votos_liquidos/secao.parquet'
                     WHERE uf <> 'ZZ'""").fetchall()
tse2ibge, falta = {}, []
for uf, cd, nm in tse:
    k = (uf, APELIDO.get((uf, norm(nm)), norm(nm)))
    if k in ibge_nome:
        tse2ibge[ibge_nome[k][0]] = cd
    else:
        falta.append((uf, cd, nm))
print('municípios TSE sem par no IBGE:', len(falta), falta[:30])


def arred(c):
    """Arredonda coordenadas a 3 casas (~100 m) e tira pontos repetidos."""
    if isinstance(c[0], (int, float)):
        return [round(c[0], 3), round(c[1], 3)]
    out = [arred(x) for x in c]
    if out and isinstance(out[0][0], (int, float)):
        out = [p for i, p in enumerate(out) if i == 0 or p != out[i - 1]]
    return out


def poligonos(g):
    return arred(g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']])


br = json.load(open(f'{GEO}/br_uf.json'))
geo = [{'nivel': 'uf', 'uf': uf_sigla[f['properties']['codarea']], 'coords': poligonos(f['geometry'])} for f in br['features']]
nome_ibge = {m['municipio-id']: m['municipio-nome'] for m in ibge}
for uf in sorted({u for u, _, _ in tse}):
    for f in json.load(open(f'{GEO}/mun_{uf}.json'))['features']:
        ib = int(f['properties']['codarea'])
        geo.append({'nivel': 'mun', 'uf': uf, 'cd_municipio': tse2ibge.get(ib), 'ibge': ib, 'nome': nome_ibge.get(ib, ''),
                    'coords': poligonos(f['geometry'])})
json.dump(geo, open(f'{OUT}/mapa_geo.json', 'w'), separators=(',', ':'), ensure_ascii=False)

# Seções: coordenadas do local só quando validadas (coord_ok)
con.execute(f"""
CREATE TABLE m AS
SELECT s.uf, s.cd_municipio, s.nr_zona, s.nr_secao, s.nr_local, s.nm_local local, s.bairro,
       CASE WHEN l.coord_ok THEN round(l.lat, 5) END lat, CASE WHEN l.coord_ok THEN round(l.lon, 5) END lon,
       s.liquidos::INT liquidos, s.ganho_lula::INT ganho_lula, s.ganho_flavio::INT ganho_flavio,
       (s.ganho_lula - s.ganho_flavio)::INT saldo,
       s.base_instavel::INT instavel
FROM '{R}/dados/votos_liquidos/secao.parquet' s
LEFT JOIN '{R}/dados/parquet/local_2026_historico.parquet' l USING (uf, cd_municipio, nr_zona, nr_local)""")
print(con.execute("SELECT count(*), count(lat), sum(saldo) FROM m").fetchone())
for uf, in con.execute("SELECT DISTINCT uf FROM m ORDER BY 1").fetchall():
    partes = {'SP1': 'cd_municipio = 71072', 'SP2': 'cd_municipio <> 71072'} if uf == 'SP' else {uf: 'TRUE'}
    for nome, filtro in partes.items():
        con.execute(f"""COPY (SELECT * EXCLUDE (uf) FROM m WHERE uf = '{uf}' AND {filtro} ORDER BY saldo DESC, cd_municipio, nr_zona, nr_secao)
                        TO '{OUT}/mapa_{nome}.csv' (HEADER)""")
