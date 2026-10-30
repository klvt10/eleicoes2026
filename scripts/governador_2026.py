"""Governador eleito em 2026 por UF, a partir dos arquivos baixados por baixa_governador_2026.sh -> dados/gov2026/governador.parquet."""
import os, json, glob, duckdb

R = os.path.join(os.path.dirname(__file__), '..')
RAW = f'{R}/dados/gov2026/raw'
num = lambda s: float(str(s).replace(',', '.')) if s not in (None, '') else None


def candidatos(path):
    d = json.load(open(path))
    out = []
    for cargo in d['carg']:
        for agr in cargo.get('agr', []):
            for par in agr.get('par', []):
                for c in par.get('cand', []):
                    out.append({'nome': c['nmu'], 'partido': par['sg'], 'coligacao': agr.get('com'), 'votos': int(c.get('vap') or 0),
                                'pct': num(c.get('pvapn')), 'eleito': c.get('e') == 's', 'situacao': c.get('st'),
                                'vice': (c.get('vs') or [{}])[0].get('nmu'), 'vice_partido': (c.get('vs') or [{}])[0].get('sgp')})
    return sorted(out, key=lambda c: -c['votos']), d


linhas = []
for f in sorted(glob.glob(f'{RAW}/t1_*.json')):
    uf = f[-7:-5].upper()
    c1, d1 = candidatos(f)
    t2 = f'{RAW}/t2_{uf.lower()}.json'
    turno, cs = (2, candidatos(t2)[0]) if os.path.exists(t2) else (1, c1)
    el = next((c for c in cs if c['eleito']), None)
    seg = next((c for c in cs if c is not el), None)
    linhas.append({'uf': uf, 'gov26_turno': turno, 'gov26_nome': el and el['nome'], 'gov26_partido': el and el['partido'],
                   'gov26_pct': el and el['pct'], 'gov26_votos': el and el['votos'], 'gov26_vice': el and el['vice'],
                   'gov26_vice_partido': el and el['vice_partido'], 'gov26_coligacao': el and el['coligacao'],
                   'gov26_2nome': seg and seg['nome'], 'gov26_2partido': seg and seg['partido'], 'gov26_2pct': seg and seg['pct'],
                   'gov26_t1_pct': el and next((c['pct'] for c in c1 if c['nome'] == el['nome']), None),
                   'gov26_totalizado': d1.get('s', {}).get('pst')})
con = duckdb.connect()
con.execute("CREATE TABLE g AS SELECT * FROM (SELECT unnest(?, recursive := true))", [linhas])
con.execute(f"COPY g TO '{R}/dados/gov2026/governador.parquet' (FORMAT parquet)")
print(con.execute("SELECT uf, gov26_turno, gov26_nome, gov26_partido, gov26_pct, gov26_2nome, gov26_2partido, gov26_2pct FROM g").df().to_string())
