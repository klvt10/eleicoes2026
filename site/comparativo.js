// Comparativo presidente × governador × deputados (1º turno 2026): estados, cidades e gráfico.
// Estado da navegação no endereço (#vis=cidades&uf=SP&ref=gov&min=5000&n=50&col=desvio&dir=d).
'use strict';

const VERSAO = '20261029140908';
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtInt = new Intl.NumberFormat('pt-BR');
const fmtPct = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
const fmtPP = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero'});
const num = (v) => (v == null ? NaN : +v);
const NOME_UF = {AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás',
  MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná',
  RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins'};
const CELULAR = matchMedia('(max-width: 860px)').matches;

// referências: o que se compara com o % de Lula no 1º turno
const REFS = {
  gov: {nome: 'campo Lula no governo', curto: 'campo Lula (gov.)', v: (r) => num(r.gl)},
  sen: {nome: 'campo Lula no senado', curto: 'campo Lula (sen.)', v: (r) => num(r.sl)},
  df: {nome: 'esquerda em deputado federal', curto: 'esquerda (dep. fed.)', v: (r) => num(r.df_esq)},
  de: {nome: 'esquerda em deputado estadual', curto: 'esquerda (dep. est.)', v: (r) => num(r.de_esq)},
  dfpt: {nome: 'PT em deputado federal', curto: 'PT (dep. fed.)', v: (r) => num(r.df_pt)},
  gf: {nome: 'Flávio × campo Flávio no governo', curto: 'campo Flávio (gov.)', v: (r) => num(r.gf), lado: 'f'},
  sf: {nome: 'Flávio × campo Flávio no senado', curto: 'campo Flávio (sen.)', v: (r) => num(r.sf), lado: 'f'},
  dfdir: {nome: 'Flávio × direita em deputado federal', curto: 'direita (dep. fed.)', v: (r) => num(r.df_dir), lado: 'f'},
};
const MINIMOS = [0, 1000, 2000, 5000, 10000, 20000, 50000, 100000];
const PAD = {vis: 'estados', uf: '', ref: 'gov', min: '2000', n: '50', col: '', dir: '', busca: '', card: ''};
function lerEstado() {
  const p = new URLSearchParams(location.hash.slice(1)); const s = {...PAD};
  for (const k of Object.keys(PAD)) if (p.get(k) != null) s[k] = p.get(k);
  if (!REFS[s.ref]) s.ref = PAD.ref; if (!['estados', 'cidades', 'grafico'].includes(s.vis)) s.vis = PAD.vis;
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
let tRes = null; window.addEventListener('resize', () => { if (S.vis === 'grafico') { clearTimeout(tRes); tRes = setTimeout(render, 150); } });

const cache = new Map();
const get = (path) => { if (!cache.has(path)) cache.set(path, fetch(`${path}?v=${VERSAO}`).then((r) => { if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); })); return cache.get(path); };

// medidas: valor de Lula (ou Flávio) menos a referência, e o desvio em relação ao estado
const alvo = (r, ref) => (ref.lado === 'f' ? num(r.f1) : num(r.l1));
const dif = (r, ref) => alvo(r, ref) - ref.v(r);
function desvio(r, ref, ufs) { const u = ufs.get(r.uf); return u ? dif(r, ref) - dif(u, ref) : NaN; }
const clsSinal = (v, lim = 0) => (v > lim ? 'pos' : v < -lim ? 'neg' : '');

function preencherSelect(s, ops, valor) {
  const assin = ops.map((o) => o[0]).join('|');
  if (s.dataset.assin !== assin) { s.replaceChildren(...ops.map(([v, t]) => new Option(t, v))); s.dataset.assin = assin; }
  s.value = valor;
}

// ---------- tabela genérica com ordenação
function montaTabela(t, cols, rows, total, chaveOrd, asc, aoOrdenar, aoClicar) {
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
      const td = el('td', (c.txt ? 'txt ' : '') + (c.cls ? c.cls(v, r) : ''), c.txt ? (v ?? '—') : Number.isFinite(v) ? (c.fmt ? c.fmt(v) : fmtPct.format(v)) : '—');
      trr.appendChild(td);
    });
    if (aoClicar && !cls) trr.onclick = () => aoClicar(r);
    return trr;
  };
  rows.forEach((r) => tbody.appendChild(linha(r)));
  t.appendChild(tbody);
  if (total) { const tf = el('tfoot'); tf.appendChild(linha(total, 'total')); t.appendChild(tf); }
}
function ordena(rows, col, asc) {
  const v = (r) => col.v(r);
  return [...rows].sort((a, b) => {
    const x = v(a), y = v(b);
    if (col.txt) return asc ? String(x).localeCompare(String(y), 'pt-BR') : String(y).localeCompare(String(x), 'pt-BR');
    if (!Number.isFinite(x)) return 1; if (!Number.isFinite(y)) return -1;
    return asc ? x - y : y - x;
  });
}

// ---------- colunas das tabelas de estados e cidades: votos dos dois turnos, votos em disputa, perfil, previsto e realizado
const pct = (k) => (r) => num(r[k]);
const fmtSig = new Intl.NumberFormat('pt-BR', {signDisplay: 'exceptZero'});
const sinal = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const COLS_M = (nomeCol) => [
  {k: 'nome', t: nomeCol, v: (r) => r.nomeT, txt: true},
  {k: 'l1', t: 'Lula 1º t.', v: (r) => num(r.l1), fmt: (v) => fmtInt.format(v), dica: 'Votos de Lula no 1º turno'},
  {k: 'f1', t: 'Flávio 1º t.', v: (r) => num(r.f1), fmt: (v) => fmtInt.format(v)},
  {k: 'l2', t: 'Lula 2º t.', v: (r) => num(r.l2), fmt: (v) => fmtInt.format(v)},
  {k: 'f2', t: 'Flávio 2º t.', v: (r) => num(r.f2), fmt: (v) => fmtInt.format(v)},
  {k: 'liq', t: 'Em disputa', v: (r) => num(r.liq), fmt: (v) => fmtInt.format(v), dica: 'Votos líquidos: outros candidatos + queda de brancos/nulos + queda da abstenção = ganho de Lula + ganho de Flávio'},
  {k: 'perfil', t: 'Perfil (% Lula)', v: (r) => num(r.perfil), fmt: (v) => fmtPct.format(v) + '%', dica: 'Metade da presidencial do 1º turno + metade da média dos outros cargos'},
  {k: 'prev_gl', t: 'Previsto Lula', v: (r) => num(r.prev_gl), fmt: (v) => fmtSig.format(v), cls: () => 'pos', dica: 'Perfil × votos em disputa'},
  {k: 'prev_gf', t: 'Previsto Flávio', v: (r) => num(r.prev_gf), fmt: (v) => fmtSig.format(v), cls: () => 'neg'},
  {k: 'gl', t: 'Realizado Lula', v: (r) => num(r.gl), fmt: (v) => fmtSig.format(v), cls: () => 'pos', dica: 'Ganho de Lula entre os turnos'},
  {k: 'gf', t: 'Realizado Flávio', v: (r) => num(r.gf), fmt: (v) => fmtSig.format(v), cls: () => 'neg'},
  {k: 'dif', t: 'Real − previsto (Lula)', v: (r) => num(r.gl) - num(r.prev_gl), fmt: (v) => fmtSig.format(v), cls: (v) => sinal(v), dica: 'Ganho real de Lula menos o previsto, em votos (para Flávio é o oposto)'},
  {k: 'difp', t: 'Dif. (p.p.)', v: (r) => { const b = num(r.liq) > 0 ? num(r.liq) : num(r.entradas); return b > 0 ? 100 * (num(r.gl) - num(r.prev_gl)) / b : NaN; }, fmt: (v) => fmtPP.format(v), cls: (v) => sinal(v), dica: 'Diferença em pontos dos votos em disputa; onde eles são negativos (abstenção subiu mais do que entraram votos), em pontos das entradas'},
];
const linhaUF = (u, m, nomeT) => ({uf: u.uf, nomeT, l1: m.l1, f1: m.f1, l2: m.l2, f2: m.f2, liq: m.liq, entradas: m.x && m.x.entradas, perfil: m.x && m.x.perfil, prev_gl: m.prev_gl, prev_gf: m.prev_gf, gl: m.gl, gf: m.gf});

// ---------- cartões
function cartoes(br, cids, ref, ufs) {
  const c = $('cartoes'); c.replaceChildren();
  const base = cids.filter((x) => Number.isFinite(desvio(x, ref, ufs)) && num(x.votos) >= 2000);
  const acima = base.filter((x) => desvio(x, ref, ufs) > 5).length, abaixo = base.filter((x) => desvio(x, ref, ufs) < -5).length;
  [['Lula 1º turno', fmtPct.format(num(br.l1)) + '%', '', `Flávio ${fmtPct.format(num(br.f1))}% · outros ${fmtPct.format(num(br.o1))}%`],
    ['Lula 2º turno', fmtPct.format(num(br.l2)) + '%', '', 'entre Lula e Flávio'],
    ['Governador: campo Lula', fmtPct.format(num(br.gl)) + '%', '', `campo Flávio ${fmtPct.format(num(br.gf))}% · outros ${fmtPct.format(num(br.go))}%`],
    ['Senador: campo Lula', fmtPct.format(num(br.sl)) + '%', '', `campo Flávio ${fmtPct.format(num(br.sf))}% · outros ${fmtPct.format(num(br.so))}%`],
    ['Dep. federal: esquerda', fmtPct.format(num(br.df_esq)) + '%', '', `centro ${fmtPct.format(num(br.df_cen))}% · direita ${fmtPct.format(num(br.df_dir))}%`],
    ['Dep. estadual: esquerda', fmtPct.format(num(br.de_esq)) + '%', '', `centro ${fmtPct.format(num(br.de_cen))}% · direita ${fmtPct.format(num(br.de_dir))}%`],
    [`Lula − ${ref.curto}`, fmtPP.format(dif(br, ref)) + ' p.p.', clsSinal(dif(br, ref)), `Brasil; ${fmtInt.format(acima)} cidades 5+ p.p. acima do seu estado, ${fmtInt.format(abaixo)} abaixo (2.000+ válidos)`],
  ].forEach(([k, v, cl, s]) => { const d = el('div', 'cartao'); d.append(el('span', 'k', k), el('span', 'v ' + cl, v)); if (s) d.appendChild(el('span', 's', s)); c.appendChild(d); });
}

// ---------- estados: tabela; clicar numa linha abre o card do estado (o total abre o Brasil)
const pctDe = (v, d) => (d > 0 ? 100 * v / d : NaN);
function estados(ufsArr, br, ref, ufs, modelo) {
  const rows = ufsArr.filter((u) => u.uf !== 'BR' && modelo.ufs[u.uf]).map((u) => linhaUF(u, modelo.ufs[u.uf], CELULAR ? u.uf : `${NOME_UF[u.uf] ?? u.uf} (${u.uf})`));
  const cols = COLS_M('Estado');
  const col = cols.find((c) => c.k === S.col) ?? cols.find((c) => c.k === 'dif');
  const asc = S.dir ? S.dir === 'a' : !!col.txt;
  montaTabela($('tab-estados'), cols, ordena(rows, col, asc), linhaUF(br, modelo.brasil, 'Brasil'), col.k, asc, (k, d) => ir({col: k, dir: d}), (r) => ir({card: r.uf}));
  const tf = $('tab-estados').querySelector('tfoot tr'); if (tf) { tf.style.cursor = 'pointer'; tf.title = 'Ver o card do Brasil'; tf.onclick = () => ir({card: 'BR'}); }
  $('nota-estados').textContent = 'Votos de Lula e Flávio nos dois turnos; votos em disputa = outros candidatos + queda de brancos/nulos + queda da abstenção; perfil = metade da presidencial do 1º turno + metade da média dos outros cargos (governador, senador, deputados), em % Lula; previsto = perfil × em disputa; realizado = ganho de cada um entre os turnos. Clique num estado, ou no total, para abrir o card.';
}

// ---------- cidades
function cidades(cids, ref, ufs, br, modelo, cm) {
  const minV = +S.min || 0, n = +S.n || 0, q = (S.busca || '').trim().toLowerCase();
  let base = cm.filter((x) => (!S.uf || x.uf === S.uf) && num(x.votos) >= minV);
  if (q) base = base.filter((x) => x.nome.toLowerCase().includes(q));
  base = base.map((x) => ({...x, nomeT: `${x.nome} (${x.uf})`, perfil: x.x && x.x.perfil, entradas: x.x && x.x.entradas}));
  const cols = COLS_M('Cidade');
  const col = cols.find((c) => c.k === S.col) ?? cols.find((c) => c.k === 'dif');
  const asc = S.dir ? S.dir === 'a' : !!col.txt;
  let rows = ordena(base, col, asc);
  if (n && rows.length > 2 * n && !q) rows = [...rows.slice(0, n), ...rows.slice(-n)];
  const tot = S.uf ? linhaUF(ufs.get(S.uf), modelo.ufs[S.uf], `${NOME_UF[S.uf]} (todo o estado)`) : linhaUF(br, modelo.brasil, 'Brasil');
  montaTabela($('tab-cidades'), cols, rows, tot, col.k, asc, (k, d) => ir({col: k, dir: d}), (r) => { location.href = `modelo.html#vis=cidades&uf=${r.uf}&card=${r.uf}-${r.cd}`; });
  $('tit-cidades').textContent = S.uf ? `Cidades de ${NOME_UF[S.uf]}` : 'Cidades do Brasil';
  $('nota-cidades').textContent = `${fmtInt.format(base.length)} cidades${minV ? ` com ${fmtInt.format(minV)} votos válidos ou mais para presidente` : ''}` +
    `${n && base.length > 2 * n && !q ? `; mostrando as ${n} de maior e as ${n} de menor valor na coluna ordenada` : ''}. ` +
    'Mesmas colunas da tabela de estados; o perfil é o da cidade. Clique numa cidade para abrir o card dela.';
}

// ---------- gráfico de dispersão: x = referência, y = Lula (ou Flávio) no 1º turno
function grafico(cids, ref, ufs, br) {
  const box = $('grafico'); box.replaceChildren();
  const minV = +S.min || 0;
  const pts = cids.filter((x) => (!S.uf || x.uf === S.uf) && num(x.votos) >= minV && Number.isFinite(ref.v(x)) && Number.isFinite(alvo(x, ref)));
  const boxTop = box.getBoundingClientRect().top + window.scrollY;
  const W = Math.max(360, box.clientWidth - 24), H = Math.max(300, window.innerHeight - boxTop - 56), L = 46, R = 16, T = 14, B = 44;
  const x = (v) => L + v / 100 * (W - L - R), y = (v) => T + (100 - v) / 100 * (H - T - B);
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H); svg.setAttribute('role', 'img');
  const mk = (tag, a, txt) => { const e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; svg.appendChild(e); return e; };
  for (let v = 0; v <= 100; v += 10) {
    mk('line', {x1: x(v), x2: x(v), y1: y(0), y2: y(100), class: 'grade'}); mk('line', {x1: x(0), x2: x(100), y1: y(v), y2: y(v), class: 'grade'});
    mk('text', {x: x(v), y: y(0) + 16, 'text-anchor': 'middle'}, v + '%'); mk('text', {x: x(0) - 6, y: y(v) + 4, 'text-anchor': 'end'}, v + '%');
  }
  mk('line', {x1: x(0), x2: x(100), y1: y(0), y2: y(0), class: 'eixo'}); mk('line', {x1: x(0), x2: x(0), y1: y(0), y2: y(100), class: 'eixo'});
  mk('text', {x: (x(0) + x(100)) / 2, y: H - 6, 'text-anchor': 'middle'}, `${ref.nome} (% dos válidos)`);
  const ty = mk('text', {x: 12, y: (y(0) + y(100)) / 2, 'text-anchor': 'middle', transform: `rotate(-90 12 ${(y(0) + y(100)) / 2})`}, `${ref.lado === 'f' ? 'Flávio' : 'Lula'} no 1º turno (% dos válidos)`);
  mk('line', {x1: x(0), y1: y(0), x2: x(100), y2: y(100), class: 'ident'});
  const base = S.uf ? ufs.get(S.uf) : br;
  const off = base ? dif(base, ref) : 0;
  if (base) { const a = Math.max(0, -off), b = Math.min(100, 100 - off); mk('line', {x1: x(a), y1: y(a + off), x2: x(b), y2: y(b + off), class: 'media'}); }
  const maxV = Math.max(...pts.map((p) => num(p.votos)), 1);
  const rad = (v) => 2 + 14 * Math.sqrt(v / maxV);
  const cor = (p) => { const d = desvio(p, ref, ufs); return d > 5 ? 'var(--lula)' : d < -5 ? 'var(--flavio)' : 'var(--neutro)'; };
  [...pts].sort((a, b) => num(b.votos) - num(a.votos)).forEach((p) => {
    const c = mk('circle', {cx: x(ref.v(p)), cy: y(alvo(p, ref)), r: rad(num(p.votos)), fill: cor(p), 'fill-opacity': 0.75});
    c.dataset.cd = p.cd; c.dataset.uf = p.uf;
  });
  box.appendChild(svg);
  let tip = null;
  const porChave = new Map(pts.map((p) => [`${p.uf}-${p.cd}`, p]));
  svg.addEventListener('mousemove', (e) => {
    const c = e.target.closest('circle'); if (!c) { if (tip) { tip.remove(); tip = null; } return; }
    const p = porChave.get(`${c.dataset.uf}-${c.dataset.cd}`); if (!p) return;
    if (!tip) { tip = el('div', 'tip'); box.appendChild(tip); }
    tip.innerHTML = `<b>${p.nome} (${p.uf})</b><br>${fmtInt.format(num(p.votos))} votos válidos<br>Lula 1º t. ${fmtPct.format(num(p.l1))}% · Flávio ${fmtPct.format(num(p.f1))}% · Lula 2º t. ${fmtPct.format(num(p.l2))}%<br>` +
      `Gov.: campo Lula ${fmtPct.format(num(p.gl))}% · campo Flávio ${fmtPct.format(num(p.gf))}%${p.gov_lider ? ` · líder ${p.gov_lider} ${fmtPct.format(num(p.gov_lider_pct))}%` : ''}<br>` +
      `Sen.: campo Lula ${fmtPct.format(num(p.sl))}% · campo Flávio ${fmtPct.format(num(p.sf))}%${p.sen_lider ? ` · líder ${p.sen_lider} ${fmtPct.format(num(p.sen_lider_pct))}%` : ''}<br>` +
      `Dep. fed.: esq. ${fmtPct.format(num(p.df_esq))}% · centro ${fmtPct.format(num(p.df_cen))}% · dir. ${fmtPct.format(num(p.df_dir))}%<br>` +
      `${ref.lado === 'f' ? 'Flávio' : 'Lula'} − ${ref.curto}: <b>${fmtPP.format(dif(p, ref))}</b> · desvio vs ${p.uf}: <b>${fmtPP.format(desvio(p, ref, ufs))}</b>`;
    const r = box.getBoundingClientRect(); let lx = e.clientX - r.left + 14, ly = e.clientY - r.top + 14;
    if (lx + 290 > r.width) lx = Math.max(0, e.clientX - r.left - 300); if (ly + 120 > r.height) ly = Math.max(0, ly - 140);
    tip.style.left = lx + 'px'; tip.style.top = ly + 'px';
  });
  svg.addEventListener('mouseleave', () => { if (tip) { tip.remove(); tip = null; } });
  svg.addEventListener('click', (e) => { const c = e.target.closest('circle'); if (c) location.href = `index.html#uf=${c.dataset.uf}&cd=${c.dataset.cd}`; });
  $('tit-grafico').textContent = `${S.uf ? NOME_UF[S.uf] : 'Brasil'}: ${ref.lado === 'f' ? 'Flávio' : 'Lula'} × ${ref.nome}`;
  $('nota-grafico').textContent = `Cada bolha é uma cidade (${fmtInt.format(pts.length)}${minV ? `, com ${fmtInt.format(minV)} válidos ou mais` : ''}); o tamanho é o número de votos válidos. ` +
    `A linha tracejada é a igualdade (mesmo % nos dois cargos); a linha cheia é o padrão ${S.uf ? 'do estado' : 'do Brasil'} (${fmtPP.format(off)} pontos). ` +
    'A cor marca o desvio em relação ao estado da cidade: vermelho acima de 5 pontos, azul abaixo de −5. Passe o mouse para ver a cidade; clique para abri-la no mapa.';
}

// ---------- render
let DADOS = null;
async function render() {
  if (!DADOS) {
    const [ufsArr, cids, modelo, cm] = await Promise.all([get('dados/comparativo/uf.json'), get('dados/comparativo/cidades.json'), get('dados/comparativo/modelo.json'), get('dados/comparativo/cidades_modelo.json')]);
    DADOS = {ufsArr, cids, modelo, cm, ufs: new Map(ufsArr.map((u) => [u.uf, u])), br: ufsArr.find((u) => u.uf === 'BR')};
  }
  const {ufsArr, cids, ufs, br, modelo, cm} = DADOS;
  Cards.setModelo(modelo);
  const ref = REFS[S.ref];
  ['estados', 'cidades', 'grafico'].forEach((v) => { $('vis-' + v).setAttribute('aria-pressed', String(S.vis === v)); $('sec-' + v).hidden = S.vis !== v; });
  preencherSelect($('sel-ref'), Object.entries(REFS).map(([k, r]) => [k, (r.lado === 'f' ? 'Flávio × ' : 'Lula × ') + r.nome.replace(/^Flávio × /, '')]), S.ref);
  preencherSelect($('sel-uf'), [['', 'Brasil'], ...Object.keys(NOME_UF).map((u) => [u, `${u} · ${NOME_UF[u]}`])], S.uf);
  preencherSelect($('sel-min'), MINIMOS.map((v) => [String(v), v ? `${fmtInt.format(v)} válidos` : 'qualquer tamanho']), S.min);
  preencherSelect($('sel-n'), [['25', '25 de cada ponta'], ['50', '50 de cada ponta'], ['100', '100 de cada ponta'], ['0', 'todas']], S.n);
  $('busca').value = S.busca;
  $('filtros').hidden = false; $('lbl-uf').hidden = S.vis === 'estados'; $('lbl-min').hidden = S.vis === 'estados'; $('sel-ref').parentElement.hidden = S.vis !== 'grafico';
  $('cartoes').hidden = S.vis === 'grafico'; document.body.classList.toggle('so-grafico', S.vis === 'grafico'); $('lbl-n').hidden = S.vis !== 'cidades'; $('lbl-busca').hidden = S.vis !== 'cidades';
  cartoes(br, cids, ref, ufs);
  if (S.vis === 'estados') estados(ufsArr, br, ref, ufs, modelo);
  else if (S.vis === 'cidades') cidades(cids, ref, ufs, br, modelo, cm);
  else grafico(cids, ref, ufs, br);
  const uc = S.card ? ufs.get(S.card) : null;
  if (uc) Cards.estado(uc, S.card === 'BR' ? modelo.brasil : modelo.ufs[S.card], [
    ...(S.card === 'BR' ? [] : [['Ver as cidades', () => ir({vis: 'cidades', uf: S.card, card: ''})]]),
    ['Ver o gráfico', () => ir({vis: 'grafico', uf: S.card === 'BR' ? '' : S.card, card: ''})]]);
  else if ($('card-uf').open) $('card-uf').close();
}
['estados', 'cidades', 'grafico'].forEach((v) => { $('vis-' + v).onclick = () => ir({vis: v}); });
$('sel-ref').onchange = (e) => ir({ref: e.target.value, col: '', dir: ''});
$('sel-uf').onchange = (e) => ir({uf: e.target.value});
$('sel-min').onchange = (e) => ir({min: e.target.value});
$('sel-n').onchange = (e) => ir({n: e.target.value});
let tBusca = null;
$('busca').oninput = (e) => { clearTimeout(tBusca); tBusca = setTimeout(() => ir({busca: e.target.value}), 250); };
$('abrir-metodo').onclick = () => $('metodo').showModal();
render().catch((err) => { $('cartoes').textContent = 'Não foi possível carregar os dados: ' + err.message; });
