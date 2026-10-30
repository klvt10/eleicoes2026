"""Gera Parquets dos dois turnos (presidente) a partir dos arquivos oficiais do TSE (dados/oficial_v2)."""
import duckdb, os
D = os.path.join(os.path.dirname(__file__), '..', 'dados')
con = duckdb.connect()
opts = "delim=';', header=true, encoding='latin-1', all_varchar=true"
for t in (1, 2):
    con.execute(f"""COPY (
      SELECT SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, NM_MUNICIPIO nm_municipio,
             CAST(NR_ZONA AS INT) nr_zona, CAST(NR_SECAO AS INT) nr_secao,
             CAST(NR_LOCAL_VOTACAO AS INT) nr_local, NM_LOCAL_VOTACAO nm_local,
             CAST(NR_VOTAVEL AS INT) nr_votavel, NM_VOTAVEL nm_votavel, CAST(QT_VOTOS AS INT) votos
      FROM read_csv('{D}/oficial_v2/votacao_secao_2026_BR.csv', {opts})
      WHERE CD_CARGO = '1' AND NR_TURNO = '{t}'
    ) TO '{D}/parquet/t{t}_votos_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (
      SELECT SG_UF uf, CAST(CD_MUNICIPIO AS INT) cd_municipio, NM_MUNICIPIO nm_municipio,
             CAST(NR_ZONA AS INT) nr_zona, CAST(NR_SECAO AS INT) nr_secao,
             CAST(NR_LOCAL_VOTACAO AS INT) nr_local, NM_LOCAL_VOTACAO nm_local, DS_LOCAL_VOTACAO_ENDERECO endereco,
             CAST(QT_APTOS AS INT) aptos, CAST(QT_COMPARECIMENTO AS INT) comparecimento,
             CAST(QT_ABSTENCOES AS INT) abstencoes, CAST(QT_VOTOS_NOMINAIS AS INT) nominais,
             CAST(QT_VOTOS_BRANCOS AS INT) brancos, CAST(QT_VOTOS_NULOS AS INT) nulos,
             DS_ORIGEM_VOTO origem_voto, ST_SECAO_INSTALADA instalada, ST_SECAO_ANULADA anulada,
             DS_MODELO_URNA modelo_urna,
             strptime(DT_RECEBIMENTO_BU_HOR_TSE, '%d/%m/%Y %H:%M:%S') recebimento_bu
      FROM read_csv('{D}/oficial_v2/detalhe_votacao_secao_2026_BR.csv', {opts})
      WHERE CD_CARGO = '1' AND NR_TURNO = '{t}'
    ) TO '{D}/parquet/t{t}_detalhe_secao.parquet' (FORMAT parquet, COMPRESSION zstd)""")
for t in (1, 2):
    print(f'--- {t}º turno')
    print(con.sql(f"""SELECT count(*) secoes, sum(aptos) aptos, sum(comparecimento) comp,
        round(100*sum(abstencoes)/sum(aptos),2) pct_abst, sum(brancos) brancos, sum(nulos) nulos
        FROM '{D}/parquet/t{t}_detalhe_secao.parquet'"""))
    print(con.sql(f"""SELECT nr_votavel, any_value(nm_votavel) nome, sum(votos) votos,
        round(100*sum(votos)/(SELECT sum(votos) FROM '{D}/parquet/t{t}_votos_secao.parquet' WHERE nr_votavel<95),2) pct_validos
        FROM '{D}/parquet/t{t}_votos_secao.parquet' WHERE nr_votavel<95 GROUP BY 1 ORDER BY 3 DESC LIMIT 6"""))
