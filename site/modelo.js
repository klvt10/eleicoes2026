// Modelo de previsão dos votos em disputa (ganho de Lula e de Flávio) pelos outros cargos: estados e cidades, previsto × real.
'use strict';
const VERSAO = '20261029140908';
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtInt = new Intl.NumberFormat('pt-BR');
const fmtPct = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
const fmtPP = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero'});
const fmtSig = new Intl.NumberFormat('pt-BR', {signDisplay: 'exceptZero'});
const fmtCoef = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 3, maximumFractionDigits: 3, signDisplay: 'exceptZero'});
const num = (v) => (v == null ? NaN : +v);
const NOME_UF = Cards.NOME_UF;
const CELULAR = matchMedia('(max-width: 860px)').matches;
const MINIMOS = [0, 1000, 2000, 5000, 10000, 20000, 50000, 100000];
const PAD = {vis: 'estados', uf: '', min: '2000', n: '50', col: '', dir: '', busca: '', card: ''};
function lerEstado() {
  const p = new URLSearchParams(location.hash.slice(1)); const s = {...PAD};
  for (const k of Object.keys(PAD)) if (p.get(k) != null) s[k] = p.get(k);
  if (!['estados', 'cidades'].includes(s.vis)) s.vis = PAD.vis;
  return s;
}
let S = lerEstado();
function ir(novo) {
  const s = {...S, ...novo}; const p = new URLSearchParams();
  for (const k of Object.keys(PAD)) if (s[k] !== PAD[k] && s[k] !== '') p.set(k, s[k]);
  const h = '#' + p.toString();
  if (h === location.hash || (h === '#' && !location.hash)) { S = s; render(); } else location.hash = h;
}
window.addEventListener('hashchange', () => { S = lerEstado(); render(); });
const cache = new Map();
const get = (path) => { if (!cache.has(path)) cache.set(path, fetch(`${path}?v=${VERSAO}`).then((r) => { if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); })); return cache.get(path); };

function preencherSelect(s, ops, valor) {
  const assin = ops.map((o) => o[0]).join('|');
  if (s.dataset.assin !== assin) { s.replaceChildren(...ops.map(([v, t]) => new Option(t, v))); s.dataset.assin = assin; }
  s.value = valor;
}
function montaTabela(t, cols, rows, total, chaveOrd, asc, aoOrdenar, aoClicar, aoClicarTotal) {
  t.replaceChildren();
  const thead = el('thead'), tr = el('tr');
  cols.forEach((c) => {
    const th = el('th', c.k === chaveOrd ? 'ord' + (asc ? ' asc' : '') : '', c.t);
    if (c.dica) th.title = c.dica;
    th.onclick = () => aoOrdenar(c.k, c.k === chaveOrd ? (asc ? 'd' : 'a') : (c.txt ? 'a' : 'd'));
    tr.appendChild(th);
  });
  thead.appendChild(tr); t.appendChild(thead);
  const tbody = el('tbody');
  const linha = (r, cls) => {
    const trr = el('tr', cls);
    cols.forEach((c) => {
      const v = c.v(r);
      trr.appendChild(el('td', (c.txt ? 'txt ' : '') + (c.cls ? c.cls(v, r) : ''), c.txt ? (v ?? '—') : Number.isFinite(v) ? (c.fmt ? c.fmt(v) : fmtPct.format(v)) : '—'));
    });
    return trr;
  };
  rows.forEach((r) => { const trr = linha(r); if (aoClicar) { trr.onclick = () => aoClicar(r); trr.style.cursor = 'pointer'; } tbody.appendChild(trr); });
  t.appendChild(tbody);
  if (total) { const tf = el('tfoot'); const trr = linha(total, 'total'); if (aoClicarTotal) { trr.onclick = aoClicarTotal; trr.style.cursor = 'pointer'; } tf.appendChild(trr); t.appendChild(tf); }
}
function ordena(rows, col, asc) {
  return [...rows].sort((a, b) => {
    const x = col.v(a), y = col.v(b);
    if (col.txt) return asc ? String(x).localeCompare(String(y), 'pt-BR') : String(y).localeCompare(String(x), 'pt-BR');
    if (!Number.isFinite(x)) return 1; if (!Number.isFinite(y)) return -1;
    return asc ? x - y : y - x;
  });
}
const sinal = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const COLS = (nomeCol) => [
  {k: 'nome', t: nomeCol, v: (r) => r.nomeT, txt: true},
  {k: 'liq', t: 'Votos líquidos', v: (r) => num(r.liq), fmt: (v) => fmtInt.format(v), dica: 'Outros candidatos + queda de brancos/nulos + queda da abstenção = ganho de Lula + ganho de Flávio'},
  {k: 'real_l', t: 'Lula real', v: (r) => num(r.real_l), fmt: (v) => fmtPct.format(v) + '%', dica: 'Ganho de Lula ÷ votos líquidos; onde os líquidos são negativos, ÷ entradas'},
  {k: 'prev_l', t: 'Lula previsto', v: (r) => num(r.prev_l), fmt: (v) => fmtPct.format(v) + '%'},
  {k: 'dif_l', t: 'Dif. Lula (p.p.)', v: (r) => num(r.dif_l), fmt: (v) => fmtPP.format(v), cls: (v) => sinal(v)},
  {k: 'dif_gl', t: 'Dif. Lula (votos)', v: (r) => num(r.dif_gl), fmt: (v) => fmtSig.format(v), cls: (v) => sinal(v)},
  {k: 'real_f', t: 'Flávio real', v: (r) => num(r.real_f), fmt: (v) => fmtPct.format(v) + '%'},
  {k: 'prev_f', t: 'Flávio previsto', v: (r) => num(r.prev_f), fmt: (v) => fmtPct.format(v) + '%'},
  {k: 'dif_f', t: 'Dif. Flávio (p.p.)', v: (r) => num(r.dif_f), fmt: (v) => fmtPP.format(v), cls: (v) => (v > 0 ? 'neg' : v < 0 ? 'pos' : '')},
  {k: 'dif_gf', t: 'Dif. Flávio (votos)', v: (r) => num(r.dif_gf), fmt: (v) => fmtSig.format(v), cls: (v) => (v > 0 ? 'neg' : v < 0 ? 'pos' : '')},
  {k: 'saldo', t: 'Saldo real − previsto', v: (r) => (num(r.gl) - num(r.gf)) - (num(r.prev_gl) - num(r.prev_gf)), fmt: (v) => fmtSig.format(v), cls: (v) => sinal(v), dica: '(ganho de Lula − ganho de Flávio) real menos o previsto, em votos'},
];

let D = null;
async function render() {
  if (!D) {
    const [ufsArr, cids, modelo, cm] = await Promise.all([get('dados/comparativo/uf.json'), get('dados/comparativo/cidades.json'), get('dados/comparativo/modelo.json'), get('dados/comparativo/cidades_modelo.json')]);
    D = {ufsArr, ufs: new Map(ufsArr.map((u) => [u.uf, u])), cids, cidMap: new Map(cids.map((c) => [`${c.uf}-${c.cd}`, c])), modelo, cm, cmMap: new Map(cm.map((r) => [`${r.uf}-${r.cd}`, r]))};
  }
  const {ufsArr, ufs, cids, cidMap, modelo, cm, cmMap} = D;
  ['estados', 'cidades'].forEach((v) => { $('vis-' + v).setAttribute('aria-pressed', String(S.vis === v)); $('sec-' + v).hidden = S.vis !== v; });
  $('filtros').hidden = S.vis === 'estados';
  preencherSelect($('sel-uf'), [['', 'Brasil'], ...Object.keys(NOME_UF).map((u) => [u, `${u} · ${NOME_UF[u]}`])], S.uf);
  preencherSelect($('sel-min'), MINIMOS.map((v) => [String(v), v ? `${fmtInt.format(v)} votos líquidos` : 'qualquer tamanho']), S.min);
  preencherSelect($('sel-n'), [['25', '25 de cada ponta'], ['50', '50 de cada ponta'], ['100', '100 de cada ponta'], ['0', 'todas']], S.n);
  $('busca').value = S.busca;

  // cartões e caixa do modelo
  Cards.setModelo(modelo);
  const br = modelo.brasil, c = $('cartoes'); c.replaceChildren();
  const x = br.x;
  [['Votos líquidos', fmtInt.format(br.liq), '', `outros candidatos ${fmtInt.format(x.outros1)} · brancos/nulos ${fmtSig.format(x.dbn)} · abstenção ${fmtSig.format(x.dabst)}`],
    ['Ganho de Lula', fmtSig.format(br.gl), 'pos', `${fmtPct.format(br.real_l)}% dos líquidos · previsto ${fmtPct.format(br.prev_l)}%`],
    ['Ganho de Flávio', fmtSig.format(br.gf), 'neg', `${fmtPct.format(br.real_f)}% · previsto ${fmtPct.format(br.prev_f)}%`],
    ['Real − previsto (Lula)', fmtSig.format(br.dif_gl), sinal(br.dif_gl), `${fmtPP.format(br.dif_l)} p.p. dos líquidos`],
    ['Perfil médio do Brasil', fmtPct.format(x.perfil) + '% Lula', '', `presidente 1º t. ${fmtPct.format(x.pres)}% · outros cargos ${fmtPct.format(x.outros)}%`],
  ].forEach(([k, v, cl, s2]) => { const d = el('div', 'cartao'); d.append(el('span', 'k', k), el('span', 'v ' + cl, v)); if (s2) d.appendChild(el('span', 's', s2)); c.appendChild(d); });
  const mb = $('modelo-box'); mb.replaceChildren();
  const tx = el('div', 'texto');
  tx.appendChild(el('p', null, 'O modelo usa só o 1º turno de 2026 e responde: dado como cada lugar votou para presidente e para os outros cargos, para onde os votos que entraram em disputa no 2º turno iriam? Depois compara com o que aconteceu. Nada do resultado do 2º turno entra, exceto o total de votos líquidos de cada cidade (o tamanho, não a direção).'));
  const ol = el('ol');
  [['Votos líquidos de cada cidade', ' = votos dos outros candidatos no 1º turno + queda de brancos e nulos + queda da abstenção (mais a variação dos aptos). É exatamente o ganho de Lula mais o ganho de Flávio entre os turnos. Entradas são as parcelas positivas (eliminados; brancos e nulos, abstenção e aptos a menos); saídas são as negativas (abstenção ou brancos e nulos a mais, que tiram votos dos dois).'],
    ['Perfil da cidade', `: a proporção em que ela votou no 1º turno, em % Lula. Presidente: Lula ÷ (Lula + Flávio). Governador e senador: campo Lula ÷ (campo Lula + campo Flávio), com o campo dado pela coligação (PT = campo Lula, PL = campo Flávio). Deputado federal e estadual: esquerda ÷ (esquerda + direita), com o bloco dado pelo partido. Nada vira 0 ou 100: a Bahia entra como 70/30 na presidencial e 56/44 no governo. Perfil = ${Math.round(100 * modelo.peso_pres)}% da presidencial + ${Math.round(100 * (1 - modelo.peso_pres))}% da média dos outros cargos.`],
    ['Previsão', ': ganho de Lula = perfil × entradas + proporção presidencial do 1º turno × saídas; ganho de Flávio = o resto. A previsão de um estado é a soma das cidades.'],
    ['Comparação', ': real − previsto, em votos e em pontos dos votos líquidos. Positivo para Lula = o lugar deu a Lula mais do que o seu próprio perfil no 1º turno sugeria. Onde a abstenção subiu mais do que entraram votos (Acre, Amapá, Roraima e 176 cidades), os votos líquidos são negativos e as porcentagens usam as entradas como base.'],
  ].forEach(([b2, t]) => { const li = el('li'); li.append(el('b', null, b2), document.createTextNode(t)); ol.appendChild(li); });
  tx.appendChild(ol);
  mb.appendChild(tx);
  const tc = el('table', 'coef'), th = el('thead'), h = el('tr');
  ['Brasil (média das cidades, ponderada pelos votos líquidos)', '% Lula'].forEach((t) => h.appendChild(el('th', null, t))); th.appendChild(h); tc.appendChild(th);
  const tb = el('tbody');
  [['Presidente, 1º turno', x.pres], ['Governador', x.gov], ['Senador', x.sen], ['Deputado federal', x.dfed], ['Deputado estadual', x.dest], ['Média dos outros cargos', x.outros], ['Perfil', x.perfil]].forEach(([k, v]) => {
    const tr = el('tr'); tr.append(el('td', null, k), el('td', null, fmtPct.format(v) + '%')); tb.appendChild(tr);
  });
  const trE = el('tr'); trE.append(el('td', null, 'Entradas / saídas (votos)'), el('td', null, `${fmtInt.format(x.entradas)} / ${fmtInt.format(x.saidas)}`)); tb.appendChild(trE);
  tc.appendChild(tb); const rol = el('div', 'pres-rol'); rol.appendChild(tc); mb.appendChild(rol);
  mb.appendChild(el('p', 'larga', `Resultado nacional: previsto ${fmtInt.format(br.prev_gl)} para Lula (${fmtPct.format(br.prev_l)}%) e ${fmtInt.format(br.prev_gf)} para Flávio dos ${fmtInt.format(br.liq)} votos líquidos; real ${fmtInt.format(br.gl)} (${fmtPct.format(br.real_l)}%) e ${fmtInt.format(br.gf)}. Diferença de ${fmtSig.format(br.dif_gl)} votos para Lula, ${fmtPP.format(br.dif_l)} pontos dos votos líquidos. O peso da presidencial e os critérios de campo e bloco estão em modelo_site.py.`));

  if (S.vis === 'estados') {
    const rows = Object.entries(modelo.ufs).map(([uf, m]) => ({...m, uf, nomeT: CELULAR ? uf : `${NOME_UF[uf]} (${uf})`}));
    const cols = COLS('Estado');
    const col = cols.find((x) => x.k === S.col) ?? cols.find((x) => x.k === 'saldo');
    const asc = S.dir ? S.dir === 'a' : !!col.txt;
    montaTabela($('tab-estados'), cols, ordena(rows, col, asc), {...br, nomeT: 'Brasil'}, col.k, asc, (k, d) => ir({col: k, dir: d}), (r) => ir({card: r.uf}), () => ir({card: 'BR'}));
    $('nota-estados').textContent = 'Previsto = soma das previsões das cidades do estado, em votos. Diferença = real − previsto. Vermelho = a favor de Lula, azul = a favor de Flávio. Estados onde os votos líquidos ficaram negativos (um candidato perdeu votos) não têm percentuais. Clique num estado, ou no total, para abrir o card com a presidencial detalhada, os votos líquidos, o modelo e os outros cargos.';
  } else {
    const minV = +S.min || 0, n = +S.n || 0, q = (S.busca || '').trim().toLowerCase();
    let base = cm.filter((r) => (!S.uf || r.uf === S.uf) && Math.abs(r.liq) >= minV);
    if (q) base = base.filter((r) => r.nome.toLowerCase().includes(q));
    base = base.map((r) => ({...r, nomeT: `${r.nome} (${r.uf})`}));
    const cols = COLS('Cidade');
    const col = cols.find((x) => x.k === S.col) ?? cols.find((x) => x.k === 'saldo');
    const asc = S.dir ? S.dir === 'a' : !!col.txt;
    let rows = ordena(base, col, asc);
    if (n && rows.length > 2 * n && !q) rows = [...rows.slice(0, n), ...rows.slice(-n)];
    const tot = S.uf ? {...modelo.ufs[S.uf], nomeT: `${NOME_UF[S.uf]} (todo o estado)`} : {...br, nomeT: 'Brasil'};
    montaTabela($('tab-cidades'), cols, rows, tot, col.k, asc, (k, d) => ir({col: k, dir: d}), (r) => ir({card: `${r.uf}-${r.cd}`}), () => ir({card: S.uf || 'BR'}));
    $('tit-cidades').textContent = S.uf ? `Cidades de ${NOME_UF[S.uf]}: previsto × real` : 'Cidades do Brasil: previsto × real';
    $('nota-cidades').textContent = `${fmtInt.format(base.length)} cidades${minV ? ` com ${fmtInt.format(minV)} votos líquidos ou mais` : ''}${n && base.length > 2 * n && !q ? `; mostrando as ${n} de maior e as ${n} de menor valor na coluna ordenada` : ''}. ` +
      'Cidades pequenas variam mais por acaso; use o mínimo para comparar só as maiores. Clique numa cidade para abrir o card.';
  }

  // card
  if (S.card) {
    if (S.card.includes('-')) {
      const [uf, cd] = S.card.split('-');
      const c = cidMap.get(S.card);
      if (c) {
        const det = await get(`dados/comparativo/detalhe/${uf}.json`);
        const d = det.cidades[cd];
        if (d) Cards.cidade(c, d, det.nomes, cmMap.get(S.card) || null, [['Ver as cidades do estado', () => ir({vis: 'cidades', uf, card: ''})], ['Ver no mapa', () => { location.href = `index.html#uf=${uf}&cd=${cd}`; }]]);
      }
    } else {
      const u = ufs.get(S.card);
      if (u) Cards.estado(u, S.card === 'BR' ? br : modelo.ufs[S.card], S.card === 'BR' ? [] : [['Ver as cidades', () => ir({vis: 'cidades', uf: S.card, card: ''})]]);
    }
  } else if ($('card-uf').open) $('card-uf').close();
}
$('card-uf').addEventListener('close', () => { if (lerEstado().card) ir({card: ''}); });
$('card-uf').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });
['estados', 'cidades'].forEach((v) => { $('vis-' + v).onclick = () => ir({vis: v}); });
$('sel-uf').onchange = (e) => ir({uf: e.target.value});
$('sel-min').onchange = (e) => ir({min: e.target.value});
$('sel-n').onchange = (e) => ir({n: e.target.value});
let tBusca = null;
$('busca').oninput = (e) => { clearTimeout(tBusca); tBusca = setTimeout(() => ir({busca: e.target.value}), 250); };
$('abrir-metodo').onclick = () => $('metodo').showModal();
render().catch((err) => { $('cartoes').textContent = 'Não foi possível carregar os dados: ' + err.message; });
