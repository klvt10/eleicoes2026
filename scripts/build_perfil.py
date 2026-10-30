"""Perfil do eleitorado por seção (TSE) 2022/2024/2026 -> Parquet.

Saídas:
  dados/parquet/perfil/ano=<a>/uf=<uf>.parquet  formato longo, uma linha por combinação de perfil
  dados/parquet/perfil_secao.parquet            resumo largo, uma linha por (ano, seção)
"""
import os, sys, zipfile, tempfile, duckdb

D = os.path.join(os.path.dirname(__file__), '..', 'dados')
RAW = f'{D}/perfil/raw'
OUT = f'{D}/parquet/perfil'
opts = "delim=';', header=true, encoding='latin-1', all_varchar=true, quote='\"'"

con = duckdb.connect()
con.execute("SET memory_limit='6GB'; SET threads=8")
tmp = tempfile.mkdtemp(dir=os.environ.get('TMPDIR'))

for nome in sorted(os.listdir(RAW)):
    ano, uf = nome[:-4].split('_')[-2:]
    dst = f'{OUT}/ano={ano}/uf={uf}.parquet'
    if os.path.exists(dst):
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with zipfile.ZipFile(f'{RAW}/{nome}') as z:
        csv = [n for n in z.namelist() if n.endswith('.csv')][0]
        z.extract(csv, tmp)
    f = f'{tmp}/{csv}'
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_csv('{f}', {opts})").fetchall()]
    qt = 'QT_ELEITORES' if 'QT_ELEITORES' in cols else 'QT_ELEITORES_PERFIL'
    c = lambda nome: nome if nome in cols else 'NULL'  # layouts variam entre arquivos (ex.: 2022 DF sem raça/cor)
    con.execute(f"""
    COPY (
      SELECT {ano}::SMALLINT ano, SG_UF uf, CD_MUNICIPIO::INT cd_municipio, NM_MUNICIPIO nm_municipio,
             NR_ZONA::INT nr_zona, NR_SECAO::INT nr_secao, NR_LOCAL_VOTACAO::INT nr_local,
             CD_GENERO::SMALLINT cd_genero, DS_GENERO ds_genero,
             CD_ESTADO_CIVIL::SMALLINT cd_estado_civil, DS_ESTADO_CIVIL ds_estado_civil,
             CD_FAIXA_ETARIA::INT cd_faixa_etaria, trim(DS_FAIXA_ETARIA) ds_faixa_etaria,
             CD_GRAU_ESCOLARIDADE::SMALLINT cd_escolaridade, DS_GRAU_ESCOLARIDADE ds_escolaridade,
             {c('CD_RACA_COR')}::SMALLINT cd_raca_cor, {c('DS_RACA_COR')} ds_raca_cor,
             {c('TP_OBRIGATORIEDADE_VOTO')} tp_obrigatoriedade,
             {qt}::INT qt_eleitores, QT_ELEITORES_BIOMETRIA::INT qt_biometria,
             QT_ELEITORES_DEFICIENCIA::INT qt_deficiencia
      FROM read_csv('{f}', {opts})
    ) TO '{dst}' (FORMAT parquet, COMPRESSION zstd)""")
    os.remove(f)
    n = con.execute(f"SELECT count(*), sum(qt_eleitores) FROM '{dst}'").fetchone()
    print(ano, uf, n, flush=True)

# Resumo por seção. Faixa etária: código AABB = de AA a BB anos (1600 = 16 anos, 7900 = 79, 9999 = 100+).
con.execute(f"""
COPY (
  WITH p AS (
    SELECT *, CASE WHEN cd_faixa_etaria >= 9999 THEN 100
                   ELSE (cd_faixa_etaria // 100 + greatest(cd_faixa_etaria % 100, cd_faixa_etaria // 100)) / 2.0 END idade_meio
    FROM read_parquet('{OUT}/*/*.parquet', hive_partitioning=false)
  )
  SELECT ano, uf, cd_municipio, nr_zona, nr_secao, any_value(nr_local) nr_local,
    sum(qt_eleitores) eleitores,
    sum(qt_eleitores * (cd_genero = 4)::INT) / sum(qt_eleitores) p_mulher,
    sum(qt_eleitores * (cd_faixa_etaria BETWEEN 1600 AND 1799)::INT) / sum(qt_eleitores) p_16_17,
    sum(qt_eleitores * (cd_faixa_etaria BETWEEN 1800 AND 2999)::INT) / sum(qt_eleitores) p_18_29,
    sum(qt_eleitores * (cd_faixa_etaria >= 6000)::INT) / sum(qt_eleitores) p_60mais,
    sum(qt_eleitores * idade_meio) FILTER (cd_faixa_etaria > 0) / sum(qt_eleitores) FILTER (cd_faixa_etaria > 0) idade_media,
    sum(qt_eleitores * (cd_escolaridade IN (1, 2, 3))::INT) / sum(qt_eleitores) p_ate_fund_incompleto,
    sum(qt_eleitores * (cd_escolaridade = 8)::INT) / sum(qt_eleitores) p_superior,
    sum(qt_eleitores * (cd_raca_cor > 0)::INT) / sum(qt_eleitores) p_raca_informada,
    sum(qt_eleitores * (cd_raca_cor = 1)::INT) / nullif(sum(qt_eleitores * (cd_raca_cor > 0)::INT), 0) p_branca_entre_informados,
    sum(qt_biometria) / sum(qt_eleitores) p_biometria
  FROM p GROUP BY ALL
) TO '{D}/parquet/perfil_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")
print(con.execute(f"SELECT ano, count(*), sum(eleitores) FROM '{D}/parquet/perfil_secao.parquet' GROUP BY 1 ORDER BY 1").fetchall())
