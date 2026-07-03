let state={routes:[],filtered:[],layers:new Map(),active:null,map:null};
const $=id=>document.getElementById(id);
const fmt=n=>n==null?'—':Number(n).toLocaleString();
function routeColor(r){const g=r.surface?.gravelPct??0; if(g>=85)return '#c6f26b'; if(g>=65)return '#8ccf57'; return '#f2d06b'}
function routeShareUrl(r){const u=new URL(location.href); u.hash=r.id; return u.toString();}
function popupHtml(r){return `<div class="popup"><strong>${r.name}</strong><br>${r.distanceMi} mi · ${r.surface.gravelPct}% gravel est · ${r.driveMinutes} min drive<br><a href="${r.sourceUrl}" target="_blank" rel="noreferrer">source</a> · <a href="${r.gpxUrl}" target="_blank" rel="noreferrer">gpx</a></div>`}
async function init(){
  const data=await fetch('./data/routes.json').then(r=>r.json());
  state.routes=data.routes;
  state.map=L.map('map',{zoomControl:false}).setView([44.96,-93.25],9);
  L.control.zoom({position:'topright'}).addTo(state.map);
  const baseTiles=L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',{
    subdomains:'abcd',
    maxZoom:19,
    detectRetina:true,
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">openstreetmap</a> contributors &copy; <a href="https://carto.com/attributions">carto</a>'
  }).addTo(state.map);
  baseTiles.on('tileerror',()=>console.warn('base map tile failed to load; carto cdn may be temporarily unavailable'));
  L.circleMarker([data.home.lat,data.home.lon],{radius:7,color:'#fff',fillColor:'#c6f26b',fillOpacity:1,weight:2}).addTo(state.map).bindPopup('home area used for drive estimates');
  ['search','drive','gravel','minMiles','maxMiles','sort'].forEach(id=>$(id).addEventListener('input',render));
  render();
  window.addEventListener('resize',()=>setTimeout(refreshMapLayout,120));
  if(window.visualViewport) window.visualViewport.addEventListener('resize',()=>setTimeout(refreshMapLayout,120));
  [150,600,1200,2200].forEach(ms=>setTimeout(refreshMapLayout,ms));
  if(location.hash){const id=location.hash.slice(1); setTimeout(()=>selectRoute(id),180)}
}
function render(){
  const q=$('search').value.trim().toLowerCase(), maxDrive=+$('drive').value, minGravel=+$('gravel').value, minMiles=+$('minMiles').value, maxMiles=+$('maxMiles').value;
  $('driveLabel').textContent=maxDrive; $('gravelLabel').textContent=minGravel;
  let routes=state.routes.filter(r=>r.driveMinutes<=maxDrive && r.distanceMi>=minMiles && r.distanceMi<=maxMiles && (r.surface.gravelPct??0)>=minGravel);
  if(q) routes=routes.filter(r=>[r.name,r.city,r.description,r.source].join(' ').toLowerCase().includes(q));
  const sort=$('sort').value;
  routes.sort((a,b)=> sort==='distance'?a.distanceMi-b.distanceMi:sort==='gravel'?(b.surface.gravelPct-a.surface.gravelPct):sort==='gain'?((b.elevationGainFt||0)-(a.elevationGainFt||0)):a.driveMinutes-b.driveMinutes);
  state.filtered=routes;
  drawMap(routes); drawList(routes); drawStats(routes);
}
function routeBounds(routes){
  const bounds=[];
  routes.forEach(r=>r.coordinates.forEach(c=>bounds.push(c)));
  return bounds;
}
function fitRoutes(routes){
  const bounds=routeBounds(routes);
  if(bounds.length) state.map.fitBounds(bounds,{padding:[30,30],animate:false});
}
function refreshMapLayout(){
  if(!state.map) return;
  state.map.invalidateSize({pan:false});
  if(state.active){
    const layer=state.layers.get(state.active);
    if(layer) state.map.fitBounds(layer.getBounds(),{padding:[40,40],animate:false});
  } else if(state.filtered.length) fitRoutes(state.filtered);
}
function drawMap(routes){
  for(const [id,l] of state.layers){ if(!routes.find(r=>r.id===id)){state.map.removeLayer(l); state.layers.delete(id);} }
  const bounds=[];
  for(const r of routes){
    let layer=state.layers.get(r.id);
    if(!layer){
      layer=L.polyline(r.coordinates,{color:routeColor(r),weight:4,opacity:.8}).bindPopup(popupHtml(r));
      layer.on('click',()=>selectRoute(r.id)); state.layers.set(r.id,layer); layer.addTo(state.map);
    } else { layer.setStyle({color:routeColor(r),weight:state.active===r.id?7:4,opacity:state.active===r.id?1:.8}); }
    r.coordinates.forEach(c=>bounds.push(c));
  }
  if(bounds.length && !state.active) fitRoutes(routes);
}
function drawList(routes){
  const list=$('routeList'); list.innerHTML=''; const tpl=$('routeCardTemplate');
  for(const r of routes){
    const node=tpl.content.cloneNode(true); const card=node.querySelector('.route-card'); card.dataset.id=r.id; if(state.active===r.id)card.classList.add('active');
    node.querySelector('.route-name').textContent=r.name;
    node.querySelector('.route-desc').textContent=r.description;
    node.querySelector('.route-facts').innerHTML=`<div><dt>drive</dt><dd>${r.driveMinutes}m</dd></div><div><dt>ride</dt><dd>${r.distanceMi}mi</dd></div><div><dt>gravel</dt><dd>${r.surface.gravelPct}%</dd></div><div><dt>gain</dt><dd>${fmt(r.elevationGainFt)}ft</dd></div>`;
    node.querySelector('.bar-gravel').style.width=`${r.surface.gravelPct}%`; node.querySelector('.bar-paved').style.width=`${r.surface.pavedPct}%`; node.querySelector('.bar-unknown').style.width=`${r.surface.unknownPct}%`;
    node.querySelector('.links').innerHTML=`<a href="${r.sourceUrl}" target="_blank" rel="noreferrer">source</a><a class="secondary" href="${r.gpxUrl}" target="_blank" rel="noreferrer">gpx</a><a class="secondary" href="${routeShareUrl(r)}">share</a>`;
    node.querySelector('button').addEventListener('click',()=>selectRoute(r.id)); list.appendChild(node);
  }
}
function drawStats(routes){
  const avg=routes.length?Math.round(routes.reduce((s,r)=>s+r.surface.gravelPct,0)/routes.length):0;
  const long=routes.length?Math.max(...routes.map(r=>r.distanceMi)):0;
  $('stats').innerHTML=`<div class="stat"><strong>${routes.length}</strong><span>visible routes</span></div><div class="stat"><strong>${avg}%</strong><span>avg gravel est</span></div><div class="stat"><strong>${long.toFixed(0)}</strong><span>longest miles</span></div>`;
}
function selectRoute(id){
  const r=state.routes.find(x=>x.id===id); if(!r)return; state.active=id; location.hash=id;
  $('selectedTitle').textContent=r.name; $('selectedMeta').textContent=`${r.distanceMi} mi · ${r.surface.gravelPct}% gravel est · ${r.driveMinutes} min drive · ${r.source}`;
  for(const [rid,l] of state.layers) l.setStyle({weight:rid===id?8:4,opacity:rid===id?1:.65});
  const layer=state.layers.get(id); if(layer){state.map.fitBounds(layer.getBounds(),{padding:[40,40]}); layer.openPopup();}
  document.querySelectorAll('.route-card').forEach(c=>c.classList.toggle('active',c.dataset.id===id));
}
init().catch(err=>{console.error(err); document.body.insertAdjacentHTML('afterbegin',`<pre>${err.stack||err}</pre>`)});
