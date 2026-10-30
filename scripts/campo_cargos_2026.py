"""Candidatos a governador e a senador 2026 (1º turno) com partido, coligação e CAMPO em relação à disputa presidencial:
  lula   = coligação com o PT, ou partido de esquerda que não coligou com o PT (PSOL, REDE, UP, PSTU, PCB, PCO)
  flavio = coligação com o PL, ou candidato do NOVO sem o PT na coligação
  outro  = nenhum dos dois (centro/independente: ex. Cleitinho em MG, Raquel Lyra em PE, Daniel Vilela em GO)
Se a coligação tem PT e PL ao mesmo tempo (não ocorre em 2026), vale o partido do candidato.
Saída: dados/gov2026/candidatos_gov.parquet e dados/sen2026/candidatos_sen.parquet (e .csv)"""
import os, json, glob, duckdb
R = os.path.join(os.path.dirname(__file__), '..')
ESQ = {'PSOL', 'REDE', 'UP', 'PSTU', 'PCB', 'PCO'}
def classifica(pasta, saida):
    rows = []
    for f in sorted(glob.glob(f'{R}/dados/{pasta}/raw/t1_*.json')):
        uf = f[-7:-5].upper(); d = json.load(open(f))
        for cargo in d['carg']:
            for agr in cargo.get('agr', []):
                for par in agr.get('par', []):
                    for c in par.get('cand', []):
                        col = (agr.get('com') or par['sg']).replace('**', '')
                        partes = {p.strip() for p in col.split('/')}
                        pt, pl = 'PT' in partes, 'PL' in partes
                        if pt and pl: campo = 'lula' if par['sg'] == 'PT' else 'flavio' if par['sg'] == 'PL' else 'outro'
                        elif pt or par['sg'] in ESQ: campo = 'lula'
                        elif pl or par['sg'] == 'NOVO': campo = 'flavio'
                        else: campo = 'outro'
                        rows.append({'uf': uf, 'nr_votavel': int(c['n']), 'nome': c['nmu'], 'partido': par['sg'], 'coligacao': col,
                                     'votos_t1': int(c.get('vap') or 0), 'eleito_t1': c.get('e') == 's', 'campo': campo})
    con = duckdb.connect()
    con.execute("CREATE TABLE g AS SELECT * FROM (SELECT unnest(?, recursive := true))", [rows])
    con.execute(f"COPY g TO '{R}/dados/{pasta}/{saida}.parquet' (FORMAT parquet)")
    con.execute(f"COPY (SELECT * FROM g ORDER BY uf, votos_t1 DESC) TO '{R}/dados/{pasta}/{saida}.csv' (HEADER, DELIMITER ';')")
    print(f'--- {pasta}')
    print(con.execute("""SELECT uf, string_agg(nome || ' (' || partido || ') ' || campo, ' | ' ORDER BY votos_t1 DESC) FILTER (votos_t1 >= 0.05 * tot) principais
      FROM (SELECT *, sum(votos_t1) OVER (PARTITION BY uf) tot FROM g) GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
    print(con.execute("SELECT campo, count(*) candidatos, sum(votos_t1) votos FROM g GROUP BY 1").fetchdf().to_string(index=False))
classifica('gov2026', 'candidatos_gov')
classifica('sen2026', 'candidatos_sen')
