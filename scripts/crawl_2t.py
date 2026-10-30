"""Baixa os boletins de urna do 2º turno (presidente) de todas as seções no portal
resultados.tse.jus.br e grava um CSV por UF em dados/t2/secoes_<uf>.csv.
Retomável: seções já gravadas são puladas. Uso: crawl_2t.py [uf ...]"""
import asyncio, aiohttp, csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import ber

PLEITO, ELEICAO = 3221, 6258
BASE = f'https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{PLEITO}'
UFS = 'ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz'.split()
OUT = os.path.join(os.path.dirname(__file__), '..', 'dados', 't2')
CONC = 6
RATE = float(os.environ.get('RATE', 20))  # requisições/s máximas
_prox = 0.0

async def _ritmo():
    global _prox
    agora = time.monotonic()
    _prox = max(_prox + 1 / RATE, agora)
    if _prox > agora: await asyncio.sleep(_prox - agora)
COLS = ['uf', 'cd_municipio', 'nm_municipio', 'nr_zona', 'nr_secao', 'status', 'aptos',
        'comparecimento', 'secoes_agregadas', 'secao_principal', 'votos_13', 'votos_22', 'brancos', 'nulos', 'outros', 'erro']

def i(v): return int.from_bytes(v, 'big', signed=True)

def parse_bu(raw):
    env = ber.parse(raw)[0][2]
    conteudo = next(v for c, t, v in env if not isinstance(v, list) and len(v) > 200)
    bu = ber.parse(conteudo)[0][2]
    for c, t, v in bu:
        if not isinstance(v, list): continue
        for el in v:  # lista de ResultadoVotacaoPorEleicao
            if not isinstance(el[2], list) or len(el[2]) < 3: continue
            f = el[2]
            if f[0][1] != 2 or i(f[0][2]) != ELEICAO: continue
            r = dict(aptos=i(f[1][2]), comparecimento=None, votos_13=0, votos_22=0,
                     brancos=0, nulos=0, outros=0)
            for _, _, rv in f[4][2]:  # resultados por tipo de urna
                r['comparecimento'] = i(rv[1][2])
                for _, _, cargo in rv[2][2]:
                    for _, _, tv in cargo[2][2]:
                        d = {t: x for c, t, x in tv if c == 2}
                        tipo, qt = i(d[1]), i(d[2])
                        if tipo == 1:
                            cod = i(d[3][1][2])
                            k = f'votos_{cod}'
                            r[k if k in r else 'outros'] += qt
                        elif tipo == 2: r['brancos'] += qt
                        elif tipo == 3: r['nulos'] += qt
                        else: r['outros'] += qt
            return r
    raise ValueError('eleicao nao encontrada no BU')

async def get(s, url, binary=False):
    ult = None
    for tent in range(8):
        try:
            await _ritmo()
            async with s.get(url) as resp:
                if resp.status == 200:
                    return await (resp.read() if binary else resp.json(content_type=None))
                if resp.status == 404: return None
                ult = resp.status
                if resp.status == 429:
                    await asyncio.sleep(float(resp.headers.get('Retry-After') or 30))
        except Exception as e: ult = type(e).__name__
        await asyncio.sleep(1 + 2 * tent)
    raise RuntimeError(f'{ult} {url}')

async def secao(s, sem, uf, mu, nm, z, sec, info):
    row = dict(uf=uf.upper(), cd_municipio=mu, nm_municipio=nm, nr_zona=z, nr_secao=sec,
               secoes_agregadas=' '.join(info.get('nsa', [])))
    if 'nsp' in info:  # agregada: votos contados na urna da seção principal
        return {**row, 'status': 'agregada', 'secao_principal': info['nsp']}
    async with sem:
        try:
            d = f'{BASE}/dados/{uf}/{mu}/{z}/{sec}'
            aux = await get(s, f'{d}/p{PLEITO:06d}-{uf}-m{mu}-z{z}-s{sec}-aux.json')
            if not aux: return {**row, 'status': 'sem_aux'}
            row['status'] = aux.get('st')
            hs = [h for h in aux['hashes'] if any(a['tp'] == 'bu' for a in h['arq'])]
            if not hs: return row
            h = sorted(hs, key=lambda h: (h['dr'][6:]+h['dr'][3:5]+h['dr'][:2], h['hr']))[-1]
            nmbu = next(a['nm'] for a in h['arq'] if a['tp'] == 'bu')
            raw = await get(s, f"{d}/{h['hash']}/{nmbu}", binary=True)
            if raw: row.update(parse_bu(raw))
            else: row['erro'] = 'bu_404'
        except Exception as e:
            row['erro'] = repr(e)[:200]
        return row

async def run_uf(s, sem, uf):
    path = os.path.join(OUT, f'secoes_{uf}.csv')
    feitos = set()
    if os.path.exists(path):
        with open(path) as f:
            feitos = {(r['cd_municipio'], r['nr_zona'], r['nr_secao']) for r in csv.DictReader(f) if not r['erro']}
    cfg = await get(s, f'{BASE}/config/{uf}/{uf}-p{PLEITO:06d}-cs.json')
    if not cfg: raise RuntimeError(f'config {uf} indisponivel')
    tarefas = [(m['cd'], m['nm'], z['cd'], sc['ns'], sc) for m in cfg['abr'][0]['mu'] for z in m['zon'] for sc in z['sec']]
    pend = [t for t in tarefas if (t[0], t[2], t[3]) not in feitos]
    print(f'{uf}: {len(tarefas)} secoes, {len(pend)} pendentes', flush=True)
    # reescreve sem as linhas com erro
    rows_ok = []
    if os.path.exists(path):
        with open(path) as f: rows_ok = [r for r in csv.DictReader(f) if not r['erro']]
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows_ok)
        t0, n, errs = time.time(), 0, 0
        for fut in asyncio.as_completed([secao(s, sem, uf, *t) for t in pend]):
            r = await fut; w.writerow(r); n += 1; errs += bool(r.get('erro'))
            if n % 5000 == 0:
                f.flush(); print(f'  {uf} {n}/{len(pend)} ({n/(time.time()-t0):.0f}/s, erros={errs})', flush=True)
    print(f'{uf}: ok ({errs} erros)', flush=True)

async def main(ufs):
    os.makedirs(OUT, exist_ok=True)
    sem = asyncio.Semaphore(CONC)
    conn = aiohttp.TCPConnector(limit=CONC)
    async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=60),
                                     headers={'User-Agent': 'pesquisa-eleicoes/1.0'}) as s:
        for uf in ufs: await run_uf(s, sem, uf)

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:] or UFS))
