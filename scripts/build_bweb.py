"""Gera Parquet por seção a partir dos Boletins de Urna Web (bweb) do TSE, 2º turno,
para 2026 e 2022: votos de presidente, hora de abertura/encerramento (local e Brasília)
e eleitores habilitados sem biometria."""
import duckdb, os, sys
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
con = duckdb.connect()
opts = "delim=';', header=true, encoding='latin-1', all_varchar=true, union_by_name=true"
# deslocamento do horário local da urna em relação a Brasília (outubro, sem horário de verão)
OFF = "CASE SG_UF WHEN 'AC' THEN 2 WHEN 'AM' THEN 1 WHEN 'RO' THEN 1 WHEN 'RR' THEN 1 WHEN 'MT' THEN 1 WHEN 'MS' THEN 1 WHEN 'ZZ' THEN NULL ELSE 0 END"
SO = sys.argv[1:]  # opcional: limitar a alguns conjuntos, ex. 2026_t1
for ano, glob, biom, fmt, agg in (
        ('2026_t1', 'bweb/2026_t1/csv/bweb_1t_*.csv', 'QT_ELEI_BIOM_SEM_HABILITACAO', '%Y-%m-%d %H:%M:%S', 'DS_SECOES_AGREGADAS'),
        (2026, 'bweb/2026/csv/bweb_2t_*.csv', 'QT_ELEI_BIOM_SEM_HABILITACAO', '%Y-%m-%d %H:%M:%S', 'DS_SECOES_AGREGADAS'),
        (2022, 'bweb/2022/csv/bweb_2t_*.csv', 'QT_ELEITORES_BIOMETRIA_NH', '%d/%m/%Y %H:%M:%S', 'DS_AGREGADAS')):
    if SO and str(ano) not in SO: continue
    con.execute(f"""COPY (
      SELECT '{ano}' ano, SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, any_value(NM_MUNICIPIO) nm_municipio,
             CAST(NR_ZONA AS INT) nr_zona, CAST(NR_SECAO AS INT) nr_secao,
             any_value(CAST(NR_LOCAL_VOTACAO AS INT)) nr_local,
             any_value(CAST(QT_APTOS AS INT)) aptos, any_value(CAST(QT_COMPARECIMENTO AS INT)) comparecimento,
             any_value(DS_TIPO_URNA) tipo_urna, any_value(NR_URNA_EFETIVADA) nr_urna,
             any_value({agg}) agregadas,
             any_value(strptime(DT_ABERTURA, '{fmt}')) abertura,
             any_value(strptime(DT_ENCERRAMENTO, '{fmt}')) encerramento,
             any_value(strptime(DT_ENCERRAMENTO, '{fmt}') + to_hours({OFF})) enc_bsb,
             any_value(strptime(DT_EMISSAO_BU, '{fmt}')) emissao_bu,
             any_value(strptime(DT_BU_RECEBIDO, '{fmt}')) bu_recebido,
             any_value(CAST({biom} AS INT)) biom_nh,
             COALESCE(sum(CAST(QT_VOTOS AS INT)) FILTER (NR_VOTAVEL='13'),0) v13,
             COALESCE(sum(CAST(QT_VOTOS AS INT)) FILTER (NR_VOTAVEL='22'),0) v22,
             COALESCE(sum(CAST(QT_VOTOS AS INT)) FILTER (NR_VOTAVEL='95'),0) brancos,
             COALESCE(sum(CAST(QT_VOTOS AS INT)) FILTER (NR_VOTAVEL='96'),0) nulos,
             sum(CAST(QT_VOTOS AS INT)) total_votos
      FROM read_csv('{D}/{glob}', {opts})
      WHERE CD_CARGO_PERGUNTA = '1'
      GROUP BY 1,2,3,5,6
    ) TO '{D}/parquet/bweb_{ano}{'' if 't1' in str(ano) else '_t2'}_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    print(con.sql(f"""SELECT count(*) secoes, sum(aptos) aptos, sum(comparecimento) comp, sum(v13) v13, sum(v22) v22,
        sum(biom_nh) biom_nh, round(100.0*sum(biom_nh)/sum(comparecimento),2) pct_biom_nh,
        min(enc_bsb) min_enc, max(enc_bsb) max_enc, count(*) FILTER (enc_bsb IS NULL) sem_hora
        FROM '{D}/parquet/bweb_{ano}{'' if 't1' in str(ano) else '_t2'}_secao.parquet'"""))
