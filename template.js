
var DADOS = {{JSON}};
var PALETA = {{PALETA}};
var STATUS_COR = {{STATUS_COR}};
var STATUS_TOKEN = {"Operacional":"--pos","Manuten\u00e7\u00e3o":"--neg",
  "Mobiliza\u00e7\u00e3o":"--alerta","Pendente":"--neutro",
  "Lavador":"--info","Erro Dados":"--roxo"};
function corSem(nome){ var v=getComputedStyle(document.documentElement).getPropertyValue('--'+nome).trim(); return v||null; }
var FONTE = "Inter, 'Segoe UI', Arial, sans-serif";

function cores(){
  var dark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    dark: dark,
    template: dark ? 'plotly_dark' : 'plotly_white',
    texto: dark ? '#e7eef7' : '#22303f',
    grid: dark ? 'rgba(148,167,193,.16)' : '#e8eef6',
    hoverBg: dark ? '#23364f' : '#22303f',
    barAmbar: dark ? 'rgba(96,165,250,.18)' : 'rgba(37,99,235,.15)'
  };
}

Plotly.setPlotConfig({displayModeBar: false, responsive: true});

function cfg(){ return {displayModeBar:false, responsive:true}; }
function baseLayout(h){
  var c = cores();
  return {
    template: c.template,
    font: {family: FONTE, size: 12, color: c.texto},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: {l:8, r:8, t:0, b:8},
    legend: {orientation:'h', yanchor:'bottom', y:1.02, x:.5, xanchor:'center'},
    hoverlabel: {bgcolor:c.hoverBg, bordercolor:'#e3e9f2', font:{color:'#fff', size:13}},
    height: h || 305
  };
}
function fmt(v){ return (v===null||v===undefined) ? '—' : Number(v).toLocaleString('pt-BR'); }
function fmtKm(v){ var s=fmt(v); return s==='—'?s:s+' km'; }

/* ---- tema claro/escuro ------------------------------------------------ */
var tg = document.getElementById('tema');
function aplicarTema(){
  document.documentElement.setAttribute('data-theme', tg.checked ? 'dark' : 'light');
  try { localStorage.setItem('frota_tema', tg.checked ? 'dark':'light'); } catch(e){}
}
try { tg.checked = localStorage.getItem('frota_tema') === 'dark'; } catch(e){}
tg.addEventListener('change', function(){ aplicarTema(); renderizar(); renderConsumo(); });
aplicarTema();

/* ---- seletor de mês ----------------------------------------------------- */
var selMes = document.getElementById('mes');
DADOS.meses.forEach(function(m){ var o=document.createElement('option'); o.value=m; o.textContent=m; selMes.appendChild(o); });
selMes.value = DADOS.meses.indexOf('AGOSTO') >= 0 ? 'AGOSTO' : DADOS.meses[0];
selMes.addEventListener('change', function(){ renderizar(); renderConsumo(); });

/* ---- KPIs --------------------------------------------------------------- */
function renderKpi(d){
  document.getElementById('k1').textContent  = fmtKm(d.kmTotal);
  document.getElementById('k1s').textContent = (d.deltaPct===null||d.deltaPct===undefined)
    ? '—' : ((d.deltaPct>=0?'▲ ':'▼ ')+Math.abs(d.deltaPct).toFixed(1)+'% vs mês anterior');
  document.getElementById('k2').textContent  = fmtKm(DADOS.historico);
  document.getElementById('k2s').textContent = DADOS.meses.length+' meses analisados';
  document.getElementById('k3').textContent  = fmtKm(d.media);
  document.getElementById('k3s').textContent = d.veiculos+' veículos no mês';
  document.getElementById('k4').textContent  = d.emManut;
  document.getElementById('k4s').textContent = 'de '+d.linhas+' linhas no mês';
  document.getElementById('k5').textContent  = d.ativos;
  document.getElementById('k5s').textContent = d.pctOp+'% do mês selecionado';
}

/* ---- resumo executivo (leitura rápida para apresentação) ------------------- */
function renderExec(d){
  var el = document.getElementById('resumoExec');
  if(!el) return;
  var i = DADOS.meses.indexOf(selMes.value);
  var deltaTxt;
  if(d.deltaPct===null || d.deltaPct===undefined){
    deltaTxt = 'primeiro mês da série';
  } else {
    deltaTxt = (d.deltaPct>=0 ? '▲ +' : '▼ ')+Math.abs(d.deltaPct).toFixed(1)+'%'
       + (i>0 ? ' vs '+DADOS.meses[i-1] : '');
  }
  var op = d.ativos===d.linhas ? 'Toda a frota ativa'
           : d.pctOp+'% da frota ativa';
  var mant = d.emManut===1 ? '1 veículo em manutenção'
    : (d.emManut>0 ? d.emManut+' veículos em manutenção'
       : 'sem veículos em manutenção');
  el.innerHTML = '<b>'+selMes.value+'</b>: '+fmtKm(d.kmTotal)+' em '+d.veiculos
    +' veículos ('+deltaTxt+'). '+op+' · média '+fmtKm(d.media)+' por veículo · '+mant+'.';
}

/* ---- tendência (fixa) ---------------------------------------------------- */
function renderTendencia(){
  var meses = DADOS.tendencia.map(function(t){return t.mes;});
  var kms, veic, barCores;
  kms  = DADOS.tendencia.map(function(t){return t.km;});
  veic = DADOS.tendencia.map(function(t){return t.veic;});
  barCores = DADOS.tendencia.map(function(t){ return t.mes===selMes.value ? '#f59e0b' : '#2563eb'; });
  var rotCor = DADOS.tendencia.map(function(t){ return t.mes===selMes.value ? '#1f2937' : '#ffffff'; });
  Plotly.react('g_tend', [
    {type:'bar', x:meses, y:kms, marker:{color:barCores},
     text: kms.map(fmt), textposition:'inside', insidetextanchor:'middle',
     textfont:{size:11, color:rotCor}, cliponaxis:false,
     customdata: veic,
     hovertemplate:'%{x}<br>KM total: <b>%{y:,.0f} km</b><br>%{customdata[0]} veículos<extra></extra>'},
    {type:'scatter', x:meses, y:veic, yaxis:'y2', mode:'lines+markers',
     line:{color:'#14b8a6', width:2.5}, marker:{size:7},
     hovertemplate:'%{x}<br>%{y} veículos<extra></extra>'}
  ], Object.assign(baseLayout(320), {
    yaxis:{title:'km', gridcolor: cores().grid, range:[0, Math.max.apply(null,kms)*1.12]},
    yaxis2:{title:'veículos', overlaying:'y', side:'right', showgrid:false,
            range:[0, Math.max.apply(null,veic)+2]},
    showlegend:true
  }), cfg());
}

/* ---- Top 5 ---------------------------------------------------------------- */
function renderTop5(d){
  var rows = d.top5.slice().sort(function(a,b){ return a[1]-b[1]; });
  if(!rows.length){ Plotly.purge('g_top'); return; }
  Plotly.react('g_top', [{
    type:'bar', x:rows.map(function(r){return r[1];}), y:rows.map(function(r){return r[0];}),
    orientation:'h',
    marker:{color: rows.map(function(_,i){return PALETA[(i+4)%PALETA.length];})},
    text: rows.map(function(r){return fmt(r[1]);}),
    textposition:'outside', cliponaxis:false,
    textfont:{size:11, color: cores().texto},
    hovertemplate:'%{y}: <b>%{x:,.0f} km</b><extra></extra>'
  }], Object.assign(baseLayout(320), {
    showlegend:false, xaxis:{visible:false, range:[0, Math.max.apply(null, rows.map(function(r){return r[1];}))*1.18]},
    yaxis:{automargin:true, tickcolor:'rgba(0,0,0,0)'},
    margin:{l:70, r:24, t:0, b:8}
  }), cfg());
}

/* ---- tipo (pizza) ---------------------------------------------------------- */
function renderTipo(d){
  var ids = ['#2563eb','#f59e0b','#0ea5e9','#10b981'];
  Plotly.react('g_tipo', [{
    type:'pie', labels:d.tipo.map(function(r){return r[0];}),
    values:d.tipo.map(function(r){return r[1];}), hole:.55,
    textinfo:'label+percent', textfont:{color:'#fff', size:11},
    marker:{colors: ids},
    hovertemplate:'%{label}<br><b>%{value:,.0f} km</b> (%{percent})<extra></extra>'
  }], Object.assign(baseLayout(315), {
    showlegend:false,
    annotations:[{text:fmtKm(d.kmTotal), x:.5, y:.5, showarrow:false,
                  font:{size:15, color: cores().texto, family:FONTE}}]
  }), cfg());
}

/* ---- status ----------------------------------------------------------------- */
function renderStatus(d){
  var rows = d.status.slice().sort(function(a,b){ return a[1]-b[1]; });
  if(!rows.length){ Plotly.purge('g_status'); return; }
  Plotly.react('g_status', [{
    type:'bar',
    x:rows.map(function(r){return r[1];}), y:rows.map(function(r){return r[0];}),
    orientation:'h',
    marker:{color: rows.map(function(r){ return STATUS_COR[r[0]] || '#94a3b8'; })},
    text: rows.map(function(r){return fmt(r[1]);}),
    textposition:'outside', cliponaxis:false,
    textfont:{size:11, color: cores().texto},
    hovertemplate:'%{y}<br><b>%{x:,.0f} km</b><extra></extra>'
  }], Object.assign(baseLayout(315), {
    showlegend:false, xaxis:{visible:false, range:[0, Math.max.apply(null, rows.map(function(r){return r[1];}))*1.18]},
    yaxis:{automargin:true, tickcolor:'rgba(0,0,0,0)', tickfont:{size:11}},
    margin:{l:120, r:24, t:0, b:8}
  }), cfg());
}

/* ---- semanal ---------------------------------------------------------------- */
function renderSemanal(d){
  var semanas=['S1','S2','S3','S4','S5'];
  var tot = semanas.map(function(s){ return d.semanal.totais[s]||0; });
  var data = [{type:'bar', x:semanas, y:tot, marker:{color: cores().barAmbar},
               hovertemplate:'%{x}<br>total: <b>%{y:,.0f} km</b><extra></extra>'}];
  d.semanal.tags.forEach(function(tag, i){
    var serie = d.semanal.series[tag];
    data.push({type:'scatter', mode:'lines+markers', x:semanas,
               y:semanas.map(function(s){ return serie[s]||0; }), name:tag,
               line:{width:2.6, color:PALETA[i%PALETA.length]},
               hovertemplate:tag+'<br>%{x}: %{y:,.0f} km<extra></extra>'});
  });
  Plotly.react('g_sem', data, Object.assign(baseLayout(315), {
    xaxis:{automargin:true},
    yaxis:{title:'km', gridcolor: cores().grid, automargin:true},
    barmode:'overlay', showlegend:true,
    margin:{l:16, r:16, t:40, b:40}
  }), cfg());
}

/* ---- tabela semanal --------------------------------------------------------- */
function renderTabelaSem(d){
  document.getElementById('semMes').textContent = selMes.value;
  var linhas = d.semTabela.map(function(r){
    var cls = r[6]===null?'':'num';
    var cel = ['S1','S2','S3','S4','S5'].map(function(_,i){ return '<td>'+fmt(r[i+1])+'</td>'; }).join('');
    return '<tr><td>'+r[0]+'</td>'+cel+'<td>'+fmt(r[6])+'</td></tr>';
  }).join('');
  document.getElementById('tabela_sem').innerHTML =
    '<table class="tab"><thead><tr><th>Veículo</th><th>S1</th><th>S2</th><th>S3</th><th>S4</th><th>S5</th><th>Total no mês</th></tr></thead><tbody>'+linhas+'</tbody></table>';
}

/* ---- tabela detalhada ------------------------------------------------------- */
function renderTabelaDet(d){
  var linhas = d.detalhe.map(function(r){
    var stCor = 'var('+(STATUS_TOKEN[r[9]]||'--neutro')+')';
    var delta = (r[8]===null||r[8]===undefined) ? '<td>—</td>'
      : '<td class="'+(r[8]>=0?'neg':'pos')+'">'+(r[8]>=0?'+':'')+fmt(r[8])+' km</td>';
    return '<tr><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td><td>'+r[3]+'</td><td>'+r[4]+'</td>'
      +'<td>'+fmt(r[5])+'</td><td>'+fmt(r[6])+'</td><td>'+fmt(r[7])+' km</td>'+delta
      +'<td style="color:'+stCor+';font-weight:700;">'+r[9]+'</td></tr>';
  }).join('');

  var totKm = d.detalhe.reduce(function(s,r){ return s+(r[7]||0); }, 0);
  var totDeltaKm = 0;
  var withPrev = d.detalhe.filter(function(r){ return r[8]!==null && r[8]!==undefined; });
  withPrev.forEach(function(r){ totDeltaKm += r[8]||0; });
  var pctKm = null;
  var antKmTotal = null;
  if(d.deltaPct!==null && d.deltaPct!==undefined){
    pctKm = d.deltaPct;
    antKmTotal = d.deltaPct!==0 ? totKm/(1+d.deltaPct/100) : null;
  }
  var totDeltaTxt = (pctKm===null) ? '—'
    : '<span class="'+(pctKm>=0?'neg':'pos')+'">'+(pctKm>=0?'▲ +':'▼ ')+Math.abs(pctKm).toFixed(1)+'%</span>';
  var totDeltaAbs = (antKmTotal===null) ? '—'
    : '<span class="'+(totDeltaKm>=0?'neg':'pos')+'">'+(totDeltaKm>=0?'+':'')+fmt(totDeltaKm)+' km</span>';

  document.getElementById('tabela_det').innerHTML =
    '<table class="tab"><thead><tr><th>Mês</th><th>Veículo</th><th>Tipo</th><th>Modelo</th>'
    +'<th>Placa</th><th>Km inicial</th><th>Km final</th><th>Km no mês</th>'
    +'<th>Δ vs mês anterior</th><th>Status</th></tr></thead><tbody>'+linhas+'</tbody>'
    +'<tfoot><tr><td class="tl" colspan="7">Consolidado total do mês</td>'
    +'<td>'+fmt(totKm)+' km</td><td>'+totDeltaTxt+'</td><td>'+totDeltaAbs+'</td></tr></tfoot></table>';
}

/* ---- consolidado total do mês (KM + CO2 vs mês anterior) -------------------- */
function renderConsolDet(d){
  var el = document.getElementById('consol_det');
  if(!el) return;
  var i = 0;
  DADOS.consumoTend.forEach(function(x,j){ if(x.mes===selMes.value) i=j; });
  var t = DADOS.consumoTend[i];
  var ant = i>0 ? DADOS.consumoTend[i-1] : null;
  var mesAnt = i>0 ? DADOS.meses[i-1] : null;

  var card = function(lbl, val, unit, atual, anterior, fmtAbs){
    var deltaTxt, clsBorda = '';
    if(anterior===undefined || anterior===null || anterior===0){
      deltaTxt = mesAnt ? ('— sem registros em '+mesAnt) : 'primeiro mês da série';
    } else {
      var dAbs = atual - anterior;
      var pct = dAbs/anterior*100;
      var sinal = dAbs>=0 ? '▲' : '▼';
      var cls = dAbs>=0 ? 'neg' : 'pos';
      clsBorda = dAbs>=0 ? ' neg-borda' : '';
      deltaTxt = '<span class="'+cls+'">'+sinal+' '+fmtAbs(Math.abs(dAbs))
        +' ('+sinal+' '+Math.abs(pct).toFixed(1)+'%)</span> vs '+mesAnt;
    }
    return '<div class="kpi'+clsBorda+'"><div class="lbl">'+lbl+'</div>'
      +'<div class="val">'+fmt(val)+' '+unit+'</div><div class="sub">'+deltaTxt+'</div></div>';
  };

  el.innerHTML = card('🛣️ KM total no mês', d.kmTotal, 'km', d.kmTotal, ant?ant.km:null,
        function(v){ return fmt(v)+' km'; })
    + card('⛽ CO₂ total no mês', t?t.total:0, 'kgCO₂e', t?t.total:0, ant?ant.total:null,
        function(v){ return fmt(v)+' kg'; });
}

/* ---- consumo de CO2 da frota (segue o mês selecionado) -------------------- */
function corComb(comb){ return comb==='Diesel' ? 'var(--alerta)' : 'var(--neg)'; }
function corCombHex(comb){ return comb==='Diesel' ? (corSem('alerta')||'#f59e0b') : (corSem('neg')||'#ef4444'); }

function renderConsumo(){
  var tend = DADOS.consumoTend;
  if(!tend || !tend.length) return;
  var mes = selMes.value;
  var i = 0;
  tend.forEach(function(x,j){ if(x.mes===mes) i=j; });
  var t = tend[i];
  var ant = i>0 ? tend[i-1] : null;
  kpisConsumo(t, ant);
  tendConsumo(t);
  veicConsumo(selMes.value);
  tabelaConsumo(selMes.value, ant);
  comparaConsumo(t, ant);
}

/* ---- comparativo mês atual × anterior (KM + CO2) -------------------------- */
function comparaConsumo(t, ant){
  var el = document.getElementById('compConsumo');
  if(!el) return;
  if(!ant){ el.innerHTML = ''; el.style.display='none'; return; }
  el.style.display = '';
  var dKm = t.km - ant.km;
  var dCo2 = t.total - ant.total;
  var pKm = ant.km ? (dKm/ant.km*100) : null;
  var pCo2 = ant.total ? (dCo2/ant.total*100) : null;
  var verb = function(p){ return (p===null) ? '—' : ((p>=0 ? '▲ ' : '▼ ')+Math.abs(p).toFixed(1)+'%'); };
  var cls = function(p){ return (p===null) ? '' : (p>=0 ? 'neg' : 'pos'); };
  el.innerHTML = '<b>🔁 Comparativo '+ant.mes+' → '+t.mes+'</b>: KM '
    +fmtKm(ant.km)+' → '+fmtKm(t.km)+' <span class="'+cls(pKm)+'">'+verb(pKm)+'</span>'
    +' &nbsp;·&nbsp; CO2 '+fmt(ant.total)+' → '+fmt(t.total)+' kg <span class="'+cls(pCo2)+'">'+verb(pCo2)+'</span>'
    +' &nbsp;·&nbsp; veículos '+ant.veic+' → '+t.veic;
}
function kpisConsumo(t, ant){
  var delta = ant ? ((t.delta>=0?'▲ ':'▼ ')+Math.abs(t.delta).toFixed(1)+'% vs '+ant.mes) : '—';
  var litros = (t.litrosD||0)+(t.litrosG||0);
  var pctD = t.total ? (t.diesel/t.total*100) : 0;
  var cards = [
    ['⛽ CO2 do mês', fmt(t.total)+' kgCO₂e', delta],
    ['🛢️ CO2 Diesel', fmt(t.diesel)+' kgCO₂e', Math.round(pctD)+'% das emissões • '+fmt(t.litrosD)+' L'],
    ['⛽ CO2 Gasolina', fmt(t.gasolina)+' kgCO₂e', Math.round(100-pctD)+'% das emissões • '+fmt(t.litrosG)+' L'],
    ['🧯 Litros totais', fmt(litros)+' L', 'combustível no mês'],
    ['🚚 Veículos no mês', t.veic, fmtKm(t.km)+' rodados']
  ];
  document.getElementById('kpis_consumo').innerHTML = cards.map(function(c){
    return '<div class="kpi"><div class="lbl">'+c[0]+'</div><div class="val">'+c[1]+'</div><div class="sub">'+c[2]+'</div></div>';
  }).join('');
}
function tendConsumo(t){
  var meses = DADOS.consumoTend.map(function(x){return x.mes;});
  var d = DADOS.consumoTend.map(function(x){return x.diesel;});
  var g = DADOS.consumoTend.map(function(x){return x.gasolina;});
  var tot = DADOS.consumoTend.map(function(x){return x.total;});
  var del = DADOS.consumoTend.map(function(x){return x.delta;});
  var maxTot = Math.max.apply(null, tot) || 1;
  Plotly.react('g_consumo_tend', [
    {type:'bar', x:meses, y:d, name:'Diesel', marker:{color:'#f59e0b'},
     hovertemplate:'%{x}<br>Diesel: <b>%{y:,.1f} kgCO₂e</b><extra></extra>'},
    {type:'bar', x:meses, y:g, name:'Gasolina', marker:{color:'#ef4444'},
     hovertemplate:'%{x}<br>Gasolina: <b>%{y:,.1f} kgCO₂e</b><extra></extra>'},
    {type:'scatter', x:meses, y:tot, name:'Total', mode:'lines+markers',
     line:{color: cores().texto, width:2.5}, marker:{size:7},
     customdata:del,
     hovertemplate:'%{x}<br>Total: <b>%{y:,.1f} kg</b> (%{customdata[0]:+.1f}%)<extra></extra>'}
  ], Object.assign(baseLayout(320), {
    barmode:'stack', bargap:.3,
    yaxis:{title:'kgCO₂e', gridcolor: cores().grid, range:[0, maxTot*1.2]}
  }), cfg());
}
function veicConsumo(mes){
  document.getElementById('consMes1').textContent = mes;
  var rows = (DADOS.consumo[mes]||[]).slice().sort(function(a,b){ return a[5]-b[5]; })
    .filter(function(r){ return r[5]>0; });
  if(!rows.length){ Plotly.purge('g_consumo_veic'); return; }
  var maxV = Math.max.apply(null, rows.map(function(r){return r[5];}))*1.18;
  Plotly.react('g_consumo_veic', [{
    type:'bar', x:rows.map(function(r){return r[5];}),
    y:rows.map(function(r){return r[0]+' · '+r[1];}), orientation:'h',
    marker:{color: rows.map(function(r){ return corCombHex(r[2]); })},
    text: rows.map(function(r){ return Number(r[5]).toLocaleString('pt-BR',{maximumFractionDigits:1}); }),
    textposition:'outside', cliponaxis:false,
    textfont:{size:11, color: cores().texto},
    hovertemplate:'%{y}<br><b>%{x:,.1f} kgCO₂e</b><extra></extra>'
  }], Object.assign(baseLayout(320), {
    showlegend:false,
    yaxis:{automargin:true, tickcolor:'rgba(0,0,0,0)', tickfont:{size:10.5}},
    xaxis:{visible:false, range:[0, Math.max(maxV, 0.1)]},
    margin:{l:110, r:30, t:0, b:8}
  }), cfg());
}
function tabelaConsumo(mes, ant){
  var rows = (DADOS.consumo[mes]||[]).slice();
  document.getElementById('consMes2').textContent = ant ? (mes+' — comparado a '+ant.mes) : mes;
  var porTag = {};
  (DADOS.consumo[ant?ant.mes:null]||[]).forEach(function(r){ porTag[r[0]]=r[5]; });
  var linhas = rows.map(function(r){
    var dAnt = (r[5]===undefined||r[5]===null) ? null : porTag[r[0]];
    var dKg, dPct;
    if(dAnt===undefined || dAnt===null || dAnt===0){
      dKg = '—'; dPct = '—';
    } else {
      var dv = r[5]-dAnt;
      var cls = dv>=0 ? 'neg' : 'pos';
      dKg = '<span class="'+cls+'">'+(dv>=0?'+':'')+dv.toLocaleString('pt-BR',{maximumFractionDigits:1})+' kg</span>';
      dPct = '<span class="'+cls+'">'+(dv>=0?'+':'')+(dv/dAnt*100).toFixed(1)+'%</span>';
    }
    return '<tr><td>'+r[0]+'</td><td>'+r[1]+'</td><td style="color:'+corComb(r[2])+';font-weight:700;">'+r[2]+'</td>'
      +'<td>'+fmt(r[3])+'</td><td>'+fmt(r[4])+'</td><td>'+fmt(r[5])+'</td>'
      +'<td>'+dKg+'</td><td>'+dPct+'</td></tr>';
  }).join('');
  document.getElementById('tabela_consumo').innerHTML =
    '<table class="tab"><thead><tr><th>Veículo</th><th>Modelo</th><th>Combustível</th>'
    +'<th>Km no mês</th><th>Litros</th><th>CO2 (kg)</th>'
    +'<th>Δ vs mês anterior (kg)</th><th>Δ (%)</th></tr></thead><tbody>'+linhas+'</tbody></table>';
}

/* ---- renderização geral ------------------------------------------------------ */
function renderizar(){
  var d = DADOS.por_mes[selMes.value] || DADOS.por_mes[DADOS.meses[0]];
  renderKpi(d);
  renderExec(d);
  renderTendencia();
  renderTop5(d);
  renderTipo(d);
  renderStatus(d);
  renderSemanal(d);
  renderTabelaSem(d);
  renderTabelaDet(d);
  renderConsolDet(d);
}
renderizar();
renderConsumo();

/* ---- atualização automática (quando servido pelo servir.py) ------------- */
(function(){
  try {
    var sc = sessionStorage.getItem('frota_scroll');
    if(sc !== null){
      sessionStorage.removeItem('frota_scroll');
      setTimeout(function(){ window.scrollTo(0, Number(sc)); }, 400);
    }
  } catch(e){}
  if(location.protocol !== 'http:' && location.protocol !== 'https:') return;
  if(location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return;
  try {
    var ev = new EventSource('/eventos');
    ev.onmessage = function(m){
      if(!m.data) return;
      try { sessionStorage.setItem('frota_scroll', String(window.scrollY)); } catch(e){}
      location.reload();
    };
    ev.onerror = function(){ try { ev.close(); } catch(e){} };
  } catch(e){}
})();
