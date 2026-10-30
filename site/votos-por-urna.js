// Votos por urna: urnas em que cada candidato a presidente teve até/pelo menos/exatamente N votos,
// o que o outro teve nelas e como as mesmas seções votaram no outro turno. Estado no endereço (#t=2026_t2&reg=NE&uf=BA&op=le&n=5).
'use strict';

const VERSAO = '20261029140908';
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtInt = new Intl.NumberFormat('pt-BR');
const fmtPct1 = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
const fmtPctUrna = (p) => (p >= 10 ? fmtPct1.format(p) : new Intl.NumberFormat('pt-BR', {maximumSignificantDigits: 2}).format(p)) + '%';
const NOME_UF = {AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás',
  MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná',
  RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins', ZZ: 'Exterior'};
const REGIOES = {BR: {nome: 'Brasil (e exterior)', ufs: Object.keys(NOME_UF)},
  N: {nome: 'Norte', ufs: ['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO']}, NE: {nome: 'Nordeste', ufs: ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE']},
  CO: {nome: 'Centro-Oeste', ufs: ['DF', 'GO', 'MS', 'MT']}, SE: {nome: 'Sudeste', ufs: ['ES', 'MG', 'RJ', 'SP']}, S: {nome: 'Sul', ufs: ['PR', 'RS', 'SC']}, ZZ: {nome: 'Exterior', ufs: ['ZZ']}};
const OPS = {le: {txt: 'até', ok: (k, n) => k <= n}, ge: {txt: 'pelo menos', ok: (k, n) => k >= n}, eq: {txt: 'exatamente', ok: (k, n) => k === n}};
const ATALHOS = [['le', 0, '0 votos'], ['le', 1, 'até 1'], ['le', 5, 'até 5'], ['le', 10, 'até 10'], ['le', 20, 'até 20'], ['ge', 300, '300 ou mais']];
const CELULAR = matchMedia('(max-width: 860px)').matches;
// índices das colunas no histograma e na lista (meta.cols_hist / meta.cols_urna)
const H = {k: 0, n: 1, outro: 2, comp: 3, aptos: 4, bn: 5, biom: 6, eu_cruz: 7, outro_cruz: 8, comp_cruz: 9, n_cruz: 10};
const U = {uf: 0, mun: 1, zona: 2, secao: 3, local: 4, agreg: 5, aptos: 6, comp: 7, v13: 8, v22: 9, bn: 10, biom: 11, c13: 12, c22: 13, ccomp: 14};

const PAD = {t: '2026_t2', reg: 'BR', uf: '', op: 'le', n: '0', col: '', dir: '', ucol: '', udir: '', ln: '50'};
function lerEstado() {
  const p = new URLSearchParams(location.hash.slice(1)); const s = {...PAD};
  for (const k of Object.keys(PAD)) if (p.get(k) != null) s[k] = p.get(k);
  if (!REGIOES[s.reg]) s.reg = 'BR'; if (!OPS[s.op]) s.op = 'le'; if (s.uf && !NOME_UF[s.uf]) s.uf = '';
  s.n = String(Math.max(0, Math.min(600, parseInt(s.n, 10) || 0)));
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
let tRes = null; window.addEventListener('resize', () => { clearTimeout(tRes); tRes = setTimeout(render, 150); });

const cache = new Map();
const get = (nome) => {
  if (window.__VPU__ && window.__VPU__[nome]) return Promise.resolve(window.__VPU__[nome]);
  if (!cache.has(nome)) cache.set(nome, fetch(`dados/votos_por_urna/${nome}.json?v=${VERSAO}`).then((r) => { if (!r.ok) throw new Error(`${nome}: HTTP ${r.status}`); return r.json(); }));
  return cache.get(nome);
};

function preencherSelect(s, ops, valor) {
  const assin = ops.map((o) => o[0]).join('|');
  if (s.dataset.assin !== assin) { s.replaceChildren(...ops.map(([v, t]) => new Option(t, v))); s.dataset.assin = assin; }
  s.value = valor;
}
const ufsSel = () => (S.uf ? [S.uf] : REGIOES[S.reg].ufs);
const nomeLugar = () => (S.uf ? NOME_UF[S.uf] : S.reg === 'BR' ? 'Brasil' : REGIOES[S.reg].nome);

// soma, para um candidato, as faixas do histograma que satisfazem a condição, nas UFs escolhidas
function somar(hist, cand, ufs, op, n) {
  const z = {n: 0, eu: 0, outro: 0, comp: 0, aptos: 0, bn: 0, biom: 0, eu_cruz: 0, outro_cruz: 0, comp_cruz: 0, n_cruz: 0, tot: 0, maxk: 0};
  const ok = OPS[op].ok;
  for (const uf of ufs) for (const b of hist[cand][uf] || []) {
    z.tot += b[H.n]; if (b[H.k] > z.maxk) z.maxk = b[H.k];
    if (!ok(b[H.k], n)) continue;
    z.n += b[H.n]; z.eu += b[H.k] * b[H.n]; z.outro += b[H.outro]; z.comp += b[H.comp]; z.aptos += b[H.aptos]; z.bn += b[H.bn]; z.biom += b[H.biom];
    z.eu_cruz += b[H.eu_cruz]; z.outro_cruz += b[H.outro_cruz]; z.comp_cruz += b[H.comp_cruz]; z.n_cruz += b[H.n_cruz];
  }
  return z;
}
const condTxt = (n = S.n) => `${OPS[S.op].txt} ${fmtInt.format(+n)} ${+n === 1 && S.op !== 'ge' ? 'voto' : 'votos'}`;

function bloco(info, cand, r) {
  const outro = cand === '13' ? '22' : '13'; const cls = cand === '13' ? 'l' : 'f';
  const nome = info.cands[cand], nomeOutro = info.cands[outro];
  const b = el('div', 'bloco');
  const h = el('h3'); h.append(el('span', cls, nome), ` com ${condTxt()} na urna`); b.append(h);
  b.append(el('div', 'grande-n ' + cls, fmtInt.format(r.n) + (r.n === 1 ? ' urna' : ' urnas')));
  b.append(el('div', 'sub', r.tot ? `${fmtPctUrna(100 * r.n / r.tot)} das ${fmtInt.format(r.tot)} urnas · ${nomeLugar()} · ${info.nome}` : 'sem urnas na seleção'));
  const t = el('table', 'kv');
  const linha = (k, v, c, sep) => { const tr = el('tr', sep ? 'sep' : ''); tr.append(el('td', 'k', k), el('td', c, v)); t.append(tr); };
  if (r.n) {
    const val = r.eu + r.outro;
    linha(`Votos de ${nome} nessas urnas`, fmtInt.format(r.eu), cls);
    linha(`Votos de ${nomeOutro} nessas urnas`, `${fmtInt.format(r.outro)}${val ? ` (${fmtPct1.format(100 * r.outro / val)}% dos válidos)` : ''}`, cand === '13' ? 'f' : 'l');
    linha('Comparecimento', fmtInt.format(r.comp));
    linha('Brancos e nulos', `${fmtInt.format(r.bn)}${r.comp ? ` (${fmtPct1.format(100 * r.bn / r.comp)}%)` : ''}`);
    linha('Eleitores aptos', `${fmtInt.format(r.aptos)}${r.aptos ? ` · comparecimento ${fmtPct1.format(100 * r.comp / r.aptos)}%` : ''}`);
    linha('Habilitados sem biometria', `${fmtInt.format(r.biom)}${r.comp ? ` (${fmtPct1.format(100 * r.biom / r.comp)}%)` : ''}`);
    const valc = r.eu_cruz + r.outro_cruz;
    linha(`${info.cruz}, mesmas urnas (${fmtInt.format(r.n_cruz)} com par)`, r.n_cruz ? '' : 'sem par', 'fraco', true);
    if (r.n_cruz) {
      linha(`${nome} no ${info.cruz_curto}`, `${fmtInt.format(r.eu_cruz)}${valc ? ` (${fmtPct1.format(100 * r.eu_cruz / valc)}% dos válidos)` : ''}`, cls);
      linha(`${nomeOutro} no ${info.cruz_curto}`, fmtInt.format(r.outro_cruz), cand === '13' ? 'f' : 'l');
      linha(`Comparecimento no ${info.cruz_curto}`, fmtInt.format(r.comp_cruz));
    }
  }
  b.append(t);
  return b;
}

function frase(info, rl, rf) {
  const p = $('frase'); p.replaceChildren();
  if (!rl.tot) { p.textContent = 'Nenhuma urna na seleção.'; return; }
  p.append(`${info.nome}, ${nomeLugar()}: `, el('b', 'l', info.cands['13']), ' teve ', el('b', null, condTxt()), ' em ', el('b', null, fmtInt.format(rl.n) + (rl.n === 1 ? ' urna' : ' urnas')),
    rl.n ? ` e nelas ${info.cands['22']} somou ` : '', rl.n ? el('b', 'f', fmtInt.format(rl.outro)) : '', rl.n ? ` votos (comparecimento ${fmtInt.format(rl.comp)}). ` : '. ',
    el('b', 'f', info.cands['22']), ' teve ', el('b', null, condTxt()), ' em ', el('b', null, fmtInt.format(rf.n) + (rf.n === 1 ? ' urna' : ' urnas')),
    rf.n ? ` e nelas ${info.cands['13']} somou ` : '', rf.n ? el('b', 'l', fmtInt.format(rf.outro)) : '', rf.n ? ` votos (comparecimento ${fmtInt.format(rf.comp)}).` : '.');
}

// gráfico: urnas por faixa de votos (eixo y logarítmico), as duas séries lado a lado
function grafico(info, hist, ufs) {
  const box = $('grafico'); box.replaceChildren();
  const passo = CELULAR ? 20 : 10;
  const n = +S.n, ok = OPS[S.op].ok;
  let maxk = 0; const cont = {13: new Map(), 22: new Map()}, det = {13: new Map(), 22: new Map()};
  for (const cand of ['13', '22']) for (const uf of ufs) for (const b of hist[cand][uf] || []) {
    const f = Math.floor(b[H.k] / passo); if (b[H.k] > maxk) maxk = b[H.k];
    cont[cand].set(f, (cont[cand].get(f) || 0) + b[H.n]);
    const d = det[cand].get(f) || {n: 0, outro: 0, comp: 0, dentro: 0}; d.n += b[H.n]; d.outro += b[H.outro]; d.comp += b[H.comp]; if (ok(b[H.k], n)) d.dentro += b[H.n]; det[cand].set(f, d);
  }
  const nf = Math.floor(maxk / passo) + 1;
  const W = Math.max(280, Math.min(box.clientWidth, document.documentElement.clientWidth - 24) - 24), HG = CELULAR ? 240 : 320, ml = 44, mr = 8, mt = 10, mb = 30;
  const pw = W - ml - mr, ph = HG - mt - mb, gw = pw / nf, bw = Math.max(1, (gw - 2) / 2 - 1);
  let ymax = 1; for (const c of ['13', '22']) for (const v of cont[c].values()) if (v > ymax) ymax = v;
  const ltop = Math.ceil(Math.log10(ymax)); const y = (v) => mt + ph - (v <= 0 ? 0 : ph * Math.log10(v) / ltop);
  const ns = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${HG}`); svg.setAttribute('width', W); svg.setAttribute('height', HG);
  const mk = (tag, at, txt) => { const e = document.createElementNS(ns, tag); for (const k in at) e.setAttribute(k, at[k]); if (txt != null) e.textContent = txt; return e; };
  for (let e = 0; e <= ltop; e++) {
    const v = 10 ** e; svg.append(mk('line', {class: 'grade', x1: ml, x2: W - mr, y1: y(v), y2: y(v)}));
    svg.append(mk('text', {x: ml - 6, y: y(v) + 4, 'text-anchor': 'end'}, v >= 1000 ? (v / 1000) + ' mil' : String(v)));
  }
  svg.append(mk('line', {class: 'eixo', x1: ml, x2: W - mr, y1: mt + ph, y2: mt + ph}));
  const cada = Math.ceil(nf / (CELULAR ? 6 : 12));
  for (let f = 0; f < nf; f++) if (f % cada === 0 && ml + f * gw < W - mr - 90) svg.append(mk('text', {x: ml + f * gw, y: HG - 10, 'text-anchor': 'start'}, String(f * passo)));
  svg.append(mk('text', {x: W - mr, y: HG - 10, 'text-anchor': 'end'}, 'votos do candidato na urna →'));
  const cor = {13: 'var(--lula)', 22: 'var(--flavio)'};
  const tip = el('div', 'tip'); tip.hidden = true; box.append(tip);
  for (const cand of ['13', '22']) for (let f = 0; f < nf; f++) {
    const d = det[cand].get(f); if (!d) continue;
    const x = ml + f * gw + 1 + (cand === '22' ? bw + 2 : 0), yy = y(d.n);
    const r = mk('rect', {class: 'b' + (d.dentro ? '' : ' fora'), x, y: yy, width: bw, height: Math.max(1, mt + ph - yy), fill: cor[cand], rx: 2});
    r.addEventListener('mousemove', (ev) => {
      const lo = f * passo, hi = Math.min(maxk, f * passo + passo - 1);
      tip.innerHTML = `<b>${info.cands[cand]}</b> com ${lo === hi ? lo : lo + ' a ' + hi} votos na urna<br>${fmtInt.format(d.n)} urnas${d.dentro && d.dentro < d.n ? ` (${fmtInt.format(d.dentro)} na condição)` : ''}<br>${info.cands[cand === '13' ? '22' : '13']} nelas: ${fmtInt.format(d.outro)} · comparecimento ${fmtInt.format(d.comp)}`;
      tip.hidden = false; const bb = box.getBoundingClientRect(); tip.style.left = Math.min(ev.clientX - bb.left + 12, bb.width - 300) + 'px'; tip.style.top = (ev.clientY - bb.top + 12) + 'px';
    });
    r.addEventListener('mouseleave', () => { tip.hidden = true; });
    r.addEventListener('click', () => ir({op: 'le', n: String(Math.min(maxk, f * passo + passo - 1))}));
    svg.append(r);
  }
  box.prepend(svg);
  $('legenda-g').replaceChildren(Object.assign(el('span', null, info.cands['13']), {style: '--c:var(--lula)'}), Object.assign(el('span', null, info.cands['22']), {style: '--c:var(--flavio)'}));
  $('nota-grafico').textContent = `Número de urnas (escala logarítmica) por faixa de ${passo} votos do candidato, ${nomeLugar()}. Barras apagadas são faixas fora da condição escolhida. Clique numa faixa para aplicar "até o topo da faixa".`;
}

function ordenar(th, chave, padrao, estado) {
  th.addEventListener('click', () => { const col = th.dataset.col; const asc = S[estado.col] === col ? (S[estado.dir] === 'a' ? 'd' : 'a') : (padrao[col] || 'd'); ir({[estado.col]: col, [estado.dir]: asc}); });
}

function tabelaEstados(info, hist) {
  const ufs = S.uf ? [S.uf] : REGIOES[S.reg].ufs; const n = +S.n;
  const linhas = ufs.map((uf) => ({uf, nome: NOME_UF[uf], l: somar(hist, '13', [uf], S.op, n), f: somar(hist, '22', [uf], S.op, n)})).filter((r) => r.l.tot);
  const tot = {uf: '', nome: 'Total', l: somar(hist, '13', ufs, S.op, n), f: somar(hist, '22', ufs, S.op, n)};
  const COLS = [['nome', 'Estado', (r) => r.nome, 'txt'], ['tot', 'Urnas', (r) => r.l.tot, 'fraco'],
    ['ln', 'Urnas', (r) => r.l.n, 'l g2'], ['lp', '% urnas', (r) => (r.l.tot ? 100 * r.l.n / r.l.tot : 0), 'l'], ['le', `${info.cands['13']} nelas`, (r) => r.l.eu, ''], ['lo', `${info.cands['22']} nelas`, (r) => r.l.outro, 'f'], ['lc', 'Comparec.', (r) => r.l.comp, 'fraco'],
    ['fn', 'Urnas', (r) => r.f.n, 'f g2'], ['fp', '% urnas', (r) => (r.f.tot ? 100 * r.f.n / r.f.tot : 0), 'f'], ['fe', `${info.cands['22']} nelas`, (r) => r.f.eu, ''], ['fo', `${info.cands['13']} nelas`, (r) => r.f.outro, 'l'], ['fc', 'Comparec.', (r) => r.f.comp, 'fraco']];
  const col = COLS.find((c) => c[0] === S.col) ? S.col : 'ln'; const asc = S.dir === 'a';
  const fn = COLS.find((c) => c[0] === col)[2];
  linhas.sort((a, b) => { const x = fn(a), y = fn(b); const c = typeof x === 'string' ? x.localeCompare(y, 'pt-BR') : x - y; return asc ? c : -c; });
  const t = $('tab-estados'); t.replaceChildren();
  const thead = el('thead'); const tr0 = el('tr');
  tr0.append(el('th', 'grupo'), el('th', 'grupo')); const g1 = el('th', 'grupo g2 l', `${info.cands['13']} com ${condTxt()}`); g1.colSpan = 5; const g2 = el('th', 'grupo g2 f', `${info.cands['22']} com ${condTxt()}`); g2.colSpan = 5; tr0.append(g1, g2);
  const tr1 = el('tr');
  for (const [k, nome, , cls] of COLS) { const th = el('th', (cls.includes('g2') ? 'g2 ' : '') + (k === col ? 'ord' + (asc ? ' asc' : '') : ''), nome); th.dataset.col = k; ordenar(th, k, {nome: 'a'}, {col: 'col', dir: 'dir'}); tr1.append(th); }
  thead.append(tr0, tr1); t.append(thead);
  const tb = el('tbody');
  const fmt = (k, v) => (k === 'nome' ? v : k === 'lp' || k === 'fp' ? (v ? fmtPctUrna(v) : '0%') : fmtInt.format(v));
  for (const r of [...linhas, tot]) {
    const tr = el('tr', r.uf ? '' : 'total');
    for (const [k, , f, cls] of COLS) tr.append(el('td', cls, fmt(k, f(r))));
    tb.append(tr);
  }
  t.append(tb);
  $('nota-estados').textContent = `Para cada estado: quantas urnas satisfazem a condição para cada candidato e, nessas urnas, os votos dos dois e o comparecimento. Clique no cabeçalho para ordenar.`;
}

async function tabelaUrnas(info, meta) {
  const t = $('tab-urnas'); const nota = $('nota-urnas'); const n = +S.n;
  const lim = meta.lim_lista;
  const listavel = (S.op === 'le' || S.op === 'eq') && n <= lim;
  $('tit-urnas').textContent = listavel ? `Urnas em que ${info.cands['13']} ou ${info.cands['22']} teve ${condTxt()} · ${nomeLugar()}` : 'Urnas';
  if (!listavel) { t.replaceChildren(); nota.textContent = `A lista nominal de urnas só está disponível para "até" ou "exatamente" ${lim} votos ou menos (${fmtInt.format(lim)} é o limite do arquivo). Use os totais acima.`; return; }
  const urnas = await get(`urnas_${S.t}`);
  const ufs = new Set(ufsSel()); const ok = OPS[S.op].ok;
  const sel = urnas.filter((u) => ufs.has(u[U.uf]) && (ok(u[U.v13], n) || ok(u[U.v22], n)));
  const COLS = [['uf', 'UF', (u) => u[U.uf], 'txt'], ['mun', 'Município', (u) => u[U.mun], 'txt'], ['zona', 'Zona', (u) => u[U.zona], 'fraco'], ['secao', 'Seção', (u) => u[U.secao], 'fraco'], ['local', 'Local', (u) => u[U.local], 'fraco'], ['agreg', 'Agregadas', (u) => u[U.agreg] || '', 'fraco txt'],
    ['aptos', 'Aptos', (u) => u[U.aptos], ''], ['comp', 'Comparec.', (u) => u[U.comp], ''], ['v13', info.cands['13'], (u) => u[U.v13], 'l g2'], ['v22', info.cands['22'], (u) => u[U.v22], 'f'], ['bn', 'Br.+nulos', (u) => u[U.bn], 'fraco'], ['biom', 'Sem biom.', (u) => u[U.biom], 'fraco'],
    ['c13', `${info.cands['13']} ${info.cruz_curto}`, (u) => u[U.c13], 'l g2'], ['c22', `${info.cands['22']} ${info.cruz_curto}`, (u) => u[U.c22], 'f'], ['ccomp', `Comparec. ${info.cruz_curto}`, (u) => u[U.ccomp], 'fraco']];
  const col = COLS.find((c) => c[0] === S.ucol) ? S.ucol : 'comp'; const asc = S.udir === 'a'; const fn = COLS.find((c) => c[0] === col)[2];
  sel.sort((a, b) => { const x = fn(a), y = fn(b); if (x == null) return 1; if (y == null) return -1; const c = typeof x === 'string' ? x.localeCompare(y, 'pt-BR') : x - y; return asc ? c : -c; });
  const ln = +S.ln; const mostrar = ln ? sel.slice(0, ln) : sel;
  t.replaceChildren();
  const thead = el('thead'); const tr0 = el('tr'); const g0 = el('th', 'grupo'); g0.colSpan = 8; const g1 = el('th', 'grupo g2', info.nome); g1.colSpan = 4; const g2 = el('th', 'grupo g2', `${info.cruz} (mesma seção)`); g2.colSpan = 3; tr0.append(g0, g1, g2);
  const tr1 = el('tr');
  for (const [k, nome, , cls] of COLS) { const th = el('th', (cls.includes('g2') ? 'g2 ' : '') + (k === col ? 'ord' + (asc ? ' asc' : '') : ''), nome); th.dataset.col = k; ordenar(th, k, {uf: 'a', mun: 'a'}, {col: 'ucol', dir: 'udir'}); tr1.append(th); }
  thead.append(tr0, tr1); t.append(thead);
  const tb = el('tbody');
  for (const u of mostrar) {
    const tr = el('tr');
    for (const [k, , f, cls] of COLS) {
      const v = f(u); const td = el('td', cls, v == null ? '–' : typeof v === 'number' ? fmtInt.format(v) : v);
      if ((k === 'v13' && ok(u[U.v13], n)) || (k === 'v22' && ok(u[U.v22], n))) td.classList.add('zero');
      if (k === 'mun') td.title = v;
      tr.append(td);
    }
    tb.append(tr);
  }
  t.append(tb);
  nota.textContent = `${fmtInt.format(sel.length)} urnas${ln && sel.length > ln ? `, mostrando ${ln} (ordenadas por ${COLS.find((c) => c[0] === col)[1]})` : ''}. A célula destacada é a que satisfaz a condição. As três últimas colunas mostram como a mesma seção votou no ${info.cruz}; "–" quando a seção não existia no outro turno.`;
}

async function render() {
  const meta = await get('meta'); if (!meta.turnos[S.t]) S.t = PAD.t;
  const info = meta.turnos[S.t];
  // controles
  const tv = $('turnos'); if (!tv.childElementCount) for (const [k, v] of Object.entries(meta.turnos)) { const b = el('button', null, v.nome); b.type = 'button'; b.dataset.t = k; b.addEventListener('click', () => ir({t: k})); tv.append(b); }
  for (const b of tv.children) b.setAttribute('aria-pressed', String(b.dataset.t === S.t));
  preencherSelect($('sel-reg'), Object.entries(REGIOES).map(([k, v]) => [k, v.nome]), S.reg);
  preencherSelect($('sel-uf'), [['', S.reg === 'BR' ? 'todos' : 'toda a região'], ...REGIOES[S.reg].ufs.map((u) => [u, NOME_UF[u]])], S.uf);
  $('sel-op').value = S.op; if (document.activeElement !== $('in-n')) $('in-n').value = S.n; $('sel-n').value = S.ln;
  const at = $('atalhos'); if (!at.childElementCount) for (const [op, n, txt] of ATALHOS) { const b = el('button', null, txt); b.type = 'button'; b.dataset.k = op + n; b.addEventListener('click', () => ir({op, n: String(n)})); at.append(b); }
  for (const b of at.children) b.setAttribute('aria-pressed', String(b.dataset.k === S.op + S.n));
  const hist = await get(`hist_${S.t}`);
  const ufs = ufsSel(), n = +S.n;
  const rl = somar(hist, '13', ufs, S.op, n), rf = somar(hist, '22', ufs, S.op, n);
  frase(info, rl, rf);
  $('painel').replaceChildren(bloco(info, '13', rl), bloco(info, '22', rf));
  grafico(info, hist, ufs);
  tabelaEstados(info, hist);
  await tabelaUrnas(info, meta);
}

$('sel-reg').addEventListener('change', (e) => ir({reg: e.target.value, uf: ''}));
$('sel-uf').addEventListener('change', (e) => ir({uf: e.target.value}));
$('sel-op').addEventListener('change', (e) => ir({op: e.target.value}));
let tN = null; $('in-n').addEventListener('input', (e) => { clearTimeout(tN); tN = setTimeout(() => ir({n: String(Math.max(0, parseInt(e.target.value, 10) || 0))}), 250); });
$('sel-n').addEventListener('change', (e) => ir({ln: e.target.value}));
$('abrir-metodo').addEventListener('click', () => $('metodo').showModal());
render().catch((err) => { $('frase').textContent = 'Não foi possível carregar os dados: ' + err.message; console.error(err); });
