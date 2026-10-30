"""Converte os arquivos oficiais do TSE de 2022 (presidente/governador) e 2024 (prefeito/vereador)
em Parquet no mesmo padrão de dados/parquet (zstd, colunas snake_case, chave uf+cd_municipio+nr_zona+nr_secao).

Entrada: dados/2022/raw e dados/2024/raw (baixados por scripts/download_2022_2024.sh).
Uso: python scripts/build_2022_2024.py
"""
import duckdb, glob, os, shutil, subprocess, sys

D = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dados'))
P = f'{D}/parquet'
TMP = f'{D}/_staging'
OPTS = "delim=';', header=true, encoding='latin-1', all_varchar=true, quote='\"'"
CARGOS = {2022: (1, 3), 2024: (11, 13)}
NOME = {1: 'presidente', 3: 'governador', 11: 'prefeito', 13: 'vereador'}
con = duckdb.connect()
con.execute("SET preserve_insertion_order=false")


def unzip(zf, pattern='*.csv'):
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    subprocess.run(['unzip', '-q', '-o', zf, pattern, '-d', TMP], check=True)
    return sorted(glob.glob(f'{TMP}/*.csv'))


VOTOS_SQL = """
  SELECT CAST(ANO_ELEICAO AS SMALLINT) ano, CAST(NR_TURNO AS TINYINT) turno, CAST(CD_ELEICAO AS INT) cd_eleicao,
         CAST(CD_CARGO AS TINYINT) cd_cargo, SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, NM_MUNICIPIO nm_municipio,
         CAST(NR_ZONA AS INT) nr_zona, CAST(NR_SECAO AS INT) nr_secao,
         CAST(NR_LOCAL_VOTACAO AS INT) nr_local, NM_LOCAL_VOTACAO nm_local,
         CAST(NR_VOTAVEL AS INT) nr_votavel, NM_VOTAVEL nm_votavel, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq_candidato,
         CAST(QT_VOTOS AS INT) votos
  FROM read_csv('{csv}', {opts})
  WHERE CD_CARGO IN ({cargos}) AND CD_TIPO_ELEICAO = '2'"""


def votos_secao():
    """Votos por seção × votável, um Parquet por (ano, cargo). Processa UF a UF."""
    parts = f'{TMP}_parts'
    shutil.rmtree(parts, ignore_errors=True)
    os.makedirs(parts)
    jobs = [(2022, z, '1') for z in [f'{D}/2022/raw/votacao_secao_2022_BR.zip']]
    jobs += [(2022, z, '3') for z in sorted(glob.glob(f'{D}/2022/raw/votacao_secao_2022_[A-Z][A-Z].zip'))]
    jobs += [(2024, z, '11,13') for z in sorted(glob.glob(f'{D}/2024/raw/votacao_secao_2024_[A-Z][A-Z].zip'))]
    for i, (ano, zf, cargos) in enumerate(jobs):
        for csv in unzip(zf):
            tag = os.path.basename(csv)[:-4]
            print(f'[{i+1}/{len(jobs)}] {tag} cargos {cargos}', flush=True)
            con.execute(f"COPY ({VOTOS_SQL.format(csv=csv, opts=OPTS, cargos=cargos)}) "
                        f"TO '{parts}/{tag}_{cargos.replace(',', '-')}.parquet' (FORMAT parquet, COMPRESSION zstd)")
    shutil.rmtree(TMP, ignore_errors=True)
    for ano, cargos in CARGOS.items():
        for c in cargos:
            out = f'{P}/e{ano}_{NOME[c]}_votos_secao.parquet'
            con.execute(f"""COPY (SELECT * EXCLUDE (ano, cd_cargo) FROM read_parquet('{parts}/*_{ano}_*.parquet')
                            WHERE cd_cargo = {c} ORDER BY uf, cd_municipio, nr_zona, nr_secao, turno, nr_votavel)
                            TO '{out}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 1000000)""")
            print(out, con.execute(f"SELECT count(*) FROM '{out}'").fetchall()[0][0], 'linhas', flush=True)
    shutil.rmtree(parts, ignore_errors=True)


def detalhe_secao():
    """Aptos/comparecimento/brancos/nulos por seção, cargo e turno."""
    for ano, cargos in CARGOS.items():
        csvs = [c for c in unzip(f'{D}/{ano}/raw/detalhe_votacao_secao_{ano}.zip') if 'BRASIL' not in c]
        lst = '[' + ','.join(f"'{c}'" for c in csvs) + ']'
        out = f'{P}/e{ano}_detalhe_secao.parquet'
        con.execute(f"""COPY (
          SELECT CAST(NR_TURNO AS TINYINT) turno, CAST(CD_CARGO AS TINYINT) cd_cargo, DS_CARGO ds_cargo,
                 SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, NM_MUNICIPIO nm_municipio,
                 CAST(NR_ZONA AS INT) nr_zona, CAST(NR_SECAO AS INT) nr_secao,
                 CAST(NR_LOCAL_VOTACAO AS INT) nr_local, NM_LOCAL_VOTACAO nm_local, DS_LOCAL_VOTACAO_ENDERECO endereco,
                 CAST(QT_APTOS AS INT) aptos, CAST(QT_COMPARECIMENTO AS INT) comparecimento,
                 CAST(QT_ABSTENCOES AS INT) abstencoes, CAST(QT_VOTOS_NOMINAIS AS INT) nominais,
                 CAST(QT_VOTOS_BRANCOS AS INT) brancos, CAST(QT_VOTOS_NULOS AS INT) nulos,
                 CAST(QT_VOTOS_LEGENDA AS INT) legenda, CAST(QT_VOTOS_ANULADOS_APU_SEP AS INT) anulados_apu_sep,
                 DS_ORIGEM_VOTO origem_voto, ST_SECAO_INSTALADA instalada, ST_SECAO_ANULADA anulada,
                 DS_MODELO_URNA modelo_urna,
                 try_strptime(DT_RECEBIMENTO_BU_HOR_TSE, '%d/%m/%Y %H:%M:%S') recebimento_bu
          FROM read_csv({lst}, {OPTS}, union_by_name=true)
          WHERE CD_CARGO IN ({','.join(map(str, cargos))}) AND CD_TIPO_ELEICAO = '2'
          ORDER BY uf, cd_municipio, nr_zona, nr_secao, cd_cargo, turno
        ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
        print(out, con.execute(f"SELECT count(*) FROM '{out}'").fetchall()[0][0], 'linhas', flush=True)
    shutil.rmtree(TMP, ignore_errors=True)


def candidatos():
    """Cadastro de candidatos (sem CPF/e-mail/título) com situação de totalização por turno."""
    for ano, cargos in CARGOS.items():
        csvs = unzip(f'{D}/{ano}/raw/consulta_cand_{ano}.zip')
        lst = '[' + ','.join(f"'{c}'" for c in csvs) + ']'
        out = f'{P}/e{ano}_candidatos.parquet'
        con.execute(f"""COPY (
          SELECT DISTINCT CAST(NR_TURNO AS TINYINT) turno, CAST(CD_CARGO AS TINYINT) cd_cargo, DS_CARGO ds_cargo,
                 SG_UF uf, SG_UE sg_ue, NM_UE nm_ue,
                 -- SG_UE municipal = código TSE do município com zeros à esquerda
                 CASE WHEN CD_CARGO IN ('11','13') THEN TRY_CAST(SG_UE AS INT) END cd_municipio,
                 CAST(SQ_CANDIDATO AS BIGINT) sq_candidato, CAST(NR_CANDIDATO AS INT) nr_candidato,
                 NM_CANDIDATO nm_candidato, NM_URNA_CANDIDATO nm_urna,
                 CAST(NR_PARTIDO AS INT) nr_partido, SG_PARTIDO sg_partido, NM_PARTIDO nm_partido,
                 NULLIF(SG_FEDERACAO, '#NULO') sg_federacao, NM_COLIGACAO nm_coligacao,
                 DS_COMPOSICAO_COLIGACAO composicao_coligacao,
                 DS_SITUACAO_CANDIDATURA situacao_candidatura,
                 DS_GENERO genero, DS_GRAU_INSTRUCAO grau_instrucao, DS_COR_RACA cor_raca, DS_OCUPACAO ocupacao,
                 try_strptime(DT_NASCIMENTO, '%d/%m/%Y')::DATE dt_nascimento,
                 CAST(CD_SIT_TOT_TURNO AS SMALLINT) cd_sit_tot_turno, DS_SIT_TOT_TURNO ds_sit_tot_turno,
                 DS_SIT_TOT_TURNO LIKE 'ELEITO%' eleito
          FROM read_csv({lst}, {OPTS}, union_by_name=true)
          WHERE CD_CARGO IN ({','.join(map(str, cargos))}) AND CD_TIPO_ELEICAO = '2'
          ORDER BY uf, cd_municipio, cd_cargo, nr_candidato, turno
        ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
        print(out, con.execute(f"SELECT count(*) FROM '{out}'").fetchall()[0][0], 'linhas', flush=True)
    shutil.rmtree(TMP, ignore_errors=True)


def derivados():
    # Presidente 2022 em formato largo: 1 linha por seção, T1 e T2 lado a lado
    con.execute(f"""COPY (
      WITH v AS (
        SELECT uf, cd_municipio, nr_zona, nr_secao,
          sum(votos) FILTER (turno=1 AND nr_votavel=13) t1_13, sum(votos) FILTER (turno=1 AND nr_votavel=22) t1_22,
          sum(votos) FILTER (turno=1 AND nr_votavel=15) t1_15, sum(votos) FILTER (turno=1 AND nr_votavel=12) t1_12,
          sum(votos) FILTER (turno=1 AND nr_votavel NOT IN (13,22,15,12,95,96)) t1_outros,
          sum(votos) FILTER (turno=1 AND nr_votavel=95) t1_brancos, sum(votos) FILTER (turno=1 AND nr_votavel=96) t1_nulos,
          sum(votos) FILTER (turno=2 AND nr_votavel=13) t2_13, sum(votos) FILTER (turno=2 AND nr_votavel=22) t2_22,
          sum(votos) FILTER (turno=2 AND nr_votavel=95) t2_brancos, sum(votos) FILTER (turno=2 AND nr_votavel=96) t2_nulos
        FROM '{P}/e2022_presidente_votos_secao.parquet' GROUP BY ALL),
      d AS (
        SELECT uf, cd_municipio, nr_zona, nr_secao, any_value(nm_municipio) nm_municipio, any_value(nr_local) nr_local,
          any_value(nm_local) nm_local, any_value(endereco) endereco, any_value(modelo_urna) modelo_urna,
          max(aptos) FILTER (turno=1) t1_aptos, max(comparecimento) FILTER (turno=1) t1_comparecimento,
          max(aptos) FILTER (turno=2) t2_aptos, max(comparecimento) FILTER (turno=2) t2_comparecimento
        FROM '{P}/e2022_detalhe_secao.parquet' WHERE cd_cargo=1 GROUP BY ALL)
      SELECT d.uf, d.cd_municipio, d.nm_municipio, d.nr_zona, d.nr_secao, d.nr_local, d.nm_local, d.endereco, d.modelo_urna,
             d.t1_aptos, d.t1_comparecimento, COALESCE(t1_13,0)::INT t1_13, COALESCE(t1_22,0)::INT t1_22, COALESCE(t1_15,0)::INT t1_15,
             COALESCE(t1_12,0)::INT t1_12, COALESCE(t1_outros,0)::INT t1_outros, COALESCE(t1_brancos,0)::INT t1_brancos,
             COALESCE(t1_nulos,0)::INT t1_nulos,
             d.t2_aptos, d.t2_comparecimento, COALESCE(t2_13,0)::INT t2_13, COALESCE(t2_22,0)::INT t2_22,
             COALESCE(t2_brancos,0)::INT t2_brancos, COALESCE(t2_nulos,0)::INT t2_nulos
      FROM d LEFT JOIN v USING (uf, cd_municipio, nr_zona, nr_secao)
      ORDER BY uf, cd_municipio, nr_zona, nr_secao
    ) TO '{P}/e2022_presidente_secao_wide.parquet' (FORMAT parquet, COMPRESSION zstd)""")

    # Lista de eleitos (governador 2022, prefeito e vereador 2024) com votos totais.
    # Situação final = linha de maior turno de cada candidato.
    con.execute(f"""COPY (
      WITH c AS (
        SELECT 2022 ano, * FROM '{P}/e2022_candidatos.parquet' WHERE cd_cargo = 3
        UNION ALL BY NAME SELECT 2024 ano, * FROM '{P}/e2024_candidatos.parquet'),
      fin AS (SELECT * FROM c QUALIFY row_number() OVER (PARTITION BY ano, sq_candidato ORDER BY turno DESC) = 1),
      v AS (
        SELECT 2022 ano, turno, sq_candidato, sum(votos) votos FROM '{P}/e2022_governador_votos_secao.parquet' GROUP BY ALL
        UNION ALL SELECT 2024, turno, sq_candidato, sum(votos) FROM '{P}/e2024_prefeito_votos_secao.parquet' GROUP BY ALL
        UNION ALL SELECT 2024, turno, sq_candidato, sum(votos) FROM '{P}/e2024_vereador_votos_secao.parquet' GROUP BY ALL)
      SELECT fin.ano, lower(fin.ds_cargo) cargo, fin.uf, fin.cd_municipio, fin.nm_ue, fin.turno turno_final,
             fin.sq_candidato, fin.nr_candidato, fin.nm_candidato, fin.nm_urna, fin.sg_partido, fin.sg_federacao,
             fin.nm_coligacao, fin.ds_sit_tot_turno, fin.genero, fin.cor_raca, fin.grau_instrucao, fin.ocupacao,
             fin.dt_nascimento,
             (SELECT sum(votos) FROM v WHERE v.ano=fin.ano AND v.sq_candidato=fin.sq_candidato AND v.turno=1) votos_t1,
             (SELECT sum(votos) FROM v WHERE v.ano=fin.ano AND v.sq_candidato=fin.sq_candidato AND v.turno=2) votos_t2
      FROM fin WHERE fin.eleito
      ORDER BY ano, uf, cd_municipio, cargo, votos_t1 DESC
    ) TO '{P}/eleitos_gov2022_pref_ver2024.parquet' (FORMAT parquet, COMPRESSION zstd)""")

    # Votos de cada eleito em cada seção (turno decisivo para governador/prefeito), com o total válido
    # do cargo na seção para calcular participação.
    con.execute(f"""COPY (
      WITH e AS (SELECT * FROM '{P}/eleitos_gov2022_pref_ver2024.parquet'),
      v AS (
        SELECT 2022 ano, 'governador' cargo, * FROM '{P}/e2022_governador_votos_secao.parquet'
        UNION ALL BY NAME SELECT 2024 ano, 'prefeito' cargo, * FROM '{P}/e2024_prefeito_votos_secao.parquet'
        UNION ALL BY NAME SELECT 2024 ano, 'vereador' cargo, * FROM '{P}/e2024_vereador_votos_secao.parquet'),
      tot AS (SELECT ano, cargo, turno, uf, cd_municipio, nr_zona, nr_secao, sum(votos)::INT validos_secao
              FROM v WHERE nr_votavel NOT IN (95, 96) GROUP BY ALL)
      SELECT v.ano, v.cargo, v.turno, v.uf, v.cd_municipio, v.nm_municipio, v.nr_zona, v.nr_secao, v.nr_local, v.nm_local,
             e.sq_candidato, e.nr_candidato, e.nm_urna, e.sg_partido, v.votos, tot.validos_secao
      FROM v JOIN e ON v.ano=e.ano AND v.sq_candidato=e.sq_candidato AND v.turno=e.turno_final
      JOIN tot ON tot.ano=v.ano AND tot.cargo=v.cargo AND tot.turno=v.turno AND tot.uf=v.uf AND tot.cd_municipio=v.cd_municipio
               AND tot.nr_zona=v.nr_zona AND tot.nr_secao=v.nr_secao
      ORDER BY v.ano, v.uf, v.cd_municipio, v.nr_zona, v.nr_secao, v.cargo
    ) TO '{P}/eleitos_votos_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")

    # Ponte com as seções de 2026: mesma chave uf+município+zona+seção. Seções são reorganizadas
    # entre eleições, então a coluna match_* indica se a seção existia na eleição anterior.
    con.execute(f"""COPY (
      WITH s26 AS (SELECT uf, cd_municipio, nm_municipio, nr_zona, nr_secao, nr_local nr_local_2026
                   FROM '{P}/t1_detalhe_secao.parquet'),
      p22 AS (SELECT * FROM '{P}/e2022_presidente_secao_wide.parquet'),
      g22 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, turno gov22_turno, nm_urna gov22_eleito, sg_partido gov22_partido,
                     votos gov22_votos_eleito, validos_secao gov22_validos
              FROM '{P}/eleitos_votos_secao.parquet' WHERE cargo='governador'),
      pf24 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, turno pref24_turno, nm_urna pref24_eleito, sg_partido pref24_partido,
                      votos pref24_votos_eleito, validos_secao pref24_validos
               FROM '{P}/eleitos_votos_secao.parquet' WHERE cargo='prefeito'),
      vr24 AS (SELECT uf, cd_municipio, nr_zona, nr_secao, sum(votos)::INT ver24_votos_eleitos, any_value(validos_secao) ver24_validos,
                      arg_max(nm_urna, votos) ver24_mais_votado_secao, max(votos) ver24_mais_votado_votos
               FROM '{P}/eleitos_votos_secao.parquet' WHERE cargo='vereador' GROUP BY ALL),
      s24 AS (SELECT DISTINCT uf, cd_municipio, nr_zona, nr_secao, nr_local nr_local_2024
              FROM '{P}/e2024_detalhe_secao.parquet' WHERE turno=1)
      SELECT s26.*, p22.nr_local IS NOT NULL match_2022, p22.nr_local nr_local_2022, s24.nr_local_2024 IS NOT NULL match_2024,
             s24.nr_local_2024,
             p22.t1_aptos p22_t1_aptos, p22.t1_comparecimento p22_t1_comparecimento, p22.t1_13 p22_t1_13, p22.t1_22 p22_t1_22,
             p22.t1_15 p22_t1_15, p22.t1_12 p22_t1_12, p22.t1_outros p22_t1_outros, p22.t1_brancos p22_t1_brancos,
             p22.t1_nulos p22_t1_nulos, p22.t2_aptos p22_t2_aptos, p22.t2_comparecimento p22_t2_comparecimento,
             p22.t2_13 p22_t2_13, p22.t2_22 p22_t2_22, p22.t2_brancos p22_t2_brancos, p22.t2_nulos p22_t2_nulos,
             g22.* EXCLUDE (uf, cd_municipio, nr_zona, nr_secao), pf24.* EXCLUDE (uf, cd_municipio, nr_zona, nr_secao),
             vr24.* EXCLUDE (uf, cd_municipio, nr_zona, nr_secao)
      FROM s26
      LEFT JOIN p22 USING (uf, cd_municipio, nr_zona, nr_secao)
      LEFT JOIN g22 USING (uf, cd_municipio, nr_zona, nr_secao)
      LEFT JOIN s24 USING (uf, cd_municipio, nr_zona, nr_secao)
      LEFT JOIN pf24 USING (uf, cd_municipio, nr_zona, nr_secao)
      LEFT JOIN vr24 USING (uf, cd_municipio, nr_zona, nr_secao)
      ORDER BY uf, cd_municipio, nr_zona, nr_secao
    ) TO '{P}/secao_2026_historico.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    for f in ['e2022_presidente_secao_wide', 'eleitos_gov2022_pref_ver2024', 'eleitos_votos_secao', 'secao_2026_historico']:
        print(f, con.execute(f"SELECT count(*) FROM '{P}/{f}.parquet'").fetchall()[0][0], 'linhas', flush=True)


if __name__ == '__main__':
    etapas = sys.argv[1:] or ['candidatos', 'detalhe_secao', 'votos_secao', 'derivados']
    for e in etapas:
        globals()[e]()
