// Cards de estado e de cidade (diálogo #card-uf), compartilhados por comparativo.html e modelo.html.
// Blocos: presidencial por turno, votos líquidos (origem e destino), modelo de previsão, outros cargos.
'use strict';
window.Cards = (() => {
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const fmtInt = new Intl.NumberFormat('pt-BR');
  const fmtPct = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const fmtPP = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero'});
  const fmtSig = new Intl.NumberFormat('pt-BR', {signDisplay: 'exceptZero'});
  const num = (v) => (v == null ? NaN : +v);
  const pctDe = (v, d) => (d > 0 ? 100 * v / d : NaN);
  const NOME_UF = {AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás',
    MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná',
    RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins'};
  const n = (v) => (v == null || !Number.isFinite(+v) ? '—' : fmtInt.format(v));
  const pc = (v) => (Number.isFinite(v) ? fmtPct.format(v) + '%' : '—');
  const pp = (v) => (Number.isFinite(v) ? fmtPP.format(v) + ' p.p.' : '—');
  const sg = (v) => (v == null || !Number.isFinite(+v) ? '—' : fmtSig.format(v));
  const cor = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');

  // tabela simples: cabs = rótulos; linhas = [classe, [texto, classe], ...]
  function tabela(cabs, linhas, cls = 'pres') {
    const t = el('table', cls), th = el('thead'), h = el('tr');
    cabs.forEach((x, i) => h.appendChild(el('th', i === 0 ? 'esq' : '', x)));
    th.appendChild(h); t.appendChild(th);
    const tb = el('tbody');
    linhas.forEach(([c, ...cels]) => {
      const tr = el('tr', c || null);
      cels.forEach(([txt, k], i) => tr.appendChild(el('td', (i === 0 ? 'esq ' : '') + (k || ''), txt)));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    const rol = el('div', 'pres-rol'); rol.appendChild(t); return rol;
  }

  // 1) presidencial por turno. cands: [{nome, partido, nr, votos}]
  function blocoPresidencial(cands, t1, t2) {
    const b = el('div');
    b.appendChild(el('h3', 'sec-tit', 'Presidente: 1º e 2º turnos'));
    const linhas = cands.map((c) => {
      const fin = c.nr === 13 ? t2.l : c.nr === 22 ? t2.f : null, g = fin == null ? null : fin - c.votos;
      return [c.nr === 13 ? 'cand-l' : c.nr === 22 ? 'cand-f' : '', [`${c.nome} (${c.partido})`], [n(c.votos)], [pc(pctDe(c.votos, t1.validos)), 'muted'], [n(fin)], [pc(fin == null ? NaN : pctDe(fin, t2.validos)), 'muted'], [sg(g), cor(g)]];
    });
    const lin = (cls, nome, a, pa, b2, pb, d) => [cls, [nome], [n(a)], [pc(pa), 'muted'], [n(b2)], [pc(pb), 'muted'], [sg(d), cor(d)]];
    linhas.push(lin('total', 'Votos válidos', t1.validos, pctDe(t1.validos, t1.comp), t2.validos, pctDe(t2.validos, t2.comp), t2.validos - t1.validos),
      lin('', 'Brancos', t1.brancos, pctDe(t1.brancos, t1.comp), t2.brancos, pctDe(t2.brancos, t2.comp), t2.brancos - t1.brancos),
      lin('', 'Nulos', t1.nulos, pctDe(t1.nulos, t1.comp), t2.nulos, pctDe(t2.nulos, t2.comp), t2.nulos - t1.nulos),
      lin('total', 'Comparecimento', t1.comp, pctDe(t1.comp, t1.aptos), t2.comp, pctDe(t2.comp, t2.aptos), t2.comp - t1.comp),
      lin('', 'Abstenções', t1.abst, pctDe(t1.abst, t1.aptos), t2.abst, pctDe(t2.abst, t2.aptos), t2.abst - t1.abst),
      lin('', 'Aptos', t1.aptos, NaN, t2.aptos, NaN, t2.aptos - t1.aptos));
    b.appendChild(tabela(['Presidente', '1º turno', '%', '2º turno', '%', 'Ganho 2º − 1º'], linhas));
    b.appendChild(el('p', 'card-uf-nota', '% dos candidatos sobre os votos válidos do turno; brancos e nulos sobre o comparecimento; comparecimento e abstenções sobre os aptos.'));
    return b;
  }

  // 2) votos líquidos: origem e destino
  function blocoLiquidos(t1, t2) {
    const outros1 = t1.validos - t1.l - t1.f, dbn = (t1.brancos + t1.nulos) - (t2.brancos + t2.nulos), dabst = t1.abst - t2.abst, dapt = t2.aptos - t1.aptos;
    const gl = t2.l - t1.l, gf = t2.f - t1.f, liq = gl + gf;
    const b = el('div');
    b.appendChild(el('h3', 'sec-tit', `Votos líquidos em disputa no 2º turno: ${fmtInt.format(liq)}`));
    const grid = el('div', 'liq-grid');
    const origem = [
      ['', ['Outros candidatos no 1º turno'], [n(outros1)], [pc(pctDe(outros1, liq)), 'muted']],
      ['', ['Queda de brancos e nulos (1º − 2º)'], [sg(dbn), cor(dbn)], [pc(pctDe(dbn, liq)), 'muted']],
      ['', ['Queda da abstenção (1º − 2º)'], [sg(dabst), cor(dabst)], [pc(pctDe(dabst, liq)), 'muted']],
    ];
    if (dapt) origem.push(['', ['Variação dos aptos (2º − 1º)'], [sg(dapt), cor(dapt)], [pc(pctDe(dapt, liq)), 'muted']]);
    origem.push(['liq', ['Votos líquidos'], [n(liq)], ['100%']]);
    grid.appendChild(tabela(['De onde vieram', 'Votos', '%'], origem));
    grid.appendChild(tabela(['Para onde foram', 'Votos', '%'], [
      ['cand-l', ['Lula'], [sg(gl), cor(gl)], [pc(pctDe(gl, liq)), gl >= gf ? 'pos' : '']],
      ['cand-f', ['Flávio'], [sg(gf), cor(gf)], [pc(pctDe(gf, liq)), gf > gl ? 'neg' : '']],
      ['liq', ['Votos líquidos'], [n(liq)], ['100%']],
    ]));
    b.appendChild(grid);
    b.appendChild(el('p', 'card-uf-nota', 'Votos líquidos = votos dos outros candidatos no 1º turno + queda de brancos e nulos + queda da abstenção entre os turnos (mais a variação dos aptos, quando houve). É o mesmo que o ganho de Lula mais o ganho de Flávio. Valor negativo numa origem significa que brancos e nulos ou a abstenção subiram; votos líquidos negativos significam que um dos dois perdeu mais votos do que o outro ganhou.'));
    return b;
  }

  // 3) modelo: perfil do lugar pela proporção em que votou no 1º turno (presidente e outros cargos). m.x: pres, gov, sen, dfed, dest, outros, perfil, dbn, dabst, outros1
  let META = null;
  function setModelo(meta) { META = meta; }
  function blocoModelo(m) {
    const b = el('div');
    b.appendChild(el('h3', 'sec-tit', 'Modelo: perfil do lugar no 1º turno aplicado aos votos líquidos'));
    if (!m || !m.x || m.x.perfil == null) { b.appendChild(el('p', 'card-uf-nota', 'Sem previsão: faltam dados de algum cargo.')); return b; }
    const o = m.x, pp2 = META ? META.peso_pres : 0.5;
    const comp = [
      ['', ['Presidente, 1º turno: Lula ÷ (Lula + Flávio)'], [pc(num(o.pres))], [`${Math.round(100 * pp2)}%`, 'muted']],
      ['', ['Governador: campo Lula ÷ (campo Lula + campo Flávio)'], [pc(num(o.gov))], ['', 'muted']],
      ['', ['Senador: idem'], [pc(num(o.sen))], ['', 'muted']],
      ['', ['Dep. federal: esquerda ÷ (esquerda + direita)'], [pc(num(o.dfed))], ['', 'muted']],
      ['', ['Dep. estadual: idem'], [pc(num(o.dest))], ['', 'muted']],
      ['total', ['Média dos outros cargos'], [pc(num(o.outros))], [`${Math.round(100 * (1 - pp2))}%`, 'muted']],
      ['liq', ['Perfil do lugar (% Lula)'], [pc(num(o.perfil))], ['100%', 'muted']],
    ];
    b.appendChild(tabela(['Como o lugar votou no 1º turno', '% Lula', 'Peso'], comp));
    b.appendChild(tabela(['Votos líquidos', 'Votos', 'Lula', 'Flávio'], [
      ['', ['Entradas (eliminados; brancos/nulos, abstenção e aptos a menos) → perfil'], [sg(o.entradas)], [sg(Math.round(num(o.perfil) / 100 * o.entradas)), 'pos'], [sg(Math.round((1 - num(o.perfil) / 100) * o.entradas)), 'neg']],
      ['', ['Saídas (brancos/nulos, abstenção ou aptos a mais) → proporção do 1º turno'], [sg(o.saidas)], [sg(m.prev_gl - Math.round(num(o.perfil) / 100 * o.entradas)), 'neg'], [sg(m.prev_gf - Math.round((1 - num(o.perfil) / 100) * o.entradas)), 'neg']],
      ['liq', ['Previsto'], [n(m.liq)], [sg(m.prev_gl), 'pos'], [sg(m.prev_gf), 'neg']],
      ['total', ['Real'], [n(m.liq)], [sg(m.gl), 'pos'], [sg(m.gf), 'neg']],
      ['total', ['Real − previsto'], ['—'], [sg(m.dif_gl), cor(m.dif_gl)], [sg(m.dif_gf), cor(-m.dif_gf)]],
    ]));
    const p = el('p', 'card-uf-nota');
    p.textContent = (m.liq > 0 ? `Em % dos votos líquidos: previsto Lula ${pc(num(m.prev_l))} e Flávio ${pc(num(m.prev_f))}; real Lula ${pc(num(m.real_l))} e Flávio ${pc(num(m.real_f))} (diferença ${pp(num(m.dif_l))} para Lula). ` : `Votos líquidos negativos: a abstenção (ou brancos e nulos) subiu mais do que entraram votos; as porcentagens usam as entradas como base: previsto Lula ${pc(num(m.prev_l))}, real ${pc(num(m.real_l))} (diferença ${pp(num(m.dif_l))}). `) +
      `Votos líquidos = outros candidatos (${n(o.outros1)}) + queda de brancos e nulos (${sg(o.dbn)}) + queda da abstenção (${sg(o.dabst)})${o.dapt ? ` + variação dos aptos (${sg(o.dapt)})` : ''}. ` +
      (m.cidades ? 'Nos estados, os percentuais são a média das cidades ponderada pelos votos líquidos; a previsão é a soma das cidades. ' : '') + 'Nada do 2º turno entra, exceto o total de votos líquidos.';
    b.appendChild(p);
    return b;
  }

  // 4) outros cargos. c: {gl, go, gf, sl, so, sf, df_esq, df_cen, df_dir, df_pt, df_pl, de_...}; gov/sen: [{nome, partido, campo, pct}]
  function blocoCargos(c, gov, sen) {
    const b = el('div');
    b.appendChild(el('h3', 'sec-tit', 'Governador, senador e deputados no 1º turno'));
    const tc = el('table', 'cargos'), th = el('thead'), h = el('tr');
    ['Cargo', 'Campo Lula / esquerda', 'Outros / centro', 'Campo Flávio / direita', 'PT', 'PL'].forEach((x, i) => h.appendChild(el('th', i === 0 ? 'esq' : '', x)));
    th.appendChild(h); tc.appendChild(th);
    const tb = el('tbody');
    [['Governador', c.gl, c.go, c.gf, null, null], ['Senador', c.sl, c.so, c.sf, null, null],
      ['Deputado federal', c.df_esq, c.df_cen, c.df_dir, c.df_pt, c.df_pl], ['Deputado estadual', c.de_esq, c.de_cen, c.de_dir, c.de_pt, c.de_pl]].forEach(([k, a, b2, c2, d, e]) => {
      const tr = el('tr');
      tr.append(el('td', 'esq', k), el('td', 'l', pc(num(a))), el('td', null, pc(num(b2))), el('td', 'f', pc(num(c2))), el('td', null, d == null ? '—' : pc(num(d))), el('td', null, e == null ? '—' : pc(num(e))));
      tb.appendChild(tr);
    });
    tc.appendChild(tb);
    const rol = el('div', 'pres-rol'); rol.appendChild(tc); b.appendChild(rol);
    const chips = (lista, lab) => {
      if (!(lista || []).length) return;
      b.appendChild(el('p', 'chips-tit', lab));
      const d = el('div', 'chips');
      lista.forEach((x) => { const ch = el('span', 'chip ' + (x.campo === 'lula' ? 'l' : x.campo === 'flavio' ? 'f' : '')); ch.append(el('span', null, `${x.nome} (${x.partido})`), el('b', null, fmtPct.format(num(x.pct)) + '%')); d.appendChild(ch); });
      b.appendChild(d);
    };
    chips(gov, 'Candidatos a governador (vermelho = coligação com o PT, azul = com o PL):');
    chips(sen, 'Candidatos a senador:');
    b.appendChild(el('p', 'card-uf-nota', 'Percentuais sobre os votos válidos de cada cargo. Deputados somados pelo partido do candidato ou da legenda nos blocos esquerda, centro e direita.'));
    return b;
  }

  function abre({titulo, sub, t1, t2, cands, cargos, gov, sen, modelo, entradas, acoes}) {
    const dlg = $('card-uf'), cab = $('card-uf-cab'), corpo = $('card-uf-corpo'), rod = $('card-uf-rodape');
    cab.replaceChildren(); corpo.replaceChildren(); rod.replaceChildren();
    const tit = el('div'); tit.append(el('h2', null, titulo), el('p', 'sub', sub)); cab.appendChild(tit);
    const venc = t2.l > t2.f ? 'l' : 'f';
    const selo = el('div', 'selo ' + (venc === 'l' ? 'venc-l' : 'venc-f'));
    selo.append(el('span', 'k', 'Venceu o 2º turno'), el('b', null, venc === 'l' ? 'Lula' : 'Flávio'), el('span', 'k', `${pc(pctDe(Math.max(t2.l, t2.f), t2.l + t2.f))} dos válidos`));
    cab.appendChild(selo);
    corpo.append(blocoPresidencial(cands, t1, t2), blocoLiquidos(t1, t2), blocoModelo(modelo), blocoCargos(cargos, gov, sen));
    (acoes || []).forEach(([txt, fn]) => { const b = el('button', 'link', txt); b.type = 'button'; b.onclick = () => { dlg.close(); fn(); }; rod.appendChild(b); });
    const f = el('form'); f.method = 'dialog'; f.style.margin = '0'; f.appendChild(el('button', 'link', 'Fechar')); rod.appendChild(f);
    if (!dlg.open) dlg.showModal();
    corpo.scrollTop = 0;
  }

  // u: linha de uf.json (com pres, gov, sen, gov_eleito); m: modelo.ufs[uf] ou modelo.brasil
  function estado(u, m, acoes) {
    const p = u.pres, ge = u.gov_eleito;
    abre({titulo: u.uf === 'BR' ? 'Brasil' : `${NOME_UF[u.uf]} (${u.uf})`,
      sub: (ge ? `Governador eleito: ${ge.nome} (${ge.partido}), ${ge.turno === 2 ? '2º turno' : '1º turno'}, ${pc(num(ge.pct))} · ` : '') + `${fmtInt.format(p.t1.aptos)} eleitores aptos`,
      t1: p.t1, t2: p.t2, cands: p.cands, cargos: u, gov: u.gov, sen: u.sen, modelo: m, entradas: null, acoes});
  }
  // c: linha de cidades.json; det: detalhe/<UF>.json .cidades[cd]; nomes: detalhe .nomes; m: linha de cidades_modelo.json
  function cidade(c, det, nomes, m, acoes) {
    const cands = det.cands.map(([nr, votos]) => ({nr, votos, nome: (nomes[nr] || ['?', '?'])[0], partido: (nomes[nr] || ['?', '?'])[1]}));
    abre({titulo: `${c.nome} (${c.uf})`, sub: `${NOME_UF[c.uf]} · ${fmtInt.format(det.t1.aptos)} eleitores aptos` + (c.gov_lider ? ` · governador mais votado: ${c.gov_lider} ${pc(num(c.gov_lider_pct))}` : ''),
      t1: det.t1, t2: det.t2, cands, cargos: c, gov: det.gov, sen: det.sen, modelo: m, entradas: m ? m.x : null, acoes});
  }
  return {estado, cidade, setModelo, NOME_UF};
})();
