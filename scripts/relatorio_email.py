"""Relatório em HTML (para e-mail: estilos inline, só tabelas) da transferência de votos de 2026 no contexto de 2006-2022.

Junta: dados/historicos/sistemica.json (transferencia_sistemica.py), dados/historicos/ei_uf.json (inferência por UF),
site/dados/anomalias.json (anomalias.py) e as abstenções oficiais por turno.
Saída: relatorios/relatorio_transferencias_2026.html
"""
import os, json

R = os.path.join(os.path.dirname(__file__), '..')
S = json.load(open(f'{R}/dados/historicos/sistemica.json'))
EIUF = json.load(open(f'{R}/dados/historicos/ei_uf.json'))
A = json.load(open(f'{R}/site/dados/anomalias.json'))
os.makedirs(f'{R}/relatorios', exist_ok=True)
H, EI, TOT = S['historico'], S['ei'], S['totais_secoes']
# abstenção (% do eleitorado) no 1º e no 2º turno, Brasil sem exterior (TSE, detalhe_votacao_munzona e arquivos por seção)
ABST = {2006: (16.73, 18.97), 2010: (18.07, 21.44), 2014: (19.29, 21.01), 2018: (20.19, 21.17), 2022: (20.79, 20.43), 2026: (20.84, 18.99)}

n = lambda v: f'{v:,.0f}'.replace(',', '.')
s = lambda v: ('+' if v > 0 else '') + n(v)
p = lambda v, d=1: f'{100 * v:.{d}f}%'.replace('.', ',')
f = lambda v, d=1: f'{v:.{d}f}'.replace('.', ',')
VERM, AZUL, CINZA, FUNDO, LINHA = '#c62828', '#1f5fbf', '#6b6b66', '#f7f7f5', '#e3e2dd'
TD = f'padding:6px 8px;border-bottom:1px solid {LINHA};text-align:right;font-size:13px;'
TH = f'padding:6px 8px;border-bottom:2px solid {LINHA};text-align:right;font-size:12px;color:{CINZA};'


def tabela(cab, linhas, primeira_esq=True, destaque=None):
    h = '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;margin:8px 0 14px;">'
    h += '<tr>' + ''.join(f'<th style="{TH}{"text-align:left;" if i == 0 and primeira_esq else ""}">{c}</th>' for i, c in enumerate(cab)) + '</tr>'
    for j, l in enumerate(linhas):
        bg = 'background:#fff3e0;' if destaque is not None and j == destaque else ''
        h += '<tr>' + ''.join(f'<td style="{TD}{bg}{"text-align:left;" if i == 0 and primeira_esq else ""}">{c}</td>' for i, c in enumerate(l)) + '</tr>'
    return h + '</table>'


def barra(v, cor, mx=1.0):
    w = max(0, min(100, 100 * v / mx))
    return f'<div style="background:{LINHA};height:8px;border-radius:4px;width:120px;display:inline-block;vertical-align:middle;"><div style="background:{cor};height:8px;border-radius:4px;width:{w:.0f}%;"></div></div>'


sec = lambda t: f'<h2 style="font-size:19px;margin:28px 0 8px;border-top:1px solid {LINHA};padding-top:18px;">{t}</h2>'
par = lambda t: f'<p style="margin:0 0 10px;font-size:15px;line-height:1.55;">{t}</p>'
caixa = lambda t, cor='#b26b00': f'<div style="border-left:4px solid {cor};background:{FUNDO};padding:10px 14px;margin:10px 0 14px;font-size:14px;line-height:1.5;">{t}</div>'

h26, h22, h06 = H['2026'], H['2022'], H['2006']
e26, e22 = EI['2026'], EI['2022']
t26 = TOT['2026']
contrib = lambda fonte, alvo: e26[alvo][fonte][0] * t26[fonte]
fontes26 = [('cury', 'Augusto Cury (Avante)'), ('renan', 'Renan Santos (Missão)'), ('caiado', 'Ronaldo Caiado (PSD)'), ('zema', 'Romeu Zema (Novo)'),
            ('peq', 'Demais candidatos'), ('bn1', 'Brancos e nulos do 1º turno'), ('abst1', 'Abstenções do 1º turno')]
ufs_bn_flavio_zero = sum(1 for u, r in EIUF['2026'].items() if r['bn1_f'] < 0.1)
ufs_bn_bolso_25 = sum(1 for u, r in EIUF['2022'].items() if r['bn1_f'] >= 0.25)
m = A['meta']

html = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transferência de votos no 2º turno de 2026: o que é normal e o que não é</title></head>
<body style="margin:0;padding:0;background:{FUNDO};font-family:Arial,Helvetica,sans-serif;color:#1c1c1a;">
<div style="max-width:780px;margin:0 auto;background:#ffffff;padding:28px 26px 36px;">
<p style="margin:0;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:{CINZA};font-weight:bold;">Relatório · eleição presidencial 2026</p>
<h1 style="font-size:26px;line-height:1.2;margin:6px 0 12px;">Transferência de votos no 2º turno: o que é normal e o que não é</h1>
{par(f'Em 2026, Lula venceu a transferência de votos entre os turnos (ganhou mais votos que Flávio do 1º para o 2º turno) em <b>{p(h26["pct_mun_pt"])} dos municípios</b> e em <b>100% dos municípios de 10 unidades da federação</b>: cinco que ele venceu (CE, PB, PE, RN, SE) e cinco que Flávio venceu (DF, ES, MS, RJ, RR). Este relatório pergunta se isso é estatisticamente anormal, comparando com todos os segundos turnos presidenciais desde 2006 e decompondo de onde vieram os votos.')}
{caixa('<b>Anomalia estatística não é prova de fraude.</b> Os números de 2026 usados aqui batem voto a voto com a totalização oficial do TSE em todos os estados (58 de 58 comparações) e os de 2006-2018 com os totais nacionais oficiais. O que este relatório faz é separar o que tem precedente do que não tem.')}

{sec('Resumo')}
<ol style="margin:0 0 6px;padding-left:20px;font-size:15px;line-height:1.55;">
<li style="margin-bottom:8px;"><b>A uniformidade não é anormal por si só.</b> Em 2006, Lula venceu a transferência em {p(h06["pct_mun_pt"])} dos municípios e em 100% dos municípios de {len(h06["ufs_100"])} estados, quatro deles vencidos por Alckmin (MS, MT, PR, RR). Em 2022 foi Bolsonaro quem venceu a transferência em {p(h22["pct_mun_vencedor_transf"])} dos municípios, com 100% em {len(h22["ufs_100"])} estados. Quando há uma maré nacional, ela aparece em quase todo lugar.</li>
<li style="margin-bottom:8px;"><b>A dispersão entre municípios é a mesma de 2022.</b> O desvio-padrão do saldo por município é {f(100 * h26["dp_s"])} pontos em 2026 e {f(100 * h22["dp_s"])} em 2022 (dentro de cada estado: {f(100 * h26["dp_dentro_uf"])} e {f(100 * h22["dp_dentro_uf"])}). Um modelo de “maré uniforme” (média e desvio de cada estado) prevê o % de municípios vencidos por estado com erro médio de {f(100 * h26["erro_medio_modelo_normal"])} ponto percentual em 2026, o mesmo nível de 2006 e 2022. Não há uniformidade excessiva.</li>
<li style="margin-bottom:8px;"><b>O que é inédito é o tamanho e a origem da virada.</b> É a primeira vez desde 2006 que o líder do 1º turno perde o 2º, e a abstenção caiu {f(ABST[2026][0] - ABST[2026][1], 2)} ponto percentual entre os turnos, a maior queda da série (em 2006, 2010, 2014 e 2018 ela subiu).</li>
<li style="margin-bottom:8px;"><b>A anomalia sistêmica mais forte está nos brancos e nulos do 1º turno.</b> Pela inferência ecológica nas {n(S["n_secoes"]["2026"])} seções, cerca de {p(e26["l2"]["bn1"][0], 0)} de quem votou branco ou nulo no 1º turno de 2026 votou em Lula no 2º e só {p(e26["f2"]["bn1"][0], 0)} em Flávio. Em 2022, pelo mesmo método, eram {p(e22["l2"]["bn1"][0], 0)} para Lula e {p(e22["b2"]["bn1"][0], 0)} para Bolsonaro. E o padrão de 2026 se repete em praticamente todos os estados, inclusive no Sul: em {ufs_bn_flavio_zero} das 27 UFs, menos de 10% desses eleitores teriam ido para Flávio. Em 2022, em {ufs_bn_bolso_25} UFs, um quarto ou mais tinha ido para Bolsonaro.</li>
<li style="margin-bottom:8px;"><b>Os eleitores de candidatos de direita também se dividiram de forma surpreendente.</b> Pela mesma estimativa, os eleitores de Renan Santos (Missão, de perfil anti-PT) teriam ido {p(e26["l2"]["renan"][0], 0)} para Lula e {p(e26["f2"]["renan"][0], 0)} para Flávio; os de Augusto Cury, {p(e26["l2"]["cury"][0], 0)} e {p(e26["f2"]["cury"][0], 0)}. Os de Caiado ({p(e26["f2"]["caiado"][0], 0)} Flávio) e de Zema ({p(e26["f2"]["zema"][0], 0)} Flávio) se comportaram como o esperado.</li>
</ol>

{sec('1. A pergunta: é normal vencer a transferência em quase todos os municípios?')}
{par('Saldo de um município = (ganho do candidato do PT − ganho do adversário) ÷ votos em disputa, em que votos em disputa = outros candidatos + brancos e nulos + abstenções do 1º turno. Quem tem saldo positivo “venceu a transferência” ali. A tabela mostra cada 2º turno presidencial desde 2006, sem o exterior.')}
{tabela(['Ano', 'PT × adversário', 'Venceu o 2º turno', 'Venceu a transferência', '% dos municípios', 'UFs com 100%', 'Dessas, vencidas pelo outro no 2º turno'],
        [[a, f'{h["pt"]} × {h["adv"]}', h['vencedor_2t'], h['vencedor_transferencia'], p(h['pct_mun_vencedor_transf']), f'{len(h["ufs_100"])} ({", ".join(h["ufs_100"])})', ', '.join(h['ufs_100_venc2t_outro']) or '—']
         for a, h in H.items()], destaque=5)}
{par(f'Em 2006, Alckmin <i>perdeu</i> {n(-h06["ganho_adv"])} votos entre os turnos e Lula venceu a transferência em {p(h06["pct_mun_pt"])} dos municípios, mais que os {p(h26["pct_mun_pt"])} de 2026. Estados em que todos os municípios foram para o vencedor da transferência, inclusive estados vencidos pelo adversário, também aconteceram em 2006. Na contagem estrita, só entram estados com mais de um município, o que tira o DF: são 9 estados em 2026 e, com o DF, as 10 unidades da federação.')}

{sec('2. Por que uma maré nacional produz 100% em vários estados')}
{par('Se o saldo dos municípios de um estado se distribui em torno de uma média m com desvio-padrão d, a fração esperada de municípios com saldo positivo é Φ(m/d) (distribuição normal). Quando a média está a 3 desvios ou mais do zero, Φ passa de 99,8% e é natural que todos os municípios fiquem do mesmo lado. É o que se vê nos estados com 100%:')}
{tabela(['UF', 'Municípios', 'Saldo médio', 'Desvio-padrão', 'Média em desvios', '% observado', '% previsto pela maré uniforme'],
        [[r['uf'], r['n'], p(r['m']), p(r['sd']), f(r['m'] / r['sd']) if r['sd'] else '—', p(r['obs']), p(r['normal']) if r['normal'] == r['normal'] else '—']
         for r in sorted(S['por_uf']['2026'], key=lambda r: -r['obs']) if r['n'] > 1])}
{par(f'Erro médio entre o observado e o previsto: {f(100 * h26["erro_medio_modelo_normal"])} p.p. em 2026, contra {f(100 * h22["erro_medio_modelo_normal"])} em 2022 e {f(100 * h06["erro_medio_modelo_normal"])} em 2006. Se os municípios estivessem “uniformes demais” (o que poderia indicar um padrão artificial), o desvio-padrão dentro dos estados seria menor que o histórico. Ele é {f(100 * h26["dp_dentro_uf"])} p.p. em 2026 e {f(100 * h22["dp_dentro_uf"])} p.p. em 2022. Os municípios que mais transferiram para Lula em 2026 são, em boa parte, os que menos transferiram para Bolsonaro em 2022 (correlação de {f(S["correlacao"]["2022-2026"]["pearson"], 2)}, a maior entre eleições consecutivas da série): a geografia é a mesma, só o nível mudou.')}

{sec('3. O que tem pouco ou nenhum precedente em 2026')}
{tabela(['Ano', 'Líder do 1º turno venceu?', 'PT no 1º turno', 'Adversário no 1º turno', 'Abstenção 1º → 2º turno', 'Saldo nacional ÷ em disputa'],
        [[a, 'não' if (h['pt1'] > h['adv1']) != (h['vencedor_2t'] == h['pt']) else 'sim', p(h['pt1']), p(h['adv1']), f'{f(ABST[int(a)][0], 2)}% → {f(ABST[int(a)][1], 2)}%', p(h['saldo_nacional_D'])]
         for a, h in H.items()], destaque=5)}
{par('Percentuais do 1º turno sobre o comparecimento. Três coisas destacam 2026: (a) é o único 2º turno da série em que quem liderou o 1º turno perdeu; (b) é a maior queda de abstenção entre os turnos, com 2,9 milhões de eleitores a mais votando no 2º turno; (c) o saldo a favor de um candidato só é maior em 2006, quando o adversário perdeu votos.')}

{sec('4. De onde vieram os votos de Lula (inferência ecológica)')}
{par(f'Para estimar para onde foi cada grupo de eleitores do 1º turno, usamos a regressão de Goodman nas {n(S["n_secoes"]["2026"])} seções: a votação de Lula, Flávio, brancos e nulos e abstenção no 2º turno de cada seção é explicada pela composição dessa seção no 1º turno, com taxas entre 0 e 1, estimadas dentro de cada estado e somadas pelo peso de cada grupo. Os erros-padrão vêm de 50 reamostragens de municípios. O mesmo método aplicado a 2022 dá resultados plausíveis: 97% dos eleitores de Lula e 100% dos de Bolsonaro repetem o voto, e os de Ciro e Tebet se dividem.')}
{tabela(['Grupo no 1º turno de 2026', 'Votos', '→ Lula', '→ Flávio', '→ branco/nulo', 'Votos estimados para Lula', 'Votos estimados para Flávio'],
        [[nome, n(t26[k]), p(e26['l2'][k][0], 0) + f' <span style="color:{CINZA}">±{f(100 * e26["l2"][k][1], 0)}</span>', p(e26['f2'][k][0], 0) + f' <span style="color:{CINZA}">±{f(100 * e26["f2"][k][1], 0)}</span>',
          p(e26['bn2'][k][0], 0), s(contrib(k, 'l2')), s(contrib(k, 'f2'))] for k, nome in fontes26])}
{par(f'Somando as linhas, e descontando os poucos eleitores de Lula ({p(1 - e26["l2"]["l1"][0])}) e de Flávio ({p(1 - e26["f2"]["f1"][0])}) do 1º turno que não repetiram o voto, a estimativa reproduz os ganhos reais: Lula +{n(h26["ganho_pt"])} e Flávio +{n(h26["ganho_adv"])}. As duas maiores fontes do ganho de Lula são os <b>brancos e nulos do 1º turno</b> (cerca de {n(contrib("bn1", "l2"))} votos) e quem <b>se absteve no 1º turno e votou no 2º</b> (cerca de {n(contrib("abst1", "l2"))}). Juntas, explicam mais da metade da virada.')}
{par('Comparação com 2022, pelo mesmo método:')}
{tabela(['Grupo no 1º turno', '2022 → PT', '2022 → adversário', '2026 → PT', '2026 → adversário'],
        [['Brancos e nulos', p(e22['l2']['bn1'][0], 0), p(e22['b2']['bn1'][0], 0), p(e26['l2']['bn1'][0], 0), p(e26['f2']['bn1'][0], 0)],
         ['Abstenção (quem não votou no 1º)', p(e22['l2']['abst1'][0], 1), p(e22['b2']['abst1'][0], 1), p(e26['l2']['abst1'][0], 1), p(e26['f2']['abst1'][0], 1)],
         ['Terceiro e quarto colocados', f'Ciro {p(e22["l2"]["ciro"][0], 0)} · Tebet {p(e22["l2"]["tebet"][0], 0)}', f'Ciro {p(e22["b2"]["ciro"][0], 0)} · Tebet {p(e22["b2"]["tebet"][0], 0)}',
          f'Cury {p(e26["l2"]["cury"][0], 0)} · Renan {p(e26["l2"]["renan"][0], 0)}', f'Cury {p(e26["f2"]["cury"][0], 0)} · Renan {p(e26["f2"]["renan"][0], 0)}']])}

{sec('5. A anomalia dos brancos e nulos, estado por estado')}
{par(f'Se a ida dos brancos e nulos para Lula fosse fruto de um perfil regional (por exemplo, o Nordeste), ela não apareceria nos estados onde Bolsonaro absorveu esses eleitores em 2022. Mas aparece: em 2026 a parcela que vai para Flávio fica perto de zero em {ufs_bn_flavio_zero} das 27 UFs.')}
{tabela(['UF', 'Brancos e nulos no 1º turno de 2026', '2022 → PT', '2022 → Bolsonaro', '2026 → Lula', '2026 → Flávio'],
        [[u, n(EIUF['2026'][u]['bn1_votos']), p(EIUF['2022'][u]['bn1_l'], 0), p(EIUF['2022'][u]['bn1_f'], 0), p(EIUF['2026'][u]['bn1_l'], 0), p(EIUF['2026'][u]['bn1_f'], 0)]
         for u in sorted(EIUF['2026'], key=lambda u: -EIUF['2026'][u]['bn1_votos'])])}
{caixa(f'<b>Leitura.</b> Esta é a mudança de comportamento mais difícil de explicar com o histórico. Explicações possíveis, que os dados de votação sozinhos não distinguem: (1) parte dos eleitores de Lula anulou ou votou em branco no 1º turno por algum motivo específico de 2026 e voltou no 2º; (2) uma campanha pelo voto em Lula entre eleitores que rejeitavam os dois no 1º turno; (3) viés da inferência ecológica (seções com mais brancos e nulos podem ser seções que, por outros motivos, viraram mais para Lula). Para separar as hipóteses seria preciso cruzar com pesquisas de opinião sobre o voto do 1º para o 2º turno e com a auditoria dos boletins de urna das seções com maior queda de brancos e nulos.', VERM)}

{sec('6. Anomalias por município (complemento)')}
{par(f'O relatório por município (aba “Anomalias” do site) responde outra pergunta: quais cidades fugiram do padrão de 2026, dado o próprio histórico. Ele não enxerga um movimento nacional, porque o modelo é treinado com os dados do próprio ano. Resultados: {m["n_q01"]} municípios com q < 1%; as {m["controle_positivo"]["n"]} cidades com eleição suplementar para prefeito no mesmo dia aparecem todas entre as {m["controle_positivo"]["ranks"][-1]} primeiras (validação do método). Casos mais fortes:')}
{tabela(['#', 'Município', 'O que aconteceu', 'Lula 1º → 2º', 'Flávio 1º → 2º'],
        [[r['rank'], f'{r["nome"].title()} ({r["uf"]})', r['tipo'] + (' · eleição suplementar no dia' if r['sup_mesmo_dia'] else ''), f'{n(r["lv1"])} → {n(r["lv1"] + r["gl"])}', f'{n(r["fv1"])} → {n(r["fv1"] + r["gf"])}'] for r in A['top'][:12]])}

{sec('Método e limites')}
{par('<b>Fontes:</b> TSE, votação por município e zona de 2006, 2010, 2014 e 2018 (votacao_candidato_munzona e detalhe_votacao_munzona) e arquivos de votação por seção de 2022 e 2026. Os totais nacionais conferem com o resultado oficial (ex.: Lula 2006, 46.662.365 e 58.295.042 votos; Bolsonaro 2018, 57.797.847 no 2º turno). O exterior fica de fora.')}
{par('<b>Maré uniforme:</b> para cada estado, Φ(média ÷ desvio-padrão do saldo dos municípios). É um modelo simples e assume distribuição aproximadamente normal. A curtose dos desvios em 2026 (8,8) é alta, mas parecida com a de 2022 (8,0): poucas cidades muito fora do padrão, não uma distribuição achatada ou artificial.')}
{par('<b>Inferência ecológica:</b> a regressão de Goodman supõe que, dentro de um estado, as taxas de transferência não dependem da composição da seção. Quando isso falha, as taxas ficam enviesadas, e esse é o limite clássico do método. Por isso o comparamos com 2022, com o mesmo método, e mostramos estado por estado. As taxas são limitadas entre 0 e 1 e as somas por grupo ficam perto de 100%, um bom sinal de consistência; nos grupos pequenos (Zema e demais candidatos) a soma se afasta de 100% e a estimativa é imprecisa.')}
{par('<b>O que não fizemos:</b> não há dado individual de voto (o voto é secreto); a confirmação de qualquer hipótese depende de pesquisas de opinião e da auditoria dos boletins de urna.')}
<p style="margin:24px 0 0;font-size:12px;color:{CINZA};">Gerado a partir dos dados públicos do TSE · scripts transferencia_sistemica.py, anomalias.py e relatorio_email.py · site: <a href="https://transferencias-2turno-2026.netlify.app" style="color:{AZUL};">transferencias-2turno-2026.netlify.app</a></p>
</div></body></html>'''
open(f'{R}/relatorios/relatorio_transferencias_2026.html', 'w').write(html)
print(len(html), 'bytes')
