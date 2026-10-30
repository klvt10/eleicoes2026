"""Casa os locais de votação de 2026 com os de 2022 e 2024 por geolocalização + nome, e gera
comparativos por local de votação (unidade estável entre eleições) e a confiança do casamento por seção.

Entrada: dados/geo/raw/eleitorado_local_votacao_{2022,2024,2026}.zip (cadastro do TSE com lat/lon)
         + Parquets de dados/parquet (build_t1.py, build_t2.py, build_2022_2024.py).
Uso: python scripts/geo_locais.py

Casamento de cada local 2026 com locais do MESMO município no ano anterior, em níveis
(o primeiro que satisfizer vence; dentro do nível, menor distância e maior similaridade):
  1 geo_nome    distância <= 150 m e nome parecido (jaro-winkler >= 0.85)
  2 geo         distância <= 75 m (mesmo ponto, nome mudou)
  3 nome        nome muito parecido (>= 0.93) + mesmo bairro, CEP, endereço parecido ou mesmo nº de local
  4 geo_proximo distância <= 400 m (confiança baixa)
Coordenadas só valem se forem válidas e não forem "centroide" (mesmo ponto para >= 3 locais de nomes diferentes).
"""
import duckdb, glob, os, shutil, subprocess

D = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dados'))
P = f'{D}/parquet'
G = f'{D}/geo'
OPTS = "delim=';', header=true, encoding='latin-1', all_varchar=true, union_by_name=true"
con = duckdb.connect()
con.execute("SET preserve_insertion_order=false")

# Normalização de nomes de escola: sem acento/pontuação e abreviações comuns expandidas
NORM = r"""trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
  ' ' || regexp_replace(upper(strip_accents({c})), '[^A-Z0-9 ]', ' ', 'g') || ' ',
  ' (E E|EE|EEEF|EEEM|EEFM|E ESTADUAL|ESC EST) ', ' ESCOLA ESTADUAL ', 'g'),
  ' (E M|EM|EMEF|EMEI|EMEIF|E MUN|ESC MUN|ESC MUNICIPAL) ', ' ESCOLA MUNICIPAL ', 'g'),
  ' (ESC|EESC) ', ' ESCOLA ', 'g'), ' (COL|C E|CE) ', ' COLEGIO ', 'g'),
  ' (PROF|PROFA|PROFESSORA) ', ' PROFESSOR ', 'g'), '\s+', ' ', 'g'))"""


def locais():
    for a in (2022, 2024, 2026):
        tmp = f'{G}/csv/{a}'
        if not glob.glob(f'{tmp}/*.csv'):
            os.makedirs(tmp, exist_ok=True)
            subprocess.run(['unzip', '-q', '-o', f'{G}/raw/eleitorado_local_votacao_{a}.zip', '*.csv', '-d', tmp], check=True)
        csvs = [c for c in glob.glob(f'{tmp}/*.csv') if 'BRASIL' not in c]  # BRASIL duplica os arquivos por UF
        lst = '[' + ','.join(f"'{c}'" for c in csvs) + ']'
        con.execute(f"""COPY (
          WITH s AS (
            SELECT SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, NM_MUNICIPIO nm_municipio, CAST(NR_ZONA AS INT) nr_zona,
                   CAST(NR_LOCAL_VOTACAO AS INT) nr_local, NM_LOCAL_VOTACAO nm_local, DS_ENDERECO endereco, NM_BAIRRO bairro,
                   NULLIF(NR_CEP, '-1') cep, TRY_CAST(replace(NR_LATITUDE, ',', '.') AS DOUBLE) lat,
                   TRY_CAST(replace(NR_LONGITUDE, ',', '.') AS DOUBLE) lon, CAST(QT_ELEITOR_SECAO AS INT) eleitores
            FROM read_csv({lst}, {OPTS}) WHERE NR_TURNO = '1'),
          l AS (
            SELECT uf, cd_municipio, nr_zona, nr_local, any_value(nm_municipio) nm_municipio, mode(nm_local) nm_local,
                   mode(endereco) endereco, mode(bairro) bairro, mode(cep) cep, mode(lat) lat, mode(lon) lon,
                   sum(eleitores) eleitores, count(*) n_secoes
            FROM s GROUP BY ALL),
          n AS (SELECT *, {NORM.format(c='nm_local')} nm_norm, {NORM.format(c='endereco')} end_norm,
                       {NORM.format(c='bairro')} bairro_norm,
                       lat BETWEEN -34 AND 6 AND lon BETWEEN -74.5 AND -28.5 AND lat <> 0 coord_valida FROM l)
          SELECT {a} ano, *,
                 coord_valida AND count(DISTINCT nm_norm) OVER (PARTITION BY uf, cd_municipio, round(lat, 4), round(lon, 4)) < 3
                   coord_ok
          FROM n ORDER BY uf, cd_municipio, nr_zona, nr_local
        ) TO '{P}/locais_votacao_{a}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
        print(a, con.execute(f"""SELECT count(*), avg(coord_valida::INT), avg(coord_ok::INT)
                                 FROM '{P}/locais_votacao_{a}.parquet'""").fetchall(), flush=True)
    shutil.rmtree(f'{G}/csv', ignore_errors=True)


def casamento():
    for a in (2022, 2024):
        con.execute(f"""COPY (
          WITH n AS (SELECT * FROM '{P}/locais_votacao_2026.parquet'),
          o AS (SELECT * FROM '{P}/locais_votacao_{a}.parquet'),
          par AS (
            SELECT n.uf, n.cd_municipio, n.nr_zona, n.nr_local, o.nr_zona nr_zona_ant, o.nr_local nr_local_ant,
                   CASE WHEN n.coord_ok AND o.coord_ok THEN 2 * 6371000 * asin(sqrt(
                     pow(sin(radians(o.lat - n.lat) / 2), 2) +
                     cos(radians(n.lat)) * cos(radians(o.lat)) * pow(sin(radians(o.lon - n.lon) / 2), 2))) END dist_m,
                   jaro_winkler_similarity(n.nm_norm, o.nm_norm) sim_nome,
                   jaro_winkler_similarity(n.end_norm, o.end_norm) sim_end,
                   (n.bairro_norm = o.bairro_norm AND n.bairro_norm <> '') OR n.cep = o.cep mesma_area,
                   n.nr_zona = o.nr_zona AND n.nr_local = o.nr_local mesmo_id
            FROM n JOIN o USING (uf, cd_municipio)),
          niv AS (
            SELECT *, CASE
                WHEN dist_m <= 150 AND sim_nome >= 0.85 THEN 1
                WHEN dist_m <= 75 THEN 2
                WHEN sim_nome >= 0.93 AND (mesma_area OR sim_end >= 0.85 OR mesmo_id) THEN 3
                WHEN dist_m <= 400 THEN 4 END nivel
            FROM par)
          SELECT uf, cd_municipio, nr_zona, nr_local, nr_zona_ant, nr_local_ant, nivel,
                 ['geo_nome', 'geo', 'nome', 'geo_proximo'][nivel] metodo,
                 round(dist_m, 1) dist_m, round(sim_nome, 3) sim_nome, round(sim_end, 3) sim_end, mesmo_id
          FROM niv WHERE nivel IS NOT NULL
          QUALIFY row_number() OVER (PARTITION BY uf, cd_municipio, nr_zona, nr_local
                                     ORDER BY nivel, mesmo_id DESC, dist_m NULLS LAST, sim_nome DESC) = 1
          ORDER BY uf, cd_municipio, nr_zona, nr_local
        ) TO '{P}/match_locais_2026_{a}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
        print(f'2026x{a}', con.execute(f"""
          SELECT count(*) total, count(m.metodo) casados, round(sum(l.eleitores) FILTER (m.metodo IS NOT NULL) / sum(l.eleitores), 4) pct_eleitores,
                 histogram(m.metodo)
          FROM '{P}/locais_votacao_2026.parquet' l
          LEFT JOIN '{P}/match_locais_2026_{a}.parquet' m USING (uf, cd_municipio, nr_zona, nr_local)""").fetchall(), flush=True)


def historico():
    # Votos agregados por local em cada ano
    con.execute(f"""CREATE TEMP TABLE v26 AS
      SELECT uf, cd_municipio, nr_zona, nr_local, sum(t1_aptos) p26_t1_aptos, sum(t1_comparecimento) p26_t1_comparecimento,
             sum(t1_13) p26_t1_13, sum(t1_22) p26_t1_22, sum(t1_70) p26_t1_70, sum(t1_14) p26_t1_14, sum(t1_55) p26_t1_55,
             sum(t1_outros) p26_t1_outros, sum(t1_brancos) p26_t1_brancos, sum(t1_nulos) p26_t1_nulos,
             count(t2_status) FILTER (t2_status = 'Totalizada') p26_t2_secoes_apuradas, count(*) p26_secoes,
             sum(t2_13) p26_t2_13, sum(t2_22) p26_t2_22, sum(t2_brancos) p26_t2_brancos, sum(t2_nulos) p26_t2_nulos
      FROM '{P}/secao_t1_t2.parquet' GROUP BY ALL""")
    con.execute(f"""CREATE TEMP TABLE v22 AS
      SELECT uf, cd_municipio, nr_zona nr_zona_ant, nr_local nr_local_ant,
             sum(t1_aptos) p22_t1_aptos, sum(t1_comparecimento) p22_t1_comparecimento, sum(t1_13) p22_t1_13,
             sum(t1_22) p22_t1_22, sum(t1_15) p22_t1_15, sum(t1_12) p22_t1_12, sum(t1_outros) p22_t1_outros,
             sum(t1_brancos) p22_t1_brancos, sum(t1_nulos) p22_t1_nulos,
             sum(t2_aptos) p22_t2_aptos, sum(t2_comparecimento) p22_t2_comparecimento, sum(t2_13) p22_t2_13,
             sum(t2_22) p22_t2_22, sum(t2_brancos) p22_t2_brancos, sum(t2_nulos) p22_t2_nulos
      FROM '{P}/e2022_presidente_secao_wide.parquet' GROUP BY ALL""")
    con.execute(f"""CREATE TEMP TABLE e AS
      SELECT cargo, uf, cd_municipio, nr_zona nr_zona_ant, nr_local nr_local_ant, any_value(turno) turno,
             any_value(nm_urna) FILTER (cargo <> 'vereador') eleito, any_value(sg_partido) FILTER (cargo <> 'vereador') partido,
             sum(votos) votos_eleitos, sum(validos_secao) FILTER (cargo <> 'vereador') validos
      FROM '{P}/eleitos_votos_secao.parquet' GROUP BY ALL""")
    # validos de vereador: votos válidos por local (o eleitos_votos_secao repete o total da seção por eleito)
    con.execute(f"""CREATE TEMP TABLE vv24 AS
      SELECT uf, cd_municipio, nr_zona nr_zona_ant, nr_local nr_local_ant, sum(votos) FILTER (nr_votavel NOT IN (95, 96)) ver24_validos
      FROM '{P}/e2024_vereador_votos_secao.parquet' WHERE turno = 1 GROUP BY ALL""")
    con.execute(f"""COPY (
      WITH m22 AS (SELECT * FROM '{P}/match_locais_2026_2022.parquet'),
           m24 AS (SELECT * FROM '{P}/match_locais_2026_2024.parquet'),
           l22 AS (SELECT uf, cd_municipio, nr_zona nr_zona_ant, nr_local nr_local_ant, nm_local nm_local_2022, eleitores eleitores_2022
                   FROM '{P}/locais_votacao_2022.parquet'),
           l24 AS (SELECT uf, cd_municipio, nr_zona nr_zona_ant, nr_local nr_local_ant, nm_local nm_local_2024, eleitores eleitores_2024
                   FROM '{P}/locais_votacao_2024.parquet')
      SELECT l.uf, l.cd_municipio, l.nm_municipio, l.nr_zona, l.nr_local, l.nm_local, l.endereco, l.bairro, l.cep, l.lat, l.lon,
             l.coord_ok, l.eleitores eleitores_2026, l.n_secoes,
             -- 2022
             m22.metodo match22_metodo, m22.nivel match22_nivel, m22.dist_m match22_dist_m, m22.sim_nome match22_sim_nome,
             m22.nr_zona_ant nr_zona_2022, m22.nr_local_ant nr_local_2022, l22.nm_local_2022, l22.eleitores_2022,
             CASE WHEN m22.nr_local_ant IS NOT NULL THEN count(*) OVER (PARTITION BY l.uf, l.cd_municipio, m22.nr_zona_ant, m22.nr_local_ant) END
               match22_compartilhado,
             -- 2024
             m24.metodo match24_metodo, m24.nivel match24_nivel, m24.dist_m match24_dist_m, m24.sim_nome match24_sim_nome,
             m24.nr_zona_ant nr_zona_2024, m24.nr_local_ant nr_local_2024, l24.nm_local_2024, l24.eleitores_2024,
             CASE WHEN m24.nr_local_ant IS NOT NULL THEN count(*) OVER (PARTITION BY l.uf, l.cd_municipio, m24.nr_zona_ant, m24.nr_local_ant) END
               match24_compartilhado,
             v26.* EXCLUDE (uf, cd_municipio, nr_zona, nr_local),
             v22.* EXCLUDE (uf, cd_municipio, nr_zona_ant, nr_local_ant),
             g.turno gov22_turno, g.eleito gov22_eleito, g.partido gov22_partido, g.votos_eleitos gov22_votos_eleito, g.validos gov22_validos,
             p.turno pref24_turno, p.eleito pref24_eleito, p.partido pref24_partido, p.votos_eleitos pref24_votos_eleito, p.validos pref24_validos,
             vr.votos_eleitos ver24_votos_eleitos, vv24.ver24_validos
      FROM '{P}/locais_votacao_2026.parquet' l
      LEFT JOIN v26 USING (uf, cd_municipio, nr_zona, nr_local)
      LEFT JOIN m22 USING (uf, cd_municipio, nr_zona, nr_local)
      LEFT JOIN m24 USING (uf, cd_municipio, nr_zona, nr_local)
      LEFT JOIN l22 ON l22.uf = l.uf AND l22.cd_municipio = l.cd_municipio AND l22.nr_zona_ant = m22.nr_zona_ant AND l22.nr_local_ant = m22.nr_local_ant
      LEFT JOIN l24 ON l24.uf = l.uf AND l24.cd_municipio = l.cd_municipio AND l24.nr_zona_ant = m24.nr_zona_ant AND l24.nr_local_ant = m24.nr_local_ant
      LEFT JOIN v22 ON v22.uf = l.uf AND v22.cd_municipio = l.cd_municipio AND v22.nr_zona_ant = m22.nr_zona_ant AND v22.nr_local_ant = m22.nr_local_ant
      LEFT JOIN e g ON g.cargo = 'governador' AND g.uf = l.uf AND g.cd_municipio = l.cd_municipio AND g.nr_zona_ant = m22.nr_zona_ant AND g.nr_local_ant = m22.nr_local_ant
      LEFT JOIN e p ON p.cargo = 'prefeito' AND p.uf = l.uf AND p.cd_municipio = l.cd_municipio AND p.nr_zona_ant = m24.nr_zona_ant AND p.nr_local_ant = m24.nr_local_ant
      LEFT JOIN e vr ON vr.cargo = 'vereador' AND vr.uf = l.uf AND vr.cd_municipio = l.cd_municipio AND vr.nr_zona_ant = m24.nr_zona_ant AND vr.nr_local_ant = m24.nr_local_ant
      LEFT JOIN vv24 ON vv24.uf = l.uf AND vv24.cd_municipio = l.cd_municipio AND vv24.nr_zona_ant = m24.nr_zona_ant AND vv24.nr_local_ant = m24.nr_local_ant
      ORDER BY l.uf, l.cd_municipio, l.nr_zona, l.nr_local
    ) TO '{P}/local_2026_historico.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    print('local_2026_historico', con.execute(f"SELECT count(*) FROM '{P}/local_2026_historico.parquet'").fetchall(), flush=True)


def secoes():
    """Confiança do casamento seção a seção: mesma seção numérica, dentro do local casado e com eleitorado parecido."""
    con.execute(f"""COPY (
      WITH s26 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, nr_local, aptos FROM '{P}/t1_detalhe_secao.parquet'),
      s22 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, nr_local, t1_aptos aptos FROM '{P}/e2022_presidente_secao_wide.parquet'),
      s24 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, any_value(nr_local) nr_local, max(aptos) aptos
              FROM '{P}/e2024_detalhe_secao.parquet' WHERE turno = 1 GROUP BY ALL),
      m22 AS (SELECT * FROM '{P}/match_locais_2026_2022.parquet'),
      m24 AS (SELECT * FROM '{P}/match_locais_2026_2024.parquet')
      SELECT s26.uf, s26.cd_municipio, s26.nr_zona, s26.nr_secao, s26.nr_local, s26.aptos aptos_2026,
             m22.metodo local22_metodo, s22.aptos aptos_2022,
             CASE WHEN m22.metodo IS NULL THEN 'sem_local'
                  WHEN s22.nr_local IS NULL OR s22.nr_zona <> m22.nr_zona_ant OR s22.nr_local <> m22.nr_local_ant THEN 'so_local'
                  WHEN abs(s26.aptos - s22.aptos) <= 0.10 * greatest(s26.aptos, s22.aptos) THEN 'secao_alta'
                  ELSE 'secao_media' END confianca_2022,
             m24.metodo local24_metodo, s24.aptos aptos_2024,
             CASE WHEN m24.metodo IS NULL THEN 'sem_local'
                  WHEN s24.nr_local IS NULL OR s24.nr_zona <> m24.nr_zona_ant OR s24.nr_local <> m24.nr_local_ant THEN 'so_local'
                  WHEN abs(s26.aptos - s24.aptos) <= 0.10 * greatest(s26.aptos, s24.aptos) THEN 'secao_alta'
                  ELSE 'secao_media' END confianca_2024
      FROM s26
      LEFT JOIN m22 USING (uf, cd_municipio, nr_zona, nr_local)
      LEFT JOIN m24 USING (uf, cd_municipio, nr_zona, nr_local)
      LEFT JOIN s22 ON s22.uf = s26.uf AND s22.cd_municipio = s26.cd_municipio AND s22.nr_zona = s26.nr_zona AND s22.nr_secao = s26.nr_secao
      LEFT JOIN s24 ON s24.uf = s26.uf AND s24.cd_municipio = s26.cd_municipio AND s24.nr_zona = s26.nr_zona AND s24.nr_secao = s26.nr_secao
      ORDER BY uf, cd_municipio, nr_zona, nr_secao
    ) TO '{P}/secao_2026_confianca.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    print(con.sql(f"""SELECT 'x2022' ano, confianca_2022 conf, count(*) n FROM '{P}/secao_2026_confianca.parquet' GROUP BY ALL
                      UNION ALL SELECT 'x2024', confianca_2024, count(*) FROM '{P}/secao_2026_confianca.parquet' GROUP BY ALL
                      ORDER BY 1, 2"""))


if __name__ == '__main__':
    import sys
    for etapa in sys.argv[1:] or ['locais', 'casamento', 'historico', 'secoes']:
        globals()[etapa]()
