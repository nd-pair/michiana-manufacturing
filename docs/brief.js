/* Sector briefs: one printable page per sector, from the same data as the map. #sec=Metal|Electronics selects sectors; no hash = all. */
(function(){
const D=window.MM_DATA, C=D.companies, SCOL=D.sectorColors;
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmtUSD=v=>v>=1e9?"$"+(v/1e9).toFixed(1)+"B":v>=1e6?"$"+(v/1e6).toFixed(1)+"M":v>=1e3?"$"+Math.round(v/1e3)+"k":"$"+Math.round(v);
const fmtN=v=>Number(v).toLocaleString();
const sel=document.getElementById("brief-sector"), out=document.getElementById("briefs");
sel.innerHTML=`<option value="">All sectors</option>`+D.sectors.map(s=>`<option>${esc(s)}</option>`).join("");
function chosen(){const m=location.hash.match(/sec=([^&]*)/);return m?m[1].split("|").map(decodeURIComponent).filter(s=>D.sectors.includes(s)):[]}
function groupsOf(list){const g={};for(const c of list){const k=c.group;(g[k]=g[k]||{name:c.parent||c.name,sites:[],emp:0,fed:0,city:c.city});g[k].sites.push(c);g[k].emp+=c.emp||0;g[k].fed+=c.federal?c.federal.total:0}return Object.values(g)}
function trend(sector){const s=(D.qcewSectors||{})[sector];if(!s)return "";const ys=Object.keys(s).map(Number).sort();if(ys.length<2)return "";
  const W=440,H=120,L=56,R=10,T=10,B=22,vs=ys.map(y=>s[y]),max=Math.max(...vs),min=0;const X=y=>L+(y-ys[0])/(ys[ys.length-1]-ys[0])*(W-L-R),Y=v=>T+(1-(v-min)/(max-min||1))*(H-T-B);
  const first=s[ys[0]],last=s[ys[ys.length-1]],chg=first?Math.round(100*(last-first)/first):0;
  return `<figure class="mm-b-trend"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Employment in ${esc(sector)}, ${ys[0]} to ${ys[ys.length-1]}">`
   +`<line x1="${L}" x2="${W-R}" y1="${Y(0)}" y2="${Y(0)}" class="ax"/><text x="${L-6}" y="${Y(max)+4}" text-anchor="end">${fmtN(max)}</text><text x="${L-6}" y="${Y(0)}" text-anchor="end">0</text>`
   +`<text x="${X(ys[0])}" y="${H-6}" text-anchor="middle">${ys[0]}</text><text x="${X(ys[ys.length-1])}" y="${H-6}" text-anchor="middle">${ys[ys.length-1]}</text>`
   +`<polyline points="${ys.map(y=>X(y).toFixed(1)+","+Y(s[y]).toFixed(1)).join(" ")}" fill="none" stroke="${SCOL[sector]}" stroke-width="2.5"/></svg>`
   +`<figcaption>Private employment in the sector's NAICS codes across the region: ${fmtN(first)} in ${ys[0]}, ${fmtN(last)} in ${ys[ys.length-1]} (${chg>=0?"+":""}${chg}%). BLS QCEW; withheld cells count as zero.</figcaption></figure>`}
function brief(sector){
  const list=C.filter(c=>c.sector===sector), groups=groupsOf(list);
  const staff=list.reduce((a,c)=>a+(c.emp||0),0), fed=list.filter(c=>c.federal), fedSum=fed.reduce((a,c)=>a+c.federal.total,0);
  const sbir=list.filter(c=>c.sbir), fda=list.filter(c=>c.fda), pats=list.filter(c=>c.patents);
  const top=groups.sort((a,b)=>b.emp-a.emp).slice(0,10);
  const caps=D.capabilities.map(k=>[k,groupsOf(list.filter(c=>c.caps.includes(k))).length]).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]);
  const gaps=D.capabilities.filter(k=>groupsOf(list.filter(c=>c.caps.includes(k))).length<=1);
  const tags={};for(const c of list)for(const t of c.tags)tags[t]=(tags[t]||0)+1;const ttop=Object.entries(tags).sort((a,b)=>b[1]-a[1]).slice(0,10);
  const ids=new Set(list.map(c=>c.id)), byId=Object.fromEntries(list.map(c=>[c.id,c]));
  const yr=new Date().getFullYear(), recent=D.events.filter(e=>ids.has(e.company)&&e.amount&&+String(e.date).slice(0,4)>=yr-3).sort((a,b)=>b.amount-a.amount).slice(0,5);
  return `<article class="mm-brief">
  <header><p class="mm-b-eyebrow">Michiana Manufacturing · sector brief · ${esc(D.built)}</p><h1><span class="mm-b-sw" style="background:${SCOL[sector]}"></span>${esc(sector)}</h1>
  <p>South Bend–Elkhart region: St. Joseph, Elkhart, Marshall, LaPorte and Kosciusko counties in Indiana, Berrien and Cass counties in Michigan, and neighbors.</p></header>
  <ul class="mm-b-stats">
    <li><b>${fmtN(groups.length)}</b><span>companies</span></li><li><b>${fmtN(list.length)}</b><span>sites</span></li>
    <li><b>${fmtN(staff)}</b><span>staff, known headcounts</span></li><li><b>${fmtUSD(fedSum)}</b><span>federal awards since FY2016, ${fed.length} sites</span></li>
    <li><b>${sbir.reduce((a,c)=>a+c.sbir.count,0)}</b><span>SBIR/STTR awards, ${sbir.length} firms</span></li><li><b>${fda.length}</b><span>FDA-registered device sites</span></li>
    ${pats.length?`<li><b>${pats.reduce((a,c)=>a+c.patents.count,0)}</b><span>patents since 2015</span></li>`:""}
  </ul>
  ${trend(sector)}
  <div class="mm-b-cols">
   <section><h2>Largest companies</h2><table><thead><tr><th>Company</th><th>Sites</th><th>Staff</th><th>Federal</th></tr></thead><tbody>
     ${top.map(g=>`<tr><td>${esc(g.name)}<small>${esc(g.city)}</small></td><td class="n">${g.sites.length}</td><td class="n">${g.emp?fmtN(g.emp):"–"}</td><td class="n">${g.fed?fmtUSD(g.fed):"–"}</td></tr>`).join("")}</tbody></table></section>
   <section><h2>Capabilities</h2><table><thead><tr><th>Process</th><th>Companies</th></tr></thead><tbody>${caps.slice(0,10).map(([k,n])=>`<tr><td>${esc(k)}</td><td class="n">${n}</td></tr>`).join("")}</tbody></table>
     <p class="mm-b-gap"><b>Gaps within the sector</b> (one or no company): ${gaps.length?esc(gaps.join(", ")):"none"}.</p>
     <h2>Most common products</h2><p class="mm-b-tags">${ttop.map(([t,n])=>`${esc(t)} (${n})`).join(" · ")}</p></section>
  </div>
  ${recent.length?`<section><h2>Largest recent awards</h2><table><tbody>${recent.map(e=>`<tr><td class="d">${esc(e.date)}</td><td>${esc(byId[e.company]?byId[e.company].name:"")}: ${esc(e.title)}</td><td class="n">${fmtUSD(e.amount)}</td></tr>`).join("")}</tbody></table></section>`:""}
  <footer>Sources: HIFLD General Manufacturing Facilities (DHS), SBIR.gov, USAspending.gov, openFDA, BLS QCEW and company publications; headcounts are approximate and dated. Methods: nd-pair.github.io/michiana-manufacturing/about.html</footer>
  </article>`}
function render(){const ch=chosen();sel.value=ch.length===1?ch[0]:"";out.innerHTML=(ch.length?ch:D.sectors).map(brief).join("");
  document.getElementById("brief-map").href="index.html"+(ch.length?"#sec="+ch.map(encodeURIComponent).join("|"):"")}
sel.addEventListener("change",()=>{location.hash=sel.value?"sec="+encodeURIComponent(sel.value):"";});
window.addEventListener("hashchange",render);
document.getElementById("brief-print").addEventListener("click",()=>window.print());
render();
})();
