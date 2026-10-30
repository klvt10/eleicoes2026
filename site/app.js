// Mapa das transferências do 2º turno: Brasil → estado → cidade → local → seção.
// Estado da navegação fica no endereço (#uf=SP&cd=71072&local=...&secao=...), então voltar e compartilhar funcionam.
'use strict';

const CAP_SP = 71072;
const fmtInt = new Intl.NumberFormat('pt-BR');
const fmtSig = new Intl.NumberFormat('pt-BR', {signDisplay: 'exceptZero'});
const fmtMil = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0, signDisplay: 'exceptZero'});
const fmtPct = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1});
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const sinal = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const quem = (v) => (v >= 0 ? 'Lula' : 'Flávio');

// ---------- dados
// Versão da publicação (scripts/publica_site.sh troca a cada deploy): endereço novo = navegador nunca mistura arquivos de versões diferentes
const VERSAO = '20261029140908';
const cache = new Map();
const get = (path) => {
  if (!cache.has(path)) cache.set(path, fetch(`${path}?v=${VERSAO}`).then((r) => { if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); }));
  return cache.get(path);
};
const secCache = new Map();
async function secoes(uf) {
  if (!secCache.has(uf)) {
    secCache.set(uf, get(`dados/secoes/${uf}.json`).then(({cols, rows}) => rows.map((v, i) => {
      const r = {}; cols.forEach((c, j) => (r[c] = v[j]));
      r.key = `${r.cd}-${r.z}-${r.s}`; r.lk = `${r.cd}-${r.z}-${r.l}`; r.rank = i + 1; r.bn = r.liq - r.gl - r.gf;
      return r;
    })));
  }
  return secCache.get(uf);
}

// ---------- métricas de ordenação (todas: maior = mais para Lula)
// pct: parte dos votos líquidos decididos (ganho de Lula + ganho de Flávio) que foi para Lula; >100% = Flávio perdeu votos
const decididos = (r) => r.gl + r.gf;
const decididos22 = (r) => (r.gl22 == null ? NaN : r.gl22 + r.gb22);
const num = (v) => (v == null ? NaN : +v);
const pctFmt = (v) => fmtPct.format(v) + '%';
// % dos decididos só faz sentido com os dois ganhos >= 0; com um ganho negativo, diz em palavras quem levou
function decidTxt(gl, ga, adv) {
  if (gl == null || ga == null) return {txt: '—', cls: ''};
  if (gl >= 0 && ga >= 0) return gl + ga > 0 ? {txt: pctFmt(100 * gl / (gl + ga)), cls: gl >= ga ? 'pos' : 'neg'} : {txt: '—', cls: ''};
  if (gl > 0) return {txt: `só Lula ganhou (${adv} ${fmtSig.format(ga)})`, cls: 'pos'};
  if (ga > 0) return {txt: `só ${adv} ganhou (Lula ${fmtSig.format(gl)})`, cls: 'neg'};
  return {txt: 'os dois perderam votos', cls: ''};
}
const ppFmt = (v) => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1, signDisplay: 'exceptZero'}).format(v) + ' p.p.';
const METRICA = {
  votos: {nome: 'transferência líquida (votos)', v: (r) => r.saldo, fmt: (v) => fmtSig.format(v), lado: (v) => v, base: 'liq', baseNome: 'votos líquidos'},
  pct: {nome: '% dos votos decididos para Lula', M: 50, v: (r) => (decididos(r) > 0 ? 100 * r.gl / decididos(r) : NaN), fmt: (v) => fmtPct.format(v) + '%', lado: (v) => v - 50, base: 'dec', baseNome: 'votos decididos'},
  mil: {nome: 'saldo a cada 1000 votos líquidos', v: (r) => (r.liq > 0 ? 1000 * r.saldo / r.liq : NaN), fmt: (v) => fmtMil.format(v), lado: (v) => v, base: 'liq', baseNome: 'votos líquidos'},
  l26: {nome: 'Lula no 2º turno 2026 (%)', v: (r) => num(r.l26), fmt: pctFmt, lado: (v) => v - 50, M: 25, base: 'liq', baseNome: 'votos líquidos'},
  var_l: {nome: 'Lula no 2º turno: 2026 − 2022 (p.p.)', v: (r) => num(r.l26) - num(r.l22), fmt: ppFmt, lado: (v) => v, base: 'liq', baseNome: 'votos líquidos'},
  pct22: {nome: '% dos decididos para Lula em 2022', v: (r) => (decididos22(r) > 0 ? 100 * r.gl22 / decididos22(r) : NaN), fmt: pctFmt, lado: (v) => v - 50, M: 50, base: 'dec22', baseNome: 'votos decididos em 2022'},
  var_pct: {nome: '% dos decididos para Lula: 2026 − 2022 (p.p.)', v: (r) => METRICA.pct.v(r) - METRICA.pct22.v(r), fmt: ppFmt, lado: (v) => v, base: 'dec2', baseNome: 'votos decididos (nos dois anos)'},
  i24: {nome: 'Índice municipal 2024 (vereador, em % Lula)', v: (r) => num(r.i24), fmt: pctFmt, lado: (v) => v - 50, M: 10, base: 'liq', baseNome: 'votos líquidos'},
  bloco24: {nome: 'Vereador 2024: esquerda − direita (p.p.)', v: (r) => num(r.esq24) - num(r.dir24), fmt: ppFmt, lado: (v) => v, base: 'liq', baseNome: 'votos líquidos'},
  l26_i24: {nome: 'Lula 2026 acima do índice municipal (p.p.)', v: (r) => num(r.l26) - num(r.i24), fmt: ppFmt, lado: (v) => v, base: 'liq', baseNome: 'votos líquidos'},
};
let BLOCO_DE = new Map();
const COR_BLOCO = {esquerda: '--lula', centro: '--neutro', direita: '--flavio'};
// Ordenações que dependem de 2022/2024: só existem de cidade para cima
const SO_AGREGADO = ['l26', 'var_l', 'pct22', 'var_pct', 'i24', 'bloco24', 'l26_i24'];
const CATEGORIA = {lula_lula: 'Lula em 2022 e em 2026', virou_lula: 'Virou para Lula em 2026', virou_contra: 'Virou contra Lula em 2026', direita_direita: 'Bolsonaro em 2022 e Flávio em 2026'};
const MINIMOS = [0, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 50000];
const modoCidade = () => S.cd && S.sec !== '1';
const nivelRk = () => (S.cd ? 'secoes' : S.uf ? (S.rk === 'secoes' ? 'secoes' : 'cidades') : S.rk === 'cidades' ? 'cidades' : 'estados');
const minAuto = (rk) => (S.ord === 'votos' ? 0 : {estados: 0, cidades: 1000, secoes: ['pct', 'pct22', 'var_pct'].includes(S.ord) ? 20 : 50}[rk]);
const minimo = (rk) => (S.min === '' ? minAuto(rk) : +S.min);
const semInstaveis = () => (S.inst === '' ? S.ord !== 'votos' : S.inst === '0');

// ---------- estado (no endereço)
const PAD = {vis: '', uf: '', cd: '', sec: '', local: '', secao: '', rk: '', ord: 'votos', min: '', inst: '', cat: '', n: '25', col: '', dir: ''};
const FICA = ['vis', 'n', 'ord', 'min', 'inst', 'cat', 'col', 'dir']; // valem em qualquer nível
function lerEstado() {
  const p = new URLSearchParams(location.hash.slice(1));
  const s = {...PAD};
  for (const k of Object.keys(PAD)) if (p.get(k)) s[k] = p.get(k);
  return s;
}
let S = lerEstado();
function ir(novo) {
  const s = {...PAD, ...Object.fromEntries(FICA.map((k) => [k, S[k]])), ...novo};
  const p = new URLSearchParams();
  for (const k of Object.keys(PAD)) if (s[k] && s[k] !== PAD[k]) p.set(k, s[k]);
  const h = '#' + p.toString();
  if (h === location.hash || (h === '#' && !location.hash)) render(); else location.hash = h;
}
window.addEventListener('hashchange', () => {
  const antes = `${S.uf}|${S.cd}|${S.sec}|${S.local}|${S.secao}`;
  S = lerEstado(); render();
  if (CELULAR && antes !== `${S.uf}|${S.cd}|${S.sec}|${S.local}|${S.secao}`) window.scrollTo({top: 0, behavior: 'smooth'});
});

// ---------- mapa
// No celular: um dedo rola a página, dois dedos movem e aproximam o mapa
const CELULAR = matchMedia('(max-width: 860px)').matches;
const mapa = L.map('mapa', {preferCanvas: true, zoomSnap: 0.25, minZoom: 3, worldCopyJump: false, dragging: !CELULAR || !L.Browser.mobile, tap: false}).setView([-14.5, -52], 4);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, className: 'fundo',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · TSE · IBGE',
}).addTo(mapa);
mapa.createPane('poligonos').style.zIndex = 410;
mapa.createPane('pontos').style.zIndex = 450;
const rendPol = L.canvas({pane: 'poligonos', padding: 0.3});
const rendPts = L.canvas({pane: 'pontos', padding: 0.3, tolerance: 3});

const legenda = L.control({position: 'bottomleft'});
legenda.onAdd = () => el('div', 'legenda');
legenda.addTo(mapa);
const status = L.control({position: 'topright'});
status.onAdd = () => el('div', 'status-mapa');
status.addTo(mapa);
const setStatus = (t) => { status.getContainer().textContent = t; };

function cor(v, M) {
  const t = (Math.max(-M, Math.min(M, v || 0)) + M) / (2 * M);
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [a, b] = t < 0.5 ? [hex(css('--flavio')), hex(css('--neutro'))] : [hex(css('--neutro')), hex(css('--lula'))];
  const u = t < 0.5 ? t * 2 : t * 2 - 1;
  return `rgb(${a.map((c, i) => Math.round(c + (b[i] - c) * u)).join(',')})`;
}
const p95 = (vals) => { const v = vals.filter(Number.isFinite).map(Math.abs).sort((a, b) => a - b); return v[Math.floor(0.95 * (v.length - 1))] || 1; };

let camEstados = null, camMun = null, camMunUF = '', camPts = L.layerGroup().addTo(mapa), enquadrado = null;

function legendaTexto(html) { legenda.getContainer().innerHTML = html; }
function escala(M, titulo, fmt = (x) => fmtMil.format(x)) {
  return `<b>${titulo}</b><div class="esc"></div><div class="ext"><span>${fmt(-M)}</span><span>${fmt(0)}</span><span>${fmt(M)}</span></div>`;
}
let tipLinhasAtual = () => [];
const tip = (titulo, linhas) => `<b>${titulo}</b>` + linhas.map((l) => `<br>${l}`).join('');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// ---------- render
let ticket = 0;
async function render() {
  const meu = ++ticket;
  const [ufs, cids, br, brasil, partidos] = await Promise.all([get('dados/uf.json'), get('dados/cidades.json'), get('dados/geo/br.json'), get('dados/brasil.json'), get('dados/partidos.json')]);
  BLOCO_DE = new Map(partidos.map((p) => [p.partido, p.bloco]));
  const ufRow = new Map(ufs.map((r) => [r.uf, r]));
  if (S.uf && !ufRow.has(S.uf)) { ir({}); return; }
  const emTabela = S.vis === 'tabela', emPlacar = S.vis === 'placar', emAnom = S.vis === 'anomalias', emDest = S.vis === 'destaques', emDisc = S.vis === 'discrepancias';
  $('vis-mapa').setAttribute('aria-pressed', String(!emTabela && !emPlacar && !emAnom && !emDest && !emDisc));
  $('vis-discrepancias').setAttribute('aria-pressed', String(emDisc));
  $('discrepancias').hidden = !emDisc;
  $('vis-destaques').setAttribute('aria-pressed', String(emDest));
  $('destaques').hidden = !emDest;
  $('vis-anomalias').setAttribute('aria-pressed', String(emAnom));
  $('anomalias').hidden = !emAnom;
  $('vis-tabela').setAttribute('aria-pressed', String(emTabela));
  $('vis-placar').setAttribute('aria-pressed', String(emPlacar));
  document.querySelector('main.app').hidden = emTabela || emPlacar || emAnom || emDest || emDisc;
  $('tabela').hidden = !emTabela;
  $('placar').hidden = !emPlacar;
  if (emTabela) { tabela(ufs, ufRow, cids, brasil); return; }
  if (emPlacar) { placar(cids, ufs); return; }
  if (emDest) { destaques(ufs, cids); return; }
  if (emDisc) { discrepancias(cids, brasil, ufs); return; }
  if (emAnom) { await relatorioAnomalias(); return; }
  mapa.invalidateSize();
  const cidUF = S.uf ? cids.filter((c) => c.uf === S.uf).sort((a, b) => a.nome.localeCompare(b.nome, 'pt')) : [];
  const cidRow = new Map(cidUF.map((c) => [String(c.cd), c]));
  const cidade = S.cd ? cidRow.get(S.cd) : null;

  preencherSelect($('sel-uf'), [['', 'Brasil (todos)'], ...ufs.map((r) => r.uf).sort().map((u) => [u, u === 'ZZ' ? 'Exterior (ZZ)' : u])], S.uf);
  preencherSelect($('sel-cidade'), [['', S.uf ? 'Todas as cidades' : 'Escolha um estado'], ...cidUF.map((c) => [String(c.cd), c.nome])], S.cd);
  $('sel-cidade').disabled = !S.uf;
  $('sel-n').value = S.n;

  // carrega o que o nível pede
  let secs = [], geoUF = null;
  const cid = modoCidade();
  $('ranking').hidden = cid;
  $('lbl-secao').hidden = cid || !S.cd;
  if (S.uf && (cid || nivelRk() === 'cidades')) {
    geoUF = S.uf === 'ZZ' ? null : await get(`dados/geo/${S.uf}.json`);
    if (meu !== ticket) return;
  } else if (S.uf) {
    setStatus('Carregando seções…');
    $('lista').replaceChildren(el('li', 'carregando', 'Carregando seções…'));
    [secs, geoUF] = await Promise.all([secoes(S.uf), S.uf === 'ZZ' ? null : get(`dados/geo/${S.uf}.json`)]);
    if (meu !== ticket) return;
    setStatus('');
  }
  const daCidade = S.cd ? secs.filter((r) => String(r.cd) === S.cd) : [];
  const escopo = S.local ? daCidade.filter((r) => r.lk === S.local) : S.cd ? daCidade : secs;
  const sel = S.secao ? secs.find((r) => r.key === S.secao) : null;
  const localRows = S.local ? daCidade.filter((r) => r.lk === S.local) : [];

  // seletor de seção
  const opSec = S.cd ? escopo.map((r) => [r.key, `Z${r.z} · S${r.s} · ${r.local} (${fmtSig.format(r.saldo)})`]) : [];
  preencherSelect($('sel-secao'), [['', S.cd ? (S.local ? 'Todas deste local' : 'Todas da cidade') : 'Escolha uma cidade'], ...opSec], S.secao);
  $('sel-secao').disabled = !S.cd;

  trilha(cidade, localRows[0] ?? (sel && S.local ? sel : null), sel);
  if (cid && cidade) cidadeSimples(cidade);
  else resumo({ufs, ufRow, cidade, localRows, sel, brasil});
  const mostradas = cid ? [] : ranking({ufs, cids, cidUF, escopo, cidRow, cidade});
  desenharMapa({br, ufs, ufRow, cidUF, cidRow, geoUF, secs, daCidade, escopo, sel, mostradas});
}

function preencherSelect(s, ops, valor) {
  const assin = ops.length + '|' + (ops[1]?.[0] ?? '') + '|' + (ops[ops.length - 1]?.[0] ?? '') + '|' + (ops[0]?.[1] ?? '') + '|' + (ops[1]?.[1] ?? '');
  if (s.dataset.assin !== assin) { s.replaceChildren(...ops.map(([v, t]) => new Option(t, v))); s.dataset.assin = assin; }
  s.value = valor;
}

function trilha(cidade, local, sel) {
  const t = $('trilha'); t.replaceChildren();
  const passos = [['Brasil', {}]];
  if (S.uf) passos.push([S.uf === 'ZZ' ? 'Exterior' : S.uf, {uf: S.uf}]);
  if (cidade) passos.push([cidade.nome, {uf: S.uf, cd: S.cd}]);
  if (cidade && S.sec === '1') passos.push(['Seções', {uf: S.uf, cd: S.cd, sec: '1'}]);
  if (S.local && local) passos.push([local.local, {uf: S.uf, cd: S.cd, sec: '1', local: S.local}]);
  if (sel) passos.push([`Seção ${sel.s} · zona ${sel.z}`, null]);
  passos.forEach(([nome, alvo], i) => {
    if (i) t.appendChild(el('i', null, '›'));
    if (i === passos.length - 1) t.appendChild(el('span', 'atual', nome));
    else { const b = el('button', null, nome); b.type = 'button'; b.onclick = () => ir(alvo); t.appendChild(b); }
  });
}

function resumo({ufs, ufRow, cidade, localRows, sel, brasil}) {
  const box = $('resumo'); box.replaceChildren();
  let nome, sub, d;
  const soma = (rs) => rs.reduce((a, r) => ({liq: a.liq + r.liq, gl: a.gl + r.gl, gf: a.gf + r.gf, bn: a.bn + r.bn, n: a.n + (r.n ?? 1)}), {liq: 0, gl: 0, gf: 0, bn: 0, n: 0});
  if (sel) { nome = `Seção ${sel.s}, zona ${sel.z}`; sub = `${sel.local} · ${sel.bairro} · ${sel.rank}ª no ranking do estado`; d = {...sel, n: 1}; }
  else if (localRows.length) { nome = localRows[0].local; sub = `${localRows[0].bairro} · ${cidade?.nome ?? ''}`; d = soma(localRows); }
  else if (cidade) { nome = cidade.nome; sub = S.uf; d = {...cidade}; }
  else if (S.uf) { nome = S.uf === 'ZZ' ? 'Exterior' : S.uf; sub = 'Estado'; d = {...ufRow.get(S.uf)}; }
  else { nome = 'Brasil'; sub = 'Todos os estados e o exterior'; d = {...soma(ufs), ...brasil}; }
  const saldo = d.gl - d.gf, mil = d.liq ? 1000 * saldo / d.liq : NaN;
  box.append(el('h2', null, nome), el('p', 'sub', `${sub} · ${fmtInt.format(d.n)} ${d.n === 1 ? 'seção' : 'seções'}`));
  if (S.uf && !cidade && !sel && !localRows.length) governador(box, ufRow.get(S.uf));
  box.appendChild(el('h3', 'sec-tit', 'Transferência no 2º turno de 2026'));
  const nums = el('div', 'numeros');
  [['Votos líquidos', fmtInt.format(d.liq), ''], ['Ganho de Lula', fmtSig.format(d.gl), 'pos'], ['Ganho de Flávio', fmtSig.format(d.gf), 'neg']].forEach(([k, v, c]) => {
    const x = el('div'); x.append(el('span', 'k', k), el('span', 'v ' + c, v)); nums.appendChild(x);
  });
  box.appendChild(nums);
  if (d.liq > 0 && d.gl >= 0 && d.gf >= 0 && d.bn >= 0) {
    const bar = el('div', 'barra');
    [[d.gl, '--lula'], [d.gf, '--flavio'], [d.bn, '--neutro']].forEach(([v, c]) => { const i = el('i'); i.style.width = (100 * v / d.liq) + '%'; i.style.background = `var(${c})`; bar.appendChild(i); });
    const leg = el('div', 'legenda-barra');
    [['Lula', d.gl, '--lula'], ['Flávio', d.gf, '--flavio'], ['branco/nulo', d.bn, '--neutro']].forEach(([n, v, c]) => { const s = el('span', null, `${n} ${fmtInt.format(Math.round(1000 * v / d.liq))}`); s.style.setProperty('--c', `var(${c})`); leg.appendChild(s); });
    box.append(bar, leg, el('p', 'nota', 'a cada 1000 votos líquidos'));
  } else {
    box.appendChild(el('p', 'nota', `Brancos e nulos no 2º turno: ${fmtInt.format(d.bn)}. ${d.gl < 0 || d.gf < 0 ? 'Um ganho negativo quer dizer menos votos que no 1º turno.' : ''}`));
  }
  const dest = el('p', 'destaque');
  dest.append('Transferência líquida: ', el('b', sinal(saldo), `${fmtSig.format(saldo)} votos`), ` para ${quem(saldo)}`);
  if (Number.isFinite(mil)) dest.append(` (saldo ${fmtMil.format(mil)} a cada 1000 líquidos)`);
  box.appendChild(dest);
  if (d.gl >= 0 && d.gf >= 0 && d.gl + d.gf > 0) {
    const p = el('p', 'destaque');
    p.append('Dos votos líquidos que foram para um candidato, ', el('b', d.gl >= d.gf ? 'pos' : 'neg', pctFmt(100 * d.gl / (d.gl + d.gf))), ' foram para Lula');
    box.appendChild(p);
  } else if (d.gl > 0 || d.gf > 0) {
    box.appendChild(el('p', 'destaque', d.gl > 0 ? `Só Lula ganhou votos entre os turnos; Flávio perdeu ${fmtInt.format(-d.gf)}.` : `Só Flávio ganhou votos entre os turnos; Lula perdeu ${fmtInt.format(-d.gl)}.`));
  }
  if (!cidade) historico(box, d, cidade, ufRow);
  if (+d.inst) box.appendChild(el('p', 'aviso', 'Base instável: o comparecimento caiu e sobraram poucos votos líquidos; a escala por 1000 exagera.'));
}

function governador(box, u) {
  if (!u?.gov26_nome) return;
  const g = el('div', 'gov');
  const tag = el('span', 'tag', u.gov26_partido); tag.style.setProperty('--c', `var(${COR_BLOCO[BLOCO_DE.get(u.gov26_partido) ?? 'centro']})`);
  const l = el('div', 'pref-linha'); l.append(el('b', 'gov-nome', u.gov26_nome), tag);
  g.append(el('span', 'k', 'Governador eleito em 2026'), l,
    el('p', 'nota', `${fmtPct.format(u.gov26_pct)}% dos votos válidos no ${u.gov26_turno}º turno` + (u.gov26_vice ? ` · vice: ${u.gov26_vice} (${u.gov26_vice_partido})` : '')),
    el('p', 'nota', `${u.gov26_turno === 2 ? 'Adversário no 2º turno' : '2º colocado'}: ${u.gov26_2nome} (${u.gov26_2partido}) ${fmtPct.format(u.gov26_2pct)}%` +
      (u.gov22_nome ? ` · em 2022: ${u.gov22_nome} (${u.gov22_partido})` : '')));
  box.appendChild(g);
}

// no card (tabela), box é o corpo do card e o cabeçalho é montado em cardCidade
function cidadeSimples(c, box = $('resumo'), noCard = false) {
  box.replaceChildren();
  if (!noCard) box.append(el('h2', null, c.nome), el('p', 'sub', S.uf));
  const bloco = (titulo) => { const b = el('div', 'bloco'); b.appendChild(el('h3', 'sec-tit', titulo)); box.appendChild(b); return b; };
  const tagPart = (sg, txt) => { const t = el('span', 'tag', txt ?? sg); t.style.setProperty('--c', `var(${COR_BLOCO[BLOCO_DE.get(sg) ?? 'centro']})`); return t; };

  // 1. prefeito
  const bp = bloco('Prefeito eleito em 2024');
  const dataBR = (d) => d.split('-').reverse().join('/');
  if (c.pref24_nome) {
    const l = el('div', 'pref-linha'); l.append(el('b', 'pref-nome', c.pref24_nome), tagPart(c.pref24_partido));
    bp.append(l, el('p', 'nota', c.pref24_suplementar ? `Eleito na eleição suplementar de ${dataBR(c.pref24_suplementar)}`
      : c.pref24_pct != null ? `${fmtPct.format(c.pref24_pct)}% dos votos válidos no ${c.pref24_turno}º turno` : ''));
  } else if (c.pref24_1nome) {
    const l = el('div', 'pref-linha'); l.append(el('b', 'pref-nome', c.pref24_1nome), tagPart(c.pref24_1partido));
    bp.append(l, el('p', 'aviso', `Mais votado em 2024 (${fmtPct.format(c.pref24_pct)}% dos válidos), mas o TSE ainda não registra eleito: resultado sub judice ou eleição anulada.`));
  } else bp.appendChild(el('p', 'nota', 'Não houve eleição para prefeito em 2024.'));

  // 2. vereadores por partido
  const bv = bloco(`Vereadores eleitos em 2024${c.ver24_total ? ` · ${c.ver24_total}` : ''}`);
  if (c.ver24_partidos) {
    const lista = el('div', 'partidos');
    c.ver24_partidos.split(',').forEach((x) => { const [sg, n] = x.split(':'); lista.appendChild(tagPart(sg, `${sg} ${n}`)); });
    bv.appendChild(lista);
  } else bv.appendChild(el('p', 'aviso', c.pref24_1nome ? 'O TSE ainda não registra os vereadores eleitos: resultado em recontagem ou sub judice.' : 'Não houve eleição para vereador em 2024.'));

  // 3. 2º turno de 2022
  const b22 = bloco('2º turno de 2022');
  if (c.lv22 != null) {
    const tot = c.lv22 + c.bv22;
    const t = el('table', 'comp');
    const cab = el('tr'); ['', 'votos', '%'].forEach((x) => cab.appendChild(el('th', null, x))); t.appendChild(cab);
    [['Lula', c.lv22, 'pos'], ['Bolsonaro', c.bv22, 'neg']].forEach(([n, v, cl]) => {
      const tr = el('tr'); tr.append(el('th', null, n), el('td', null, fmtInt.format(v)), el('td', cl, fmtPct.format(100 * v / tot) + '%')); t.appendChild(tr);
    });
    b22.appendChild(t);
  } else b22.appendChild(el('p', 'nota', 'Município sem votação em 2022 (criado depois).'));

  // 4. 2026: 1º e 2º turno entre Lula e Flávio
  const b26 = bloco('2026 · Lula × Flávio');
  const l2 = c.lv1 + c.gl, f2 = c.fv1 + c.gf, val1 = c.lv1 + c.fv1 + c.ov1, val2 = l2 + f2;
  const t26 = el('table', 'comp');
  const cab = el('tr'); ['', '1º turno', '', '2º turno', ''].forEach((x) => cab.appendChild(el('th', null, x))); t26.appendChild(cab);
  [['Lula', c.lv1, l2, 'pos'], ['Flávio', c.fv1, f2, 'neg']].forEach(([n, v1, v2, cl]) => {
    const tr = el('tr'); tr.append(el('th', null, n), el('td', null, fmtInt.format(v1)), el('td', cl, fmtPct.format(100 * v1 / val1) + '%'),
      el('td', null, fmtInt.format(v2)), el('td', cl, fmtPct.format(100 * v2 / val2) + '%'));
    t26.appendChild(tr);
  });
  b26.append(t26, el('p', 'nota', '% dos votos válidos de cada turno (no 1º turno, entre todos os candidatos).'));

  // 5. votos líquidos, só com as diferenças entre os turnos: outros candidatos + (brancos/nulos 1º − 2º) + (comparecimento 2º − 1º).
  //    Comparecimento, não abstenção: a abstenção também muda com o número de aptos entre os turnos.
  //    = ganho de Lula + ganho de Flávio
  const dbn = c.bn1 - c.bn, dec = c.gl + c.gf;
  const bl = bloco(`Votos líquidos em disputa · ${fmtInt.format(dec)}`);
  const tabela = (titulo, linhas) => {
    const t = el('table', 'comp');
    const h = el('tr'); h.append(el('th', null, titulo), el('th', null, '')); t.appendChild(h);
    linhas.forEach(([k, v, cl]) => { const tr = el('tr'); tr.append(el('th', null, k), el('td', cl ?? '', v)); t.appendChild(tr); });
    return t;
  };
  bl.appendChild(tabela('De onde vieram', [
    ['Outros candidatos no 1º turno', fmtSig.format(c.ov1)],
    [`Brancos e nulos ${dbn >= 0 ? 'caíram' : 'subiram'} (${fmtInt.format(c.bn1)} → ${fmtInt.format(c.bn)})`, fmtSig.format(dbn)],
    [`Comparecimento ${c.dcomp >= 0 ? 'subiu' : 'caiu'} (${fmtInt.format(c.comp2 - c.dcomp)} → ${fmtInt.format(c.comp2)})`, fmtSig.format(c.dcomp)],
    ['Total', fmtInt.format(dec), 'total']]));
  bl.appendChild(tabela('Para onde foram', [['Lula', fmtSig.format(c.gl), 'pos'], ['Flávio', fmtSig.format(c.gf), 'neg'], ['Total', fmtInt.format(dec), 'total']]));
  bl.appendChild(el('p', 'nota', 'Diferenças entre o 1º e o 2º turno; um valor negativo tira votos da conta. Votos anulados pelo TSE (candidato 28) contam como nulos.'));
  const p = el('p', 'destaque');
  p.append('Transferência líquida: ', el('b', sinal(c.saldo), `${fmtSig.format(c.saldo)} votos`), ` para ${quem(c.saldo)}`);
  if (c.gl >= 0 && c.gf >= 0 && dec > 0) p.append(` · ${pctFmt(100 * c.gl / dec)} dos votos decididos foram para Lula`);
  else if (c.gl > 0 || c.gf > 0) p.append(c.gl > 0 ? ` · só Lula ganhou votos; Flávio perdeu ${fmtInt.format(-c.gf)}` : ` · só Flávio ganhou votos; Lula perdeu ${fmtInt.format(-c.gl)}`);
  bl.appendChild(p);
  if (+c.inst) bl.appendChild(el('p', 'aviso', 'Base instável: a abstenção subiu e sobraram poucos votos líquidos.'));

  if (noCard) return;
  const ver = el('button', 'link', 'Ver as seções desta cidade'); ver.type = 'button';
  ver.onclick = () => ir({uf: S.uf, cd: S.cd, sec: '1'});
  box.appendChild(ver);
}

function historico(box, d, cidade, ufRow) {
  if (d.l22 == null && d.i24 == null) return;
  const h = el('div', 'hist');
  h.appendChild(el('h3', 'sec-tit', 'Comparação com 2022 e posicionamento'));
  const t = el('table', 'comp');
  const cab = el('tr'); ['', '2022', '2026'].forEach((x) => cab.appendChild(el('th', null, x))); t.appendChild(cab);
  const p26 = METRICA.pct.v(d), t22 = decidTxt(d.gl22, d.gb22, 'Bolsonaro'), t26 = decidTxt(d.gl, d.gf, 'Flávio');
  const lin = (rot, a, b, cls) => { const tr = el('tr'); tr.appendChild(el('th', null, rot)); [a, b].forEach((v, i) => tr.appendChild(el('td', cls?.[i] ?? '', v))); t.appendChild(tr); };
  const f = (v, fn) => (v == null || !Number.isFinite(+v) ? '—' : fn(+v));
  lin('Lula no 2º turno', f(d.l22, pctFmt), f(d.l26, pctFmt), [d.l22 >= 50 ? 'pos' : 'neg', d.l26 >= 50 ? 'pos' : 'neg']);
  lin('Adversário', 'Bolsonaro', 'Flávio');
  lin('Votos líquidos', f(d.liq22, (v) => fmtInt.format(v)), f(d.liq, (v) => fmtInt.format(v)));
  lin('Ganho de Lula', f(d.gl22, (v) => fmtSig.format(v)), f(d.gl, (v) => fmtSig.format(v)));
  lin('Ganho do adversário', f(d.gb22, (v) => fmtSig.format(v)), f(d.gf, (v) => fmtSig.format(v)));
  lin('% dos decididos p/ Lula', t22.txt, t26.txt, [t22.cls, t26.cls]);
  h.appendChild(t);

  if (d.i24 != null) {
    const b = el('div', 'barra');
    [[d.esq24, '--lula'], [d.cen24, '--neutro'], [d.dir24, '--flavio']].forEach(([v, c]) => { const i = el('i'); i.style.width = (+v || 0) + '%'; i.style.background = `var(${c})`; b.appendChild(i); });
    const leg = el('div', 'legenda-barra');
    [['esquerda', d.esq24, '--lula'], ['centro', d.cen24, '--neutro'], ['direita', d.dir24, '--flavio']].forEach(([n, v, c]) => { const s = el('span', null, `${n} ${f(v, pctFmt)}`); s.style.setProperty('--c', `var(${c})`); leg.appendChild(s); });
    h.append(el('p', 'k2', 'Voto em vereador 2024, por bloco de partidos'), b, leg);
    const ip = el('p', 'destaque');
    ip.append('Índice municipal: pelo voto em vereador, o lugar “parece” ', el('b', d.i24 >= 50 ? 'pos' : 'neg', pctFmt(+d.i24)), ' Lula');
    if (d.l26 != null) { const dif = d.l26 - d.i24; ip.append(`; no 2º turno de 2026 Lula teve ${pctFmt(+d.l26)} (${ppFmt(dif)}).`); }
    h.appendChild(ip);
  }
  const extras = [];
  extras.forEach((x) => h.appendChild(el('p', 'nota', x)));
  const cat = d.cat ?? (d.l22 != null && d.l26 != null ? (d.l22 >= 50 ? (d.l26 >= 50 ? 'lula_lula' : 'virou_contra') : (d.l26 >= 50 ? 'virou_lula' : 'direita_direita')) : null);
  if (cat) {
    const c = el('p', 'categoria cat-' + cat, CATEGORIA[cat]);
    h.appendChild(c);
    if (cat === 'direita_direita' && p26 >= 80) h.appendChild(el('p', 'nota', 'Votou contra Lula nos dois anos, mas quase todos os votos em disputa no 2º turno de 2026 foram para ele.'));
    if (cat === 'lula_lula' && p26 < 50) h.appendChild(el('p', 'nota', 'Votou em Lula nos dois anos, mas a maior parte dos votos em disputa no 2º turno de 2026 foi para Flávio.'));
  }
  box.appendChild(h);
}

// ---------- tabela: Brasil (linhas = estados) → estado (linhas = cidades); clicar numa cidade abre a cidade no mapa
const NOME_UF = {AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás',
  MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná',
  RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo',
  TO: 'Tocantins', ZZ: 'Exterior'};
// votos em disputa = todo eleitor que não votou em Lula nem em Flávio no 1º turno; % ganho = ganho ÷ votos em disputa
const disputa = (r) => r.ov1 + r.bn1 + r.abst1;
// vencedor do turno (mais votos entre Lula e Flávio): a célula de votos dele ganha a cor do candidato
const vencedor = (r, t) => { const l = t === 1 ? r.lv1 : r.lv1 + r.gl, f = t === 1 ? r.fv1 : r.fv1 + r.gf; return l > f ? 'l' : f > l ? 'f' : ''; };
const clsVenc = (c, r) => (c.venc && vencedor(r, c.venc[0]) === c.venc[1] ? (c.venc[1] === 'l' ? 'venc-l' : 'venc-f') : '');
const pctDe = (v, d) => (d > 0 ? 100 * v / d : NaN);
const fmtPct1 = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
// vereadores 2024: 0 = todo voto em partido de esquerda, 100 = todo em direita, centro conta 50
const escalaVer = (r) => {
  if (r.esq24 == null && r.cen24 == null && r.dir24 == null) return NaN;
  const e = +r.esq24 || 0, c = +r.cen24 || 0, d = +r.dir24 || 0;
  return e + c + d > 0 ? (100 * d + 50 * c) / (e + c + d) : NaN;
};
const validos1 = (r) => r.lv1 + r.fv1 + r.ov1;
// partido do prefeito 2024 (cidade) ou do governador eleito em 2026 (estado); total sem partido
const partidoT = (r) => r.pref24_partido ?? r.pref24_1partido ?? r.gov26_partido ?? '';
const COLS_T = [
  {k: 'nome', t: 'Local', v: (r) => r.nomeT},
  {k: 'lv1', t: 'Lula', v: (r) => r.lv1, g: 1, venc: [1, 'l']},
  {k: 'fv1', t: 'Flávio', v: (r) => r.fv1, g: 1, venc: [1, 'f']},
  {k: 'pl1', t: '% Lula', v: (r) => pctDe(r.lv1, validos1(r)), g: 1, pct: true, cor: 'pos', dica: 'Lula ÷ votos válidos do 1º turno'},
  {k: 'pf1', t: '% Flávio', v: (r) => pctDe(r.fv1, validos1(r)), g: 1, pct: true, cor: 'neg', dica: 'Flávio ÷ votos válidos do 1º turno'},
  {k: 'ov1', t: 'Outros', v: (r) => r.ov1, g: 1},
  {k: 'bn1', t: 'Brancos e nulos', v: (r) => r.bn1, g: 1},
  {k: 'abst1', t: 'Abstenções', v: (r) => r.abst1, g: 1},
  {k: 'disp', t: 'Votos em disputa', v: disputa, g: 2, cls: 'disp', dica: 'Outros + brancos e nulos + abstenções do 1º turno'},
  {k: 'lv2', t: 'Lula', v: (r) => r.lv1 + r.gl, g: 3, venc: [2, 'l']},
  {k: 'fv2', t: 'Flávio', v: (r) => r.fv1 + r.gf, g: 3, venc: [2, 'f']},
  {k: 'gl', t: 'Ganho Lula', v: (r) => r.gl, g: 3, sig: true},
  {k: 'gf', t: 'Ganho Flávio', v: (r) => r.gf, g: 3, sig: true},
  {k: 'saldo', t: 'Lula − Flávio', v: (r) => r.gl - r.gf, g: 3, sig: true, dif: true, dica: 'Ganho de Lula − ganho de Flávio (transferência líquida)'},
  {k: 'pgl', t: '% ganho Lula', v: (r) => pctDe(r.gl, disputa(r)), g: 3, pct: true, dica: 'Ganho de Lula ÷ votos em disputa'},
  {k: 'pgf', t: '% ganho Flávio', v: (r) => pctDe(r.gf, disputa(r)), g: 3, pct: true, dica: 'Ganho de Flávio ÷ votos em disputa'},
  {k: 'part', t: 'Prefeito', v: partidoT, g: 4, txt: true},
  {k: 'ver', t: 'Vereadores', v: escalaVer, g: 4, num1: true, dica: 'Voto em vereador 2024 por bloco: 0 = só esquerda, 50 = centro, 100 = só direita'},
];
const G2 = new Set(['disp', 'lv2', 'part']); // colunas que abrem um grupo (linha à esquerda)
const somaT = (rs) => rs.reduce((a, r) => { ['lv1', 'fv1', 'ov1', 'bn1', 'abst1', 'gl', 'gf'].forEach((k) => (a[k] += r[k])); return a; }, {lv1: 0, fv1: 0, ov1: 0, bn1: 0, abst1: 0, gl: 0, gf: 0});
const semAcento = (t) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
// card da cidade na tabela: o mesmo conteúdo do painel da cidade no mapa
function cardCidade(c) {
  const dlg = $('card-cidade');
  if (!c) { if (dlg.open) dlg.close(); return; }
  const cab = $('card-cab'); cab.replaceChildren();
  const l2 = c.lv1 + c.gl, f2 = c.fv1 + c.gf, v = vencedor(c, 2);
  const tit = el('div'); tit.append(el('h2', null, c.nome), el('p', 'sub', `${NOME_UF[c.uf] ?? c.uf} · ${fmtInt.format(c.n)} seções`));
  cab.appendChild(tit);
  if (v) {
    const sel = el('div', 'selo ' + (v === 'l' ? 'venc-l' : 'venc-f'));
    sel.append(el('span', 'k', 'Venceu o 2º turno'), el('b', null, v === 'l' ? 'Lula' : 'Flávio'), el('span', 'k', pctFmt(100 * Math.max(l2, f2) / (l2 + f2)) + ' dos válidos'));
    cab.appendChild(sel);
  }
  cidadeSimples(c, $('card-corpo'), true);
  $('card-mapa').onclick = () => { dlg.close(); ir({uf: c.uf, cd: String(c.cd), vis: ''}); };
  $('card-secoes').onclick = () => { dlg.close(); ir({uf: c.uf, cd: String(c.cd), sec: '1', vis: ''}); };
  if (!dlg.open) dlg.showModal();
  $('card-corpo').scrollTop = 0;
}
// fechar o card tira a cidade do endereço (lê o endereço atual: "Abrir no mapa" já trocou a página antes do evento chegar)
$('card-cidade').addEventListener('close', () => { const s = lerEstado(); if (s.vis === 'tabela' && s.cd) ir({uf: s.uf}); else if ((s.vis === 'destaques' || s.vis === 'discrepancias') && s.cd) ir({}); });
$('card-cidade').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }); // clique fora fecha

const ordenaLinhas = (rows, col, asc) => [...rows].sort((x, y) => {
  const a = col.v(x), c = col.v(y);
  if (col.k === 'nome' || col.txt) return (!a || !c) ? (!a === !c ? 0 : a ? -1 : 1) : (asc ? 1 : -1) * a.localeCompare(c, 'pt') || x.nomeT.localeCompare(y.nomeT, 'pt');
  const fa = Number.isFinite(a), fc = Number.isFinite(c);
  if (!fa || !fc) return fa === fc ? 0 : fa ? -1 : 1; // sem valor vai para o fim
  return (asc ? a - c : c - a) || x.nomeT.localeCompare(y.nomeT, 'pt');
});
// monta a tabela grande (Tabela e Destaques): linha de total + linhas, cabeçalho ordenável
// extra = {titulo, cols}: grupo de colunas a mais no fim (a primeira abre o grupo)
function montaTabela(t, total, rows, col, asc, noUF, ordenaPor, alvoDe, extra = null) {
  const cols = extra ? [...COLS_T, ...extra.cols.map((c, i) => ({...c, abre: i === 0}))] : COLS_T;
  const g2 = (c) => G2.has(c.k) || c.abre;
  t.replaceChildren();
  const thead = el('thead');
  const h1 = el('tr');
  [['', 1, ''], ['1º turno 2026', 7, ''], ['', 1, 'g2'], ['2º turno 2026', 7, 'g2'], ['Política local', 2, 'g2'], ...(extra ? [[extra.titulo, extra.cols.length, 'g2']] : [])].forEach(([txt, n, c]) => { const th = el('th', 'grupo ' + c, txt); th.colSpan = n; h1.appendChild(th); });
  const h2 = el('tr');
  cols.forEach((c) => {
    const rot = c.k === 'part' && !noUF ? 'Governador 2026' : c.t;
    const th = el('th', (c.k === col.k ? 'ord ' : '') + (g2(c) ? 'g2' : ''), rot + (c.k === col.k ? (asc ? ' ▲' : ' ▼') : ''));
    th.scope = 'col'; th.tabIndex = 0;
    if (c.dica) th.title = c.dica;
    th.setAttribute('aria-sort', c.k === col.k ? (asc ? 'ascending' : 'descending') : 'none');
    const ordena = () => ordenaPor(c.k, c.k === col.k ? (asc ? 'd' : 'a') : c.k === 'nome' || c.txt ? 'a' : 'd');
    th.onclick = ordena;
    th.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ordena(); } };
    h2.appendChild(th);
  });
  thead.append(h1, h2);
  const tbody = el('tbody');
  const celula = (c, r) => {
    const v = c.v(r);
    if (c.k === 'nome') return el('td', null, v);
    if (c.txt) {
      const td = el('td', g2(c) ? 'g2' : null);
      if (v) { const t = el('span', 'tag', v); t.style.setProperty('--c', `var(${COR_BLOCO[BLOCO_DE.get(v) ?? 'centro']})`); td.appendChild(t); } else td.textContent = '—';
      if (r.pref24_1partido && !r.pref24_partido) td.title = 'Mais votado em 2024; o TSE ainda não registra eleito';
      return td;
    }
    const txt = !Number.isFinite(v) ? '—' : c.pp ? fmtPctS.format(v) + ' p.p.' : c.pct ? fmtPct1.format(v) + '%' : c.num1 ? fmtPct1.format(v) : c.sig ? fmtSig.format(v) : fmtInt.format(v);
    const cor = c.cor ? c.cor : c.dif ? sinal(v) : c.k === 'ver' ? (v > 50 ? 'neg' : v < 50 ? 'pos' : '') :
      c.sig || c.pct ? (v < 0 ? 'perda' : v > 0 ? (c.k === 'gl' || c.k === 'pgl' ? 'pos' : 'neg') : '') : '';
    const td = el('td', [g2(c) ? 'g2' : '', c.cls ?? '', Number.isFinite(v) ? cor : '', clsVenc(c, r)].join(' ').trim() || null, txt);
    if (c.k === 'ver' && Number.isFinite(v)) td.title = `esquerda ${fmtPct.format(+r.esq24 || 0)}% · centro ${fmtPct.format(+r.cen24 || 0)}% · direita ${fmtPct.format(+r.dir24 || 0)}%`;
    return td;
  };
  const linhaT = (r, ehTotal) => {
    const tr = el('tr', ehTotal ? 'total' : null);
    cols.forEach((c) => tr.appendChild(celula(c, r)));
    if (!ehTotal) {
      tr.tabIndex = 0;
      const alvo = alvoDe(r);
      tr.title = noUF ? 'Ver o resumo da cidade' : 'Ver as cidades do estado';
      tr.onclick = () => ir(alvo);
      tr.onkeydown = (e) => { if (e.key === 'Enter') ir(alvo); };
    }
    return tr;
  };
  tbody.appendChild(linhaT(total, true));
  rows.forEach((r) => tbody.appendChild(linhaT(r)));
  t.append(thead, tbody);
}

let assinTab = '';
function tabela(ufs, ufRow, cids, brasil) {
  const c = S.cd && S.uf ? cids.find((x) => x.uf === S.uf && String(x.cd) === S.cd) : null;
  cardCidade(c);
  const assin = [S.uf, S.col, S.dir, $('tab-busca').value, CELULAR].join('|');
  if (assin === assinTab && $('tab-grande').rows.length) return;
  assinTab = assin;
  const brasilVer = {esq24: brasil.esq24, cen24: brasil.cen24, dir24: brasil.dir24};
  const noUF = !!S.uf;
  // trilha
  const tr = $('tab-trilha'); tr.replaceChildren();
  const b = el('button', null, 'Brasil'); b.type = 'button'; b.onclick = () => ir({});
  if (noUF) tr.append(b, el('i', null, '›'), el('span', 'atual', NOME_UF[S.uf] ?? S.uf)); else tr.appendChild(el('span', 'atual', 'Brasil · por estado'));
  $('tab-busca').hidden = !noUF;
  if (!noUF) $('tab-busca').value = '';

  const linhas = noUF ? cids.filter((c) => c.uf === S.uf).map((c) => ({...c, nomeT: c.nome})) : ufs.map((r) => ({...r, nomeT: CELULAR ? (r.uf === 'ZZ' ? 'Exterior' : r.uf) : `${NOME_UF[r.uf] ?? r.uf}${r.uf === 'ZZ' ? '' : ' (' + r.uf + ')'}`}));
  const total = noUF ? {...ufRow.get(S.uf), nomeT: `Total ${S.uf === 'ZZ' ? 'do exterior' : NOME_UF[S.uf] ?? S.uf}`} : {...somaT(ufs), ...brasilVer, nomeT: 'Total Brasil'};
  if (noUF) total.gov26_partido = null; // o partido do total do estado não é o de uma cidade
  const col = COLS_T.find((c) => c.k === S.col) ?? COLS_T.find((c) => c.k === 'gl');
  const asc = S.dir ? S.dir === 'a' : col.k === 'nome' || !!col.txt;
  const busca = semAcento($('tab-busca').value.trim());
  let rows = busca ? linhas.filter((r) => semAcento(r.nomeT).includes(busca)) : linhas;
  rows = ordenaLinhas(rows, col, asc);

  montaTabela($('tab-grande'), total, rows, col, asc, noUF,
    (k, dir) => ir({uf: S.uf, col: k, dir}),
    (r) => (noUF ? {uf: r.uf, cd: String(r.cd)} : {uf: r.uf}));
  $('tab-nota').textContent = (noUF ? `${fmtInt.format(rows.length)} cidades` : `${rows.filter((r) => r.uf !== 'ZZ').length} unidades da federação e o exterior`) + `${busca ? ` com “${$('tab-busca').value.trim()}”` : ''}. ` +
    '% Lula e % Flávio do 1º turno: sobre os votos válidos. Votos em disputa = outros + brancos e nulos + abstenções do 1º turno. % ganho = ganho ÷ votos em disputa; o resto ficou em branco, nulo ou abstenção no 2º turno, e um ganho negativo é perda de votos. ' +
    `${noUF ? 'Prefeito eleito em 2024' : 'Governador eleito em 2026'}: partido, na cor do bloco. Vereadores: voto em vereador 2024 por bloco de partidos, de 0 (só esquerda) a 100 (só direita), centro conta 50. ` +
    (noUF ? 'Clique numa cidade para ver o resumo dela.' : 'Clique num estado para ver as cidades.');
}

// ---------- destaques: cidades com prefeito do PL, vereadores à direita, em estado com governador de direita (eleito em 2022),
// onde a transferência para Lula foi muito maior que para Flávio e muito maior que em 2022
const CRIT_D = {ver: 70, s26: 30, ds: 60, dg: 30, liq: 200};
const pctLiq = (v, liq) => (liq > 0 ? 100 * v / liq : NaN);
function destacada(c, govDir) {
  if (c.pref24_partido !== 'PL' || !govDir.has(c.uf) || c.inst || c.liq < CRIT_D.liq) return false;
  const s26 = pctLiq(c.gl - c.gf, c.liq), s22 = pctLiq(c.gl22 - c.gb22, c.liq22);
  return Math.round(10 * escalaVer(c)) / 10 >= CRIT_D.ver && // como aparece na coluna Vereadores
    s26 >= CRIT_D.s26 && s26 - s22 >= CRIT_D.ds && pctLiq(c.gl, c.liq) - pctLiq(c.gl22, c.liq22) >= CRIT_D.dg;
}
function destaques(ufs, cids) {
  const c = S.cd && S.uf ? cids.find((x) => x.uf === S.uf && String(x.cd) === S.cd) : null;
  cardCidade(c);
  const govDir = new Set(ufs.filter((u) => BLOCO_DE.get(u.gov22_partido) === 'direita').map((u) => u.uf));
  const sel = cids.filter((x) => destacada(x, govDir)).map((x) => ({...x, nomeT: `${x.nome} (${x.uf})`}));
  const total = {...somaT(sel), nomeT: `Total das ${sel.length} cidades`};
  ['liq', 'gl22', 'gb22', 'liq22'].forEach((k) => (total[k] = sel.reduce((a, r) => a + r[k], 0)));

  const cart = $('dest-cartoes'); cart.replaceChildren();
  const s26 = pctLiq(total.gl - total.gf, total.liq), s22 = pctLiq(total.gl22 - total.gb22, total.liq22);
  [['Cidades', fmtInt.format(sel.length), '', `em ${new Set(sel.map((r) => r.uf)).size} estados`],
    ['Ganho Lula', fmtSig.format(total.gl), 'pos', `2022: ${fmtSig.format(total.gl22)}`],
    ['Ganho Flávio', fmtSig.format(total.gf), 'neg', `Bolsonaro 2022: ${fmtSig.format(total.gb22)}`],
    ['Saldo', fmtPctS.format(s26) + '%', 'pos', `2022: ${fmtPctS.format(s22)}% dos votos líquidos`]].forEach(([k, v, cl, sub]) => {
    const d = el('div', 'cartao'); d.append(el('span', 'k', k), el('span', 'v ' + cl, v)); if (sub) d.appendChild(el('span', 's', sub)); cart.appendChild(d);
  });

  const col = COLS_T.find((x) => x.k === S.col) ?? COLS_T.find((x) => x.k === 'saldo');
  const asc = S.dir ? S.dir === 'a' : col.k === 'nome' || !!col.txt;
  montaTabela($('tab-dest'), total, ordenaLinhas(sel, col, asc), col, asc, true,
    (k, dir) => ir({col: k, dir}),
    (r) => ({uf: r.uf, cd: String(r.cd)}));
  const nomes = [...govDir].sort().map((u) => `${u} (${ufs.find((x) => x.uf === u).gov22_nome.toLowerCase().replace(/(^|\s)\S/g, (m) => m.toUpperCase())}, ${ufs.find((x) => x.uf === u).gov22_partido})`);
  $('dest-nota').textContent = `Critérios: prefeito eleito em 2024 pelo PL; vereadores 2024 com nota ${CRIT_D.ver} ou mais (0 = só esquerda, 100 = só direita); ` +
    `estado com governador de direita eleito em 2022: ${nomes.join(', ')}; ` +
    `saldo de 2026 (ganho de Lula − ganho de Flávio ÷ votos líquidos) de ${CRIT_D.s26}% ou mais; saldo pelo menos ${CRIT_D.ds} pontos acima do de 2022 (Lula × Bolsonaro); ` +
    `fatia do ganho de Lula nos votos líquidos pelo menos ${CRIT_D.dg} pontos acima da de 2022; sem base instável e com ${CRIT_D.liq} votos líquidos ou mais. ` +
    'Votos líquidos = comparecimento do 2º turno − votos de Lula e Flávio no 1º. As colunas são as da Tabela. Clique numa cidade para ver o resumo dela.';
}

// ---------- discrepâncias: cidades cujo 2º turno mais mudou de 2022 (Lula × Bolsonaro) para 2026 (Lula × Flávio)
// margem = % de Lula − % do adversário nos votos válidos do 2º turno; variação = margem 2026 − margem 2022
const margem22 = (r) => pctDe(r.lv22 - r.bv22, r.lv22 + r.bv22);
const margem26 = (r) => { const l = r.lv1 + r.gl, f = r.fv1 + r.gf; return pctDe(l - f, l + f); };
const varMargem = (r) => margem26(r) - margem22(r);
const COLS_D = [
  {k: 'lv22', t: 'Lula 2022', v: (r) => r.lv22},
  {k: 'bv22', t: 'Bolsonaro 2022', v: (r) => r.bv22},
  {k: 'm22', t: 'Margem 2022', v: margem22, pp: true, dif: true, dica: '% de Lula − % de Bolsonaro nos votos válidos do 2º turno de 2022'},
  {k: 'm26', t: 'Margem 2026', v: margem26, pp: true, dif: true, dica: '% de Lula − % de Flávio nos votos válidos do 2º turno de 2026'},
  {k: 'vm', t: 'Variação', v: varMargem, pp: true, dif: true, cls: 'disp', dica: 'Margem 2026 − margem 2022 (positiva = a cidade foi para o lado de Lula)'},
];
const MIN_D = [0, 1000, 5000, 20000, 100000];
function discrepancias(cids, brasil, ufs) {
  const c = S.cd && S.uf ? cids.find((x) => x.uf === S.uf && String(x.cd) === S.cd) : null;
  cardCidade(c);
  const n = +S.n || 0, minV = +S.min || 0;
  const base = cids.filter((x) => x.uf !== 'ZZ' && x.lv22 + x.bv22 >= minV && Number.isFinite(varMargem(x)));
  const porVar = [...base].sort((x, y) => varMargem(y) - varMargem(x));
  const sel = (n ? [...new Set([...porVar.slice(0, n), ...porVar.slice(-n)])] : porVar).map((x) => ({...x, nomeT: `${x.nome} (${x.uf})`}));
  const soma = (rs) => { const t = somaT(rs); ['lv22', 'bv22'].forEach((k) => (t[k] = rs.reduce((a, r) => a + r[k], 0))); return t; };
  const total = {...soma(sel), nomeT: `Total das ${fmtInt.format(sel.length)} cidades`};

  // filtros
  const fn = $('disc-n'), fm = $('disc-min');
  preencherSelect(fn, [['10', '10 de cada lado'], ['25', '25 de cada lado'], ['50', '50 de cada lado'], ['100', '100 de cada lado'], ['0', 'todas']], S.n);
  preencherSelect(fm, MIN_D.map((v) => [String(v), v ? `${fmtInt.format(v)} votos válidos em 2022` : 'qualquer tamanho']), String(minV));
  fn.onchange = () => ir({n: fn.value}); fm.onchange = () => ir({min: fm.value});

  // cartões: Brasil (sem exterior) e os extremos
  const br = soma(ufs.filter((u) => u.uf !== 'ZZ')), vBr = varMargem(br);
  const med = (() => { const v = base.map(varMargem).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : NaN; })();
  const nomeC = (r) => `${r.nome.toLowerCase().replace(/(^|\s)\S/g, (m) => m.toUpperCase())} (${r.uf})`;
  const cart = $('disc-cartoes'); cart.replaceChildren();
  [['Brasil', fmtPctS.format(vBr) + ' p.p.', sinal(vBr), `margem ${fmtPctS.format(margem22(br))} → ${fmtPctS.format(margem26(br))}`],
    ['Cidade mediana', fmtPctS.format(med) + ' p.p.', sinal(med), `${fmtInt.format(base.length)} cidades`],
    ['Mais para Lula', porVar.length ? fmtPctS.format(varMargem(porVar[0])) + ' p.p.' : '—', 'pos', porVar.length ? nomeC(porVar[0]) : ''],
    ['Mais para Flávio', porVar.length ? fmtPctS.format(varMargem(porVar.at(-1))) + ' p.p.' : '—', 'neg', porVar.length ? nomeC(porVar.at(-1)) : '']].forEach(([k, v, cl, sub]) => {
    const d = el('div', 'cartao'); d.append(el('span', 'k', k), el('span', 'v ' + cl, v)); if (sub) d.appendChild(el('span', 's', sub)); cart.appendChild(d);
  });

  const cols = [...COLS_T, ...COLS_D];
  const col = cols.find((x) => x.k === S.col) ?? COLS_D.find((x) => x.k === 'vm');
  const asc = S.dir ? S.dir === 'a' : col.k === 'nome' || !!col.txt;
  montaTabela($('tab-disc'), total, ordenaLinhas(sel, col, asc), col, asc, true,
    (k, dir) => ir({col: k, dir}),
    (r) => ({uf: r.uf, cd: String(r.cd)}),
    {titulo: '2º turno: 2022 × 2026', cols: COLS_D});
  $('disc-nota').textContent = `${n ? `As ${n} cidades que mais foram para o lado de Lula e as ${n} que mais foram para o lado de Flávio` : 'Todas as cidades'}${minV ? ` com ${fmtInt.format(minV)} votos válidos ou mais no 2º turno de 2022` : ''}, sem o exterior. ` +
    'Margem = % de Lula − % do adversário nos votos válidos do 2º turno (Bolsonaro em 2022, Flávio em 2026); variação = margem 2026 − margem 2022, em pontos percentuais. ' +
    `No Brasil a margem foi de ${fmtPctS.format(margem22(br))} para ${fmtPctS.format(margem26(br))} p.p. (${fmtPctS.format(vBr)}); compare cada cidade com esse movimento nacional. ` +
    'As demais colunas são as da Tabela. Cidades pequenas variam mais por acaso; use o mínimo de votos para comparar só as maiores. Clique numa cidade para ver o resumo dela.';
}

// ---------- placar: por estado, quantas cidades tiveram mais ganho de Lula que de Flávio entre os turnos (transferência líquida > 0)
// colunas do placar; g = grupo do cabeçalho (o primeiro de cada grupo abre uma linha à esquerda)
const varPct = (a, b) => (a > 0 ? 100 * (b - a) / a : NaN);
// taxa de abstenção (%) = abstenções ÷ (comparecimento + abstenções) do turno, como o TSE
const taxaAbst = (r, t) => { const ab = t === 1 ? r.abst1 : r.abst2, comp = t === 1 ? r.comp2 - r.dcomp : r.comp2; return pctDe(ab, comp + ab); };
const fmtPct2 = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fmtBps = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0, signDisplay: 'exceptZero'});
const COLS_P = [
  {k: 'nome', t: 'Estado', v: (r) => r.nomeT},
  {k: 'n', t: 'Total', g: 'Cidades', v: (r) => r.n},
  {k: 'l', t: 'Lula', g: 'Cidades', v: (r) => r.l, cor: 'pos'},
  {k: 'f', t: 'Flávio', g: 'Cidades', v: (r) => r.f, cor: 'neg'},
  {k: 'e', t: 'Empate', g: 'Cidades', v: (r) => r.e},
  {k: 'pl', t: 'Divisão', g: 'Cidades', v: (r) => pctDe(r.l, r.n), barra: true, dica: '% das cidades em que Lula ganhou mais votos líquidos'},
  {k: 'l1', t: 'Lula', g: '1º turno', v: (r) => r.lv1, venc: [1, 'l']},
  {k: 'f1', t: 'Flávio', g: '1º turno', v: (r) => r.fv1, venc: [1, 'f']},
  {k: 'b1', t: 'Brancos e nulos', g: '1º turno', v: (r) => r.bn1},
  {k: 'a1', t: 'Abstenções', g: '1º turno', v: (r) => r.abst1},
  {k: 'ta1', t: 'Abstenção %', g: '1º turno', v: (r) => taxaAbst(r, 1), pct: true, semSinal: true, dica: 'Abstenções ÷ eleitorado do 1º turno (comparecimento + abstenções)'},
  {k: 'l2', t: 'Lula', g: '2º turno', v: (r) => r.lv1 + r.gl, venc: [2, 'l']},
  {k: 'f2', t: 'Flávio', g: '2º turno', v: (r) => r.fv1 + r.gf, venc: [2, 'f']},
  {k: 'b2', t: 'Brancos e nulos', g: '2º turno', v: (r) => r.bn},
  {k: 'a2', t: 'Abstenções', g: '2º turno', v: (r) => r.abst2},
  {k: 'ta2', t: 'Abstenção %', g: '2º turno', v: (r) => taxaAbst(r, 2), pct: true, semSinal: true, dica: 'Abstenções ÷ eleitorado do 2º turno (comparecimento + abstenções)'},
  {k: 'bv', t: 'Brancos e nulos', g: 'Variação (2º − 1º turno)', v: (r) => r.bn - r.bn1, sig: true},
  {k: 'bp', t: 'Brancos e nulos %', g: 'Variação (2º − 1º turno)', v: (r) => varPct(r.bn1, r.bn), pct: true},
  {k: 'av', t: 'Abstenções', g: 'Variação (2º − 1º turno)', v: (r) => r.abst2 - r.abst1, sig: true},
  {k: 'ab', t: 'Abstenção (bps)', g: 'Variação (2º − 1º turno)', v: (r) => 10000 * (taxaAbst(r, 2) - taxaAbst(r, 1)) / 100, bps: true, dica: 'Variação da taxa de abstenção em pontos-base (100 bps = 1 ponto percentual)'},
];
const fmtPctS = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero'});
function placar(cids, ufs) {
  const conta = (rs) => ({n: rs.length, l: rs.filter((c) => c.saldo > 0).length, f: rs.filter((c) => c.saldo < 0).length, e: rs.filter((c) => c.saldo === 0).length});
  const VOTOS = ['lv1', 'fv1', 'gl', 'gf', 'bn1', 'bn', 'abst1', 'abst2', 'comp2', 'dcomp'];
  const porUF = new Map();
  cids.forEach((c) => { if (!porUF.has(c.uf)) porUF.set(c.uf, []); porUF.get(c.uf).push(c); });
  const linhas = ufs.filter((u) => u.uf !== 'ZZ').map((u) => ({...u, nomeT: CELULAR ? u.uf : NOME_UF[u.uf], ...conta(porUF.get(u.uf) ?? [])}));
  const total = {nomeT: 'Total Brasil', ...conta(cids.filter((c) => c.uf !== 'ZZ'))};
  VOTOS.forEach((k) => (total[k] = linhas.reduce((a, r) => a + r[k], 0)));

  // cartões do Brasil
  const cart = $('placar-cartoes'); cart.replaceChildren();
  [['Cidades', fmtInt.format(total.n), '', ''], ['Lula ganhou', fmtInt.format(total.l), 'pos', `${fmtPct1.format(pctDe(total.l, total.n))}% das cidades`],
    ['Flávio ganhou', fmtInt.format(total.f), 'neg', `${fmtPct1.format(pctDe(total.f, total.n))}% das cidades`], ['Empate', fmtInt.format(total.e), '', '']].forEach(([k, v, c, s]) => {
    const d = el('div', 'cartao'); d.append(el('span', 'k', k), el('span', 'v ' + c, v)); if (s) d.appendChild(el('span', 's', s)); cart.appendChild(d);
  });

  const col = COLS_P.find((c) => c.k === S.col) ?? COLS_P.find((c) => c.k === 'pl');
  const asc = S.dir ? S.dir === 'a' : col.k === 'nome';
  linhas.sort((x, y) => (col.k === 'nome' ? (asc ? 1 : -1) * x.nomeT.localeCompare(y.nomeT, 'pt') : (asc ? col.v(x) - col.v(y) : col.v(y) - col.v(x)) || x.nomeT.localeCompare(y.nomeT, 'pt')));

  const abre = (c, i) => c.g && COLS_P[i - 1]?.g !== c.g;
  const t = $('tab-placar'); t.replaceChildren();
  const thead = el('thead'), h1 = el('tr'), h2 = el('tr');
  h1.appendChild(el('th', 'grupo'));
  COLS_P.forEach((c, i) => {
    if (abre(c, i)) { const th = el('th', 'grupo g2 grp-' + semAcento(c.g).replace(/\s+/g, ''), c.g); th.colSpan = COLS_P.filter((x) => x.g === c.g).length; h1.appendChild(th); }
    const th = el('th', [c.k === col.k ? 'ord' : '', abre(c, i) ? 'g2' : ''].join(' ').trim() || null, c.t + (c.k === col.k ? (asc ? ' ▲' : ' ▼') : ''));
    th.scope = 'col'; th.tabIndex = 0;
    if (c.dica) th.title = c.dica;
    th.setAttribute('aria-sort', c.k === col.k ? (asc ? 'ascending' : 'descending') : 'none');
    const ordena = () => ir({vis: 'placar', col: c.k, dir: c.k === col.k ? (asc ? 'd' : 'a') : c.k === 'nome' ? 'a' : 'd'});
    th.onclick = ordena;
    th.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ordena(); } };
    h2.appendChild(th);
  });
  thead.append(h1, h2);
  const linhaP = (r, cls) => {
    const tr = el('tr', cls);
    COLS_P.forEach((c, i) => {
      const v = c.v(r), g = abre(c, i) ? 'g2' : '';
      if (c.k === 'nome') { tr.appendChild(el('td', null, v)); return; }
      if (c.barra) {
        const td = el('td', 'divisao ' + g), b = el('div', 'mini-barra');
        [[r.l, '--lula'], [r.e, '--neutro'], [r.f, '--flavio']].forEach(([n, cor]) => { const x = el('i'); x.style.width = (100 * n / r.n) + '%'; x.style.background = `var(${cor})`; b.appendChild(x); });
        td.append(b, el('span', 'pos', fmtPct1.format(v) + '%'));
        td.title = `Lula ${fmtInt.format(r.l)} · Flávio ${fmtInt.format(r.f)}${r.e ? ` · empate ${fmtInt.format(r.e)}` : ''}`;
        tr.appendChild(td); return;
      }
      const txt = !Number.isFinite(v) ? '—' : c.bps ? fmtBps.format(v) + ' bps' : c.pct ? (c.semSinal ? fmtPct2 : fmtPctS).format(v) + '%' : c.sig ? fmtSig.format(v) : fmtInt.format(v);
      const cor = c.cor && v ? c.cor : (c.sig || (c.pct && !c.semSinal) || c.bps) && Number.isFinite(v) ? (v > 0 ? 'sobe' : v < 0 ? 'desce' : '') : '';
      tr.appendChild(el('td', [g, cor, clsVenc(c, r)].join(' ').trim() || null, txt));
    });
    return tr;
  };
  const tbody = el('tbody');
  linhas.forEach((r) => {
    const tr = linhaP(r);
    tr.tabIndex = 0; tr.title = 'Ver as cidades do estado na tabela';
    tr.onclick = () => ir({uf: r.uf, vis: 'tabela', col: 'saldo', dir: 'd'});
    tr.onkeydown = (e) => { if (e.key === 'Enter') tr.onclick(); };
    tbody.appendChild(tr);
  });
  const tfoot = el('tfoot');
  tfoot.appendChild(linhaP(total, 'total'));
  t.append(thead, tbody, tfoot);
  const zc = conta(cids.filter((c) => c.uf === 'ZZ'));
  $('placar-nota').textContent = 'Lula ganhou = a cidade deu mais ganho de votos a Lula que a Flávio entre o 1º e o 2º turno (transferência líquida positiva); Flávio ganhou = o contrário. ' +
    'Votos, brancos e nulos e abstenções somam todas as seções do estado e batem com o resultado oficial do TSE; variação = 2º turno − 1º turno; a taxa de abstenção é sobre o eleitorado de cada turno e a variação dela vai em pontos-base (100 bps = 1 ponto percentual). ' +
    `O total é do Brasil sem o exterior (exterior: ${fmtInt.format(zc.n)} cidades, Lula ganhou em ${fmtInt.format(zc.l)}, Flávio em ${fmtInt.format(zc.f)}). Clique num estado para ver as cidades.`;
}

const LOTE = 1000;
function ranking({ufs, cids, cidUF, escopo, cidRow, cidade}) {
  const ul = $('lista'); ul.replaceChildren();
  const rk = nivelRk(), soAgr = rk === 'secoes' && SO_AGREGADO.includes(S.ord);
  const M = soAgr ? METRICA.votos : METRICA[S.ord] ?? METRICA.votos, min = soAgr ? 0 : minimo(rk);
  const cat = rk === 'secoes' ? '' : S.cat;
  const semInst = soAgr ? S.inst === '0' : semInstaveis();

  // controles
  preencherSelect($('sel-rk'), S.cd ? [['', 'Seções']] : S.uf ? [['', 'Cidades'], ['secoes', 'Seções']] : [['', 'Estados'], ['cidades', 'Cidades']],
    S.cd ? '' : S.uf ? (S.rk === 'secoes' ? 'secoes' : '') : S.rk === 'cidades' ? 'cidades' : '');
  $('sel-rk').disabled = !!S.cd;
  $('sel-ord').value = S.ord;
  preencherSelect($('sel-min'), MINIMOS.map((v) => [String(v), v ? `≥ ${fmtInt.format(v)} ${M.baseNome}` : 'sem mínimo']), String(min));
  if (!MINIMOS.includes(min)) $('sel-min').value = '0';
  $('chk-inst').checked = !semInst;
  $('sel-cat').value = cat;
  $('sel-cat').disabled = rk === 'secoes';
  [...$('sel-ord').querySelectorAll('optgroup option')].forEach((o) => (o.disabled = rk === 'secoes'));

  // linhas do nível
  let linhas, nome, alvo, onde, det, chave;
  const detBase = (r) => `${fmtInt.format(r.liq)} líquidos · Lula ${fmtSig.format(r.gl)} · Flávio ${fmtSig.format(r.gf)} · branco/nulo ${fmtInt.format(r.bn)}` +
    (rk !== 'secoes' && S.ord !== 'pct' && Number.isFinite(METRICA.pct.v(r)) ? ` · ${fmtPct.format(METRICA.pct.v(r))}% p/ Lula` : '') + (S.ord !== 'votos' ? ` · ${fmtSig.format(r.saldo)} votos` : '') +
    (rk !== 'secoes' && r.l22 != null ? ` · Lula 2ºT ${fmtPct.format(r.l22)}% (2022) → ${fmtPct.format(r.l26)}% (2026)` : '') + (r.i24 != null ? ` · índice municipal ${fmtPct.format(r.i24)}%` : '');
  if (rk === 'estados') {
    linhas = ufs; nome = (r) => (r.uf === 'ZZ' ? 'Exterior (ZZ)' : r.uf); onde = (r) => `${fmtInt.format(r.n)} seções`; alvo = (r) => ({uf: r.uf}); chave = () => false;
  } else if (rk === 'cidades') {
    linhas = S.uf ? cidUF : cids; nome = (r) => `${r.nome}${S.uf ? '' : ' · ' + r.uf}`; onde = (r) => `${fmtInt.format(r.n)} seções`; alvo = (r) => ({uf: r.uf, cd: String(r.cd)}); chave = () => false;
  } else {
    linhas = escopo; nome = (r) => `Seção ${r.s} · zona ${r.z}`; onde = (r) => `${r.local} · ${r.bairro}${cidade ? '' : ' · ' + (cidRow.get(String(r.cd))?.nome ?? '')}`;
    alvo = (r) => ({uf: S.uf, cd: String(r.cd), sec: '1', local: S.local, secao: r.key}); chave = (r) => r.key === S.secao;
  }
  const base = (r) => (M.base === 'dec' ? decididos(r) : M.base === 'dec22' ? decididos22(r) : M.base === 'dec2' ? Math.min(decididos(r), decididos22(r)) : r.liq);
  const total = linhas.length;
  let lista = linhas.map((r) => ({r, v: M.v(r)})).filter(({r, v}) => Number.isFinite(v) && (!min || base(r) >= min) && !(semInst && +r.inst) && (!cat || r.cat === cat));
  lista.sort((a, b) => b.v - a.v || b.r.saldo - a.r.saldo);

  const nomeNivel = {estados: 'Estados', cidades: 'Cidades', secoes: 'Seções'}[rk];
  const ondeTit = rk === 'estados' || (rk === 'cidades' && !S.uf) ? 'do Brasil' : S.local ? 'deste local' : cidade ? `de ${cidade.nome}` : S.uf === 'ZZ' ? 'do exterior' : `de ${S.uf}`;
  $('rk-titulo').textContent = `${nomeNivel} ${ondeTit}: de Lula → Flávio`;
  const n = lista.length, N = +S.n, lula = lista.filter(({v}) => M.lado(v) > 0).length, fla = lista.filter(({v}) => M.lado(v) < 0).length;
  const fora = total - n;
  $('rk-nota').textContent = `Ordenado por ${M.nome}. ${fmtInt.format(n)} ${nomeNivel.toLowerCase()} · ${fmtInt.format(lula)} do lado de Lula, ${fmtInt.format(fla)} do lado de Flávio` +
    (fora ? ` · ${fmtInt.format(fora)} fora pelo filtro (mínimo${semInst ? ', base instável' : ''}${cat ? ', categoria' : ''} ou sem dado)` : '') + '.' + (soAgr ? ' A comparação com 2022/2024 existe só para cidades e estados; aqui as seções seguem a transferência.' : '');

  const linha = ({r, v}, i) => item({pos: i + 1, nome: nome(r), onde: onde(r), valor: M.fmt(v), lado: M.lado(v), det: detBase(r) + (r.lat === null ? ' · sem coordenada' : ''), alvo: alvo(r), sel: chave(r)});
  let mostradas;
  if (N && n > 2 * N) {
    mostradas = [...lista.slice(0, N), ...lista.slice(n - N)];
    ul.appendChild(el('li', 'lado pos', `${N} mais para Lula`));
    lista.slice(0, N).forEach((x, i) => ul.appendChild(linha(x, i)));
    ul.appendChild(el('li', 'meio', `… ${fmtInt.format(n - 2 * N)} no meio …`));
    ul.appendChild(el('li', 'lado neg', `${N} mais para Flávio (a última é a mais extrema)`));
    lista.slice(n - N).forEach((x, j) => ul.appendChild(linha(x, n - N + j)));
  } else {
    mostradas = lista;
    let feito = 0;
    const mais = () => {
      lista.slice(feito, feito + LOTE).forEach((x, j) => ul.appendChild(linha(x, feito + j)));
      feito += LOTE;
      if (feito < n) { const b = el('li', 'meio'); const bt = el('button', 'link', `Mostrar mais (${fmtInt.format(n - feito)} restantes)`); bt.type = 'button'; bt.onclick = () => { b.remove(); mais(); }; b.appendChild(bt); ul.appendChild(b); }
    };
    mais();
  }
  if (!n) ul.appendChild(el('li', 'meio', 'Nada passa nesse filtro. Diminua o mínimo, inclua as bases instáveis ou mude a categoria.'));
  const s = ul.querySelector('li.sel');
  if (s) s.scrollIntoView({block: 'nearest'});
  return rk === 'secoes' ? mostradas.map(({r}) => r) : [];
}
function item({pos, nome, onde, valor, lado, det, alvo, sel}) {
  const li = el('li', sel ? 'sel' : null);
  li.tabIndex = 0;
  li.append(el('span', 'pos-n', fmtInt.format(pos) + 'º'));
  const meio = el('div'); meio.append(el('div', 'nome', nome), el('div', 'onde', onde)); li.appendChild(meio);
  li.append(el('span', 'val ' + sinal(lado), valor), el('span', 'det', det));
  li.onclick = () => ir(alvo);
  li.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ir(alvo); } };
  return li;
}

// Pontos crescem ao aproximar: a partir do zoom 12, dobram a cada 2 níveis (até 3x)
const fatorZoom = () => Math.max(1, Math.min(3, 2 ** ((mapa.getZoom() - 12) / 2)));
mapa.on('zoomend', () => camPts.eachLayer((m) => { if (m.raioBase) m.setRadius(m.raioBase * fatorZoom()); }));

function desenharMapa({br, ufs, ufRow, cidUF, cidRow, geoUF, secs, daCidade, escopo, sel, mostradas}) {
  // cor de estados e municípios: % dos decididos (centrada em 50%) quando é a ordenação; senão saldo a cada 1000
  // cor de estados e municípios = métrica da ordenação (transferência em votos usa o saldo a cada 1000)
  const MC = S.ord === 'votos' ? METRICA.mil : METRICA[S.ord] ?? METRICA.mil;
  // índice municipal dentro de um estado: centrado na média do estado (no Brasil todo, em 50%)
  const relativo = MC === METRICA.i24 && S.uf && ufRow.get(S.uf)?.i24 != null;
  const centro = relativo ? +ufRow.get(S.uf).i24 : MC.M ? 50 : 0;
  const valCor = (r) => (r ? MC.v(r) - centro : NaN);
  const fixo = relativo ? undefined : MC.M;
  const escalaCor = (M, onde) => escala(M, `${onde}: ${MC.nome}${relativo ? ' (centro = média do estado)' : ''}`, (x) => MC.fmt(x + centro));
  const tipLinhas = (r) => [`Transferência líquida ${fmtSig.format(r.saldo)} votos`, `Decididos para Lula: ${decidTxt(r.gl, r.gf, 'Flávio').txt}`, `Saldo ${fmtMil.format(r.mil)} a cada 1000 · ${fmtInt.format(r.liq)} líquidos`,
    ...(r.l22 != null ? [`Lula 2º turno: ${fmtPct.format(r.l22)}% (2022) → ${fmtPct.format(r.l26)}% (2026)`] : []), ...(r.i24 != null ? [`Índice municipal 2024: ${fmtPct.format(r.i24)}% · esq ${fmtPct.format(r.esq24)}% / dir ${fmtPct.format(r.dir24)}%`] : []),
    ...(r.pref24_nome ? [`Prefeito 2024: ${esc(r.pref24_nome)} (${r.pref24_partido})`] : []), ...(r.gov22_nome ? [`Governador 2022: ${esc(r.gov22_nome)} (${r.gov22_partido})`] : [])];
  // estados
  const Mu = fixo ?? p95(ufs.filter((r) => r.uf !== 'ZZ' && !r.inst).map(valCor));
  if (!camEstados) {
    camEstados = L.geoJSON(br, {renderer: rendPol, pane: 'poligonos'}).addTo(mapa);
    camEstados.eachLayer((l) => {
      const u = l.feature.properties.uf;
      l.bindTooltip(() => tip(u, tipLinhasAtual(ufRow.get(u))), {sticky: true});
      l.on('click', () => ir({uf: u}));
    });
  }
  camEstados.eachLayer((l) => {
    const u = l.feature.properties.uf;
    l.setStyle(!S.uf || S.uf === 'ZZ'
      ? {fillColor: cor(valCor(ufRow.get(u)), Mu), fillOpacity: 0.75, color: '#fff', weight: 1}
      : u === S.uf ? {fillOpacity: 0, color: css('--fg'), weight: 1.5} : {fillColor: css('--neutro'), fillOpacity: 0.35, color: '#fff', weight: 0.8});
  });

  // municípios do estado
  if (camMunUF !== S.uf) {
    if (camMun) mapa.removeLayer(camMun);
    camMun = null; camMunUF = S.uf;
    if (geoUF) {
      camMun = L.geoJSON(geoUF, {renderer: rendPol, pane: 'poligonos'}).addTo(mapa);
      camMun.eachLayer((l) => {
        const cd = String(l.feature.properties.cd);
        l.bindTooltip(() => { const c = cidRow.get(cd); return c ? tip(c.nome, tipLinhasAtual(c)) : esc(l.feature.properties.nome); }, {sticky: true});
        l.on('click', () => ir({uf: S.uf, cd}));
      });
    }
  }
  tipLinhasAtual = tipLinhas;
  const Mc = fixo ?? p95(cidUF.filter((c) => !c.inst && c.liq >= 200).map(valCor));
  if (camMun) camMun.eachLayer((l) => {
    const cd = String(l.feature.properties.cd), c = cidRow.get(cd);
    l.setStyle(!S.cd ? {fillColor: cor(valCor(c), Mc), fillOpacity: 0.7, color: '#fff', weight: 0.5}
      : cd === S.cd ? {fillColor: cor(valCor(c), Mc), fillOpacity: modoCidade() ? 0.65 : 0.25, color: css('--fg'), weight: 2.5} : {fillColor: cor(valCor(c), Mc), fillOpacity: 0.12, color: '#fff', weight: 0.4});
  });

  // pontos: na cidade, todos os locais; no estado, os locais das seções do ranking
  camPts.clearLayers();
  let base = [];
  if (S.cd) base = modoCidade() ? [] : daCidade;
  else if (S.uf && S.uf !== 'ZZ') base = mostradas.length > 2000 ? [...mostradas.slice(0, 1000), ...mostradas.slice(-1000)] : mostradas;
  const grupos = new Map();
  base.forEach((r) => { if (r.lat == null) return; if (!grupos.has(r.lk)) grupos.set(r.lk, []); grupos.get(r.lk).push(r); });
  const locs = [...grupos.values()].map((rs) => ({lk: rs[0].lk, rs, lat: rs[0].lat, lon: rs[0].lon, saldo: rs.reduce((a, r) => a + r.saldo, 0)}))
    .sort((a, b) => Math.abs(a.saldo) - Math.abs(b.saldo));
  const Ms = Math.max(1, ...locs.map((l) => Math.abs(l.saldo))), rMax = S.cd ? 8 : 9;
  const raio = (v) => (2.5 + (rMax - 2.5) * Math.sqrt(Math.min(Math.abs(v), Ms) / Ms)) * fatorZoom();
  const destaque = sel ? sel.lk : S.local;
  locs.forEach((l) => {
    const m = L.circleMarker([l.lat, l.lon], {renderer: rendPts, pane: 'pontos', radius: raio(l.saldo), color: '#fff', weight: 1,
      fillColor: l.saldo >= 0 ? css('--lula') : css('--flavio'), fillOpacity: 0.85});
    const r0 = l.rs[0];
    m.bindTooltip(tip(esc(r0.local), [`${esc(r0.bairro)} · ${esc(cidRow.get(String(r0.cd))?.nome ?? '')}`,
      `${l.rs.length} ${l.rs.length > 1 ? 'seções' : 'seção'}${S.cd ? '' : ' no ranking'} · transferência líquida <b>${fmtSig.format(l.saldo)}</b>`,
      `Lula ${fmtSig.format(l.rs.reduce((a, r) => a + r.gl, 0))} · Flávio ${fmtSig.format(l.rs.reduce((a, r) => a + r.gf, 0))}`]), {direction: 'top', offset: [0, -4]});
    m.raioBase = raio(l.saldo) / fatorZoom();
    m.on('click', () => (S.cd ? ir({uf: S.uf, cd: S.cd, sec: '1', local: l.lk}) : ir({uf: S.uf, cd: String(r0.cd), sec: '1', local: l.lk, secao: r0.key})));
    camPts.addLayer(m);
  });
  const alvoPt = destaque && grupos.get(destaque)?.[0];
  if (alvoPt) { const anel = L.circleMarker([alvoPt.lat, alvoPt.lon], {renderer: rendPts, pane: 'pontos', radius: raio(locs.find((l) => l.lk === destaque).saldo) + 5,
    color: css('--fg'), weight: 3, fill: false, interactive: false}); anel.raioBase = anel.getRadius() / fatorZoom(); anel.extra = 5; camPts.addLayer(anel); }

  // legenda
  if (!S.uf || S.uf === 'ZZ') legendaTexto(escalaCor(Mu, 'Estados') + (S.uf === 'ZZ' ? '<br>Exterior: só ranking, sem mapa.' : '<br>Clique num estado.'));
  else legendaTexto(escalaCor(Mc, 'Municípios') + (!locs.length ? '' :
    `<span class="extra"><br><b>Pontos</b>: ${S.cd ? 'locais de votação' : 'locais das seções do ranking'}; tamanho = transferência em votos (maior: ${fmtInt.format(Ms)}).` +
    (S.cd && base.length - locs.reduce((a, l) => a + l.rs.length, 0) ? `<br>${fmtInt.format(base.length - locs.reduce((a, l) => a + l.rs.length, 0))} seções sem coordenada ficam só no ranking.` : '') + '</span>'));

  // enquadramento: só quando muda estado/cidade, ou ao escolher uma seção
  const chave = `${S.uf}|${S.cd}|${S.secao}`;
  if (chave !== enquadrado) {
    const mudouArea = enquadrado == null || enquadrado.split('|').slice(0, 2).join('|') !== `${S.uf}|${S.cd}`;
    enquadrado = chave;
    if (sel && sel.lat != null) {
      if (mudouArea || !mapa.getBounds().pad(-0.1).contains([sel.lat, sel.lon]) || mapa.getZoom() < 14) mapa.flyTo([sel.lat, sel.lon], Math.max(mapa.getZoom(), 15), {duration: 0.6});
    } else if (mudouArea) {
      let b = null;
      if (S.cd && camMun) camMun.eachLayer((l) => { if (String(l.feature.properties.cd) === S.cd) b = l.getBounds(); });
      if (!b && S.cd && locs.length) b = L.latLngBounds(locs.map((l) => [l.lat, l.lon]));
      if (!b && S.uf && S.uf !== 'ZZ') camEstados.eachLayer((l) => { if (l.feature.properties.uf === S.uf) b = l.getBounds(); });
      if (!b) b = camEstados.getBounds();
      mapa.flyToBounds(b, {padding: [20, 20], duration: 0.6});
    }
  }
}

// ---------- controles
$('sel-uf').onchange = (e) => ir({uf: e.target.value});
$('sel-cidade').onchange = (e) => ir({uf: S.uf, cd: e.target.value});
$('sel-secao').onchange = (e) => ir({uf: S.uf, cd: S.cd, sec: '1', local: S.local, secao: e.target.value});
$('sel-n').onchange = (e) => { S.n = e.target.value; ir({uf: S.uf, cd: S.cd, sec: S.sec, local: S.local, secao: S.secao, rk: S.rk}); };
$('sel-cat').onchange = (e) => { S.cat = e.target.value; ir({uf: S.uf, cd: S.cd, sec: S.sec, local: S.local, secao: S.secao, rk: S.rk}); };
$('sel-rk').onchange = (e) => ir({uf: S.uf, rk: e.target.value});
$('sel-ord').onchange = (e) => { S.ord = e.target.value; S.min = ''; S.inst = ''; ir({uf: S.uf, cd: S.cd, sec: S.sec, local: S.local, secao: S.secao, rk: S.rk}); };
$('sel-min').onchange = (e) => { S.min = e.target.value; ir({uf: S.uf, cd: S.cd, sec: S.sec, local: S.local, secao: S.secao, rk: S.rk}); };
$('chk-inst').onchange = (e) => { S.inst = e.target.checked ? '1' : '0'; ir({uf: S.uf, cd: S.cd, sec: S.sec, local: S.local, secao: S.secao, rk: S.rk}); };
$('vis-mapa').onclick = () => ir({uf: S.uf, cd: S.cd, vis: ''});
$('vis-tabela').onclick = () => ir({uf: S.uf, vis: 'tabela'});
$('vis-placar').onclick = () => ir({vis: 'placar', col: '', dir: ''});
$('vis-destaques').onclick = () => ir({vis: 'destaques', col: '', dir: ''});
$('vis-discrepancias').onclick = () => ir({vis: 'discrepancias', col: '', dir: '', min: ''});
$('vis-anomalias').onclick = () => ir({vis: 'anomalias', col: '', dir: ''});
let buscaT = 0;
$('tab-busca').oninput = () => { clearTimeout(buscaT); buscaT = setTimeout(render, 150); };
$('abrir-metodo').onclick = async () => {
  $('metodo').showModal();
  const tb = $('tab-partidos');
  if (tb.dataset.ok) return;
  const ps = await get('dados/partidos.json');
  ps.forEach((p) => { const tr = el('tr'); [p.partido, p.bloco, fmtPct.format(p.nota) + '%', fmtInt.format(p.votos)].forEach((v) => tr.appendChild(el('td', null, v))); tb.appendChild(tr); });
  tb.dataset.ok = '1';
};

if (CELULAR) {
  $('rk-filtros').open = false;
  if (L.Browser.mobile) { $('dica-mapa').hidden = false; setTimeout(() => ($('dica-mapa').hidden = true), 6000); }
}
render().catch((e) => { setStatus('Erro ao carregar os dados'); console.error(e); });
window.addEventListener('unhandledrejection', (e) => { setStatus('Erro ao carregar os dados'); console.error(e.reason); });

// ---------- relatório (relatorio-transferencias.html, gerado por scripts/relatorio_email.py)
let anomFeito = false;
async function relatorioAnomalias() {
  if (anomFeito) return;
  const r = await fetch(`relatorio-transferencias.html?v=${VERSAO}`);
  if (!r.ok) throw new Error(`relatorio-transferencias.html: HTTP ${r.status}`);
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  $('anom').replaceChildren(...doc.body.childNodes);
  anomFeito = true;
}
