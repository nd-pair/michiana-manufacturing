/* Michiana Manufacturing — the map. Data comes from data.js (built from companies/*.toml by scripts/build.py). */
const DATA=window.MM_DATA; const SCOL=DATA.sectorColors;
const C=DATA.companies, TAGS=[...new Set(C.flatMap(c=>c.tags))].sort((a,b)=>a.localeCompare(b));
const st={sec:new Set(),tag:new Set(),sel:null,hot:null,q:"",sort:{sec:{key:"n",dir:-1},tag:{key:"n",dir:-1}}};
try{const h=location.hash.slice(1);if(h&&C.some(c=>c.id===h))st.sel=h}catch(e){}
const matchRel=c=>true, matchSec=c=>!st.sec.size||st.sec.has(c.sector), matchTag=c=>!st.tag.size||c.tags.some(t=>st.tag.has(t));
const visible=c=>matchRel(c)&&matchSec(c)&&matchTag(c);
const hotMatch=c=>st.hot&&(st.hot.sec?c.sector===st.hot.sec:c.tags.includes(st.hot.tag));
const esc=s=>String(s).replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmtEmp=c=>c.emp?c.emp.toLocaleString()+(c.emp_scope==="company"?" (company-wide)":""):"unknown";
const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- a true-scale globe, one continuous zoom ---------- */
const R=10, RAD=Math.PI/180, KM=6371/R;              // scene unit -> km
const [LATC,LONC]=DATA.center;
const P=(lat,lon,h=0)=>{const la=lat*RAD,lo=lon*RAD,r=R+h;return new THREE.Vector3(r*Math.cos(la)*Math.sin(lo),r*Math.sin(la),r*Math.cos(la)*Math.cos(lo))};
const latLonOf=p=>{const r=p.length();return [Math.asin(p.y/r)/RAD,Math.atan2(p.x,p.z)/RAD]};
const box=document.getElementById("scene"), tip=document.getElementById("tip"), hud=document.getElementById("hud");
const renderer=new THREE.WebGLRenderer({antialias:true,logarithmicDepthBuffer:true}); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.outputEncoding=THREE.sRGBEncoding; box.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color("#05070b");
const camera=new THREE.PerspectiveCamera(42,1.6,0.001,100);
const globe=new THREE.Group(); scene.add(globe);
scene.add(new THREE.HemisphereLight(0x9fd6ff,0x0a0f16,0.8));
const key=new THREE.DirectionalLight(0xbfe9ff,0.9); key.position.set(-4,6,10); scene.add(key);
const lift=k=>k*1e-4;                                 // layer lifts in true scale: 1e-4 R = 0.64 km

/* ground: a dark steel sphere with a faint graticule */
globe.add(new THREE.Mesh(new THREE.SphereGeometry(R,256,128),new THREE.MeshStandardMaterial({color:0x0a0e14,metalness:0.7,roughness:0.55})));
(function graticule(){const mat=new THREE.LineBasicMaterial({color:0x17212c,transparent:true,opacity:0.9});
  for(let lon=-96;lon<=-76;lon+=0.5){const pts=[];for(let la=35;la<=49;la+=0.25)pts.push(P(la,lon,lift(0.5)));globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),mat))}
  for(let la=35;la<=49;la+=0.5){const pts=[];for(let lon=-96;lon<=-76;lon+=0.25)pts.push(P(la,lon,lift(0.5)));globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),mat))}})();

/* panels on the surface: triangulate in lon/lat, lift onto the sphere */
function panel(ring,mat,h){if(ring.length>3&&ring[0][0]===ring[ring.length-1][0]&&ring[0][1]===ring[ring.length-1][1])ring=ring.slice(0,-1);const pts2=ring.map(([la,lo])=>new THREE.Vector2(lo,la));let tris;try{tris=THREE.ShapeUtils.triangulateShape(pts2,[])}catch(e){return}
  const pos=[];for(const t of tris)for(const i of t){const p=P(ring[i][0],ring[i][1],h);pos.push(p.x,p.y,p.z)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));g.computeVertexNormals();globe.add(new THREE.Mesh(g,mat))}
function outline(ring,mat,h){globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ring.map(([la,lo])=>P(la,lo,h))),mat))}
/* the Great Lakes: painted onto a canvas texture on a surface patch (canvas fill handles any shoreline polygon; triangulation does not) */
(function lakes(){
  const LAT0=37,LAT1=49,LON0=-93.5,LON1=-75.5,W=4096,H=2736,cv=document.createElement("canvas");cv.width=W;cv.height=H;const cx=cv.getContext("2d");
  const X=lo=>(lo-LON0)/(LON1-LON0)*W, Y=la=>(LAT1-la)/(LAT1-LAT0)*H;
  cx.beginPath();for(const ring of DATA.lakes){ring.forEach(([la,lo],i)=>i?cx.lineTo(X(lo),Y(la)):cx.moveTo(X(lo),Y(la)));cx.closePath()}
  cx.fillStyle="#0b1b30";cx.fill("evenodd");cx.lineWidth=3;cx.strokeStyle="rgba(42,127,166,0.9)";cx.stroke();
  const tex=new THREE.CanvasTexture(cv);tex.encoding=THREE.sRGBEncoding;tex.anisotropy=8;tex.minFilter=THREE.LinearMipmapLinearFilter;
  const NX=180,NY=120,pos=[],uv=[],idx=[];
  for(let j=0;j<=NY;j++)for(let i=0;i<=NX;i++){const la=LAT0+(LAT1-LAT0)*j/NY,lo=LON0+(LON1-LON0)*i/NX;const p=P(la,lo,lift(0.8));pos.push(p.x,p.y,p.z);uv.push(i/NX,j/NY)}
  for(let j=0;j<NY;j++)for(let i=0;i<NX;i++){const a=j*(NX+1)+i,b=a+1,c=a+NX+1,d=c+1;idx.push(a,b,c,b,d,c)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));g.setAttribute("uv",new THREE.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();
  globe.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false})));
})();
const coreMat=new THREE.MeshStandardMaterial({color:0x182734,metalness:0.6,roughness:0.5,polygonOffset:true,polygonOffsetFactor:-1});
const farMat=new THREE.MeshStandardMaterial({color:0x10161e,metalness:0.6,roughness:0.6,polygonOffset:true,polygonOffsetFactor:-1});
const coreLine=new THREE.LineBasicMaterial({color:0x35d6ff,transparent:true,opacity:0.75}), farLine=new THREE.LineBasicMaterial({color:0x2a4150,transparent:true,opacity:0.9});
for(const k of DATA.counties)for(const ring of k.rings){panel(ring,k.core?coreMat:farMat,lift(1));outline(ring,k.core?coreLine:farLine,lift(k.core?1.6:1.4))}

/* labels: canvas sprites, screen-constant */
const placed=[], KREF=0.052;   // object sizes were designed for a view 5 units up; the home view is 0.26 up, at true scale
function place(obj,lat,lon,h,o={}){const mode=o.mode||"screen";if(mode!=="map")obj.scale.multiplyScalar(KREF);obj.userData.lay={lat,lon,h,base:obj.scale.clone(),mode,group:o.group||null};const p=P(lat,lon,h);obj.position.copy(p);if(!obj.isSprite)obj.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),p.clone().normalize());placed.push(obj);(o.group||globe).add(obj);return obj}
function label(text,opts={}){const s=opts.size||26,pad=10,cv=document.createElement("canvas"),cx=cv.getContext("2d");const font=`${opts.weight||600} ${s}px Rajdhani, Inter, system-ui, sans-serif`;cx.font=font;
  const w=Math.ceil(cx.measureText(text).width)+pad*2;cv.width=w*2;cv.height=(s+pad*2)*2;cx.scale(2,2);cx.font=font;
  if(opts.glow){cx.shadowColor=opts.glow;cx.shadowBlur=12}
  cx.fillStyle=opts.color||"#e6edf3";cx.textBaseline="middle";cx.fillText(text,pad,(s+pad*2)/2);
  const t=new THREE.CanvasTexture(cv);t.minFilter=THREE.LinearFilter;const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,depthTest:false,opacity:opts.opacity??1}));
  const k=(opts.scale||0.012);sp.scale.set(w*k,(s+pad*2)*k,1);sp.center.set(opts.cx??0,0.5);return sp}
const near=new THREE.Group(), mid=new THREE.Group(), far=new THREE.Group(); globe.add(near,mid,far);
const dotMat=new THREE.MeshBasicMaterial({color:0xe6edf3});
for(const [n,[la,lo]] of Object.entries(DATA.cities)){
  place(new THREE.Mesh(new THREE.SphereGeometry(0.03,10,10),dotMat),la,lo,lift(2),{group:near});
  const l=label(n,{size:22,weight:600,color:"#dfe9f2",scale:0.006});l.center.set(-0.1,0.5);place(l,la,lo,lift(2),{group:near})}
for(const k of DATA.counties){if(!k.core)continue;const la=k.rings[0].reduce((a,p)=>a+p[0],0)/k.rings[0].length,lo=k.rings[0].reduce((a,p)=>a+p[1],0)/k.rings[0].length;
  place(label(k.name.toUpperCase(),{size:18,weight:500,color:"#35d6ff",opacity:0.75,scale:0.0055,cx:0.5}),la,lo,lift(2),{group:near})}
for(const [n,[la,lo,big]] of Object.entries(DATA.metros)){
  place(new THREE.Mesh(new THREE.SphereGeometry(big?0.05:0.035,12,12),new THREE.MeshBasicMaterial({color:big?0xffb020:0x9fb0c0})),la,lo,lift(2),{group:big?globe:mid});
  const l=label(n,{size:big?28:22,weight:big?700:500,color:big?"#ffd280":"#b8c6d4",glow:big?"#ffb020":null,scale:0.006});l.center.set(-0.1,0.5);place(l,la,lo,lift(2),{group:big?globe:mid})}
for(const [n,[la,lo]] of Object.entries(DATA.states))place(label(n,{size:30,weight:500,color:"#4f6478",opacity:0.8,scale:0.009,cx:0.5}),la,lo,lift(2),{group:far});
const regionLabel=place(label("SOUTH BEND–ELKHART",{size:22,weight:700,color:"#35d6ff",glow:"#35d6ff",scale:0.006,cx:0.5}),LATC-0.28,LONC+0.1,lift(3),{group:far});

/* Notre Dame Main Building: schematic, ten times its footprint, shown only at the closest zoom */
let dome=null;
(function mainBuilding(){
  const g=new THREE.Group(); const brick=new THREE.MeshStandardMaterial({color:0xd8c48f,roughness:0.85}); const trim=new THREE.MeshStandardMaterial({color:0xf2ead6,roughness:0.7});
  const gold=new THREE.MeshStandardMaterial({color:0xe3b53a,metalness:0.95,roughness:0.22,emissive:0x5a3f00,emissiveIntensity:0.5});
  const slate=new THREE.MeshStandardMaterial({color:0x5b6670,roughness:0.9});
  const add=(geo,mat,x,y,z)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);g.add(m);return m};
  const B=0.0016;   // 1 km across; the real building is ~100 m
  add(new THREE.BoxGeometry(1.9*B,0.015*B,1.1*B),new THREE.MeshStandardMaterial({color:0x1d4a2e,roughness:1}),0,0.005*B,0);
  add(new THREE.BoxGeometry(1.5*B,0.30*B,0.34*B),brick,0,0.15*B,0.2*B);
  add(new THREE.BoxGeometry(1.5*B,0.03*B,0.36*B),slate,0,0.315*B,0.2*B);
  add(new THREE.BoxGeometry(0.46*B,0.46*B,0.46*B),brick,0,0.23*B,0.2*B);
  add(new THREE.BoxGeometry(0.50*B,0.03*B,0.50*B),trim,0,0.47*B,0.2*B);
  add(new THREE.CylinderGeometry(0.17*B,0.19*B,0.20*B,24),trim,0,0.58*B,0.2*B);
  add(new THREE.SphereGeometry(0.19*B,32,16,0,Math.PI*2,0,Math.PI/2),gold,0,0.68*B,0.2*B);
  add(new THREE.CylinderGeometry(0.045*B,0.05*B,0.09*B,12),gold,0,0.91*B,0.2*B);
  add(new THREE.CylinderGeometry(0.012*B,0.025*B,0.08*B,8),gold,0,0.99*B,0.2*B);
  add(new THREE.SphereGeometry(0.02*B,8,8),gold,0,1.04*B,0.2*B);
  g.rotation.y=Math.PI/2;   // the long facade runs north-south on the map; rotate the model to match
  dome=place(g,DATA.landmark.lat,DATA.landmark.lon,lift(1.8),{mode:"map"});
  place(label(DATA.landmark.name.toUpperCase(),{size:18,weight:700,color:"#ffd280",glow:"#ffb020",scale:0.0055,cx:0.5}),DATA.landmark.lat,DATA.landmark.lon,0.003,{group:near});
})();

/* company columns: unlit, exact sector hex on top, darker sides, plus an additive glow shell */
const barH=c=>c.emp?0.08+0.15*Math.log10(Math.max(c.emp,10)):0.09;
function columnGeometry(w,h,hex){const g=new THREE.BoxGeometry(w,h,w);g.translate(0,h/2,0);const base=new THREE.Color(hex).convertSRGBToLinear();const shade=[0.72,0.72,1,0.5,0.86,0.86];
  const col=new Float32Array(24*3);for(let f=0;f<6;f++)for(let v=0;v<4;v++){const i=f*4+v;col[3*i]=base.r*shade[f];col[3*i+1]=base.g*shade[f];col[3*i+2]=base.b*shade[f]}g.setAttribute("color",new THREE.BufferAttribute(col,3));return g}
const bars=[]; const WHITE=new THREE.Color(1,1,1), LIT=new THREE.Color(1.6,1.6,1.6);
for(const c of C){
  const h=barH(c), w=0.06;
  const mat=new THREE.MeshBasicMaterial({vertexColors:true,transparent:true}); if(!c.emp)mat.opacity=0.5;
  const m=new THREE.Mesh(columnGeometry(w,h,SCOL[c.sector]),mat); m.userData=c; place(m,c.lat,c.lon,lift(2.2),{mode:"pin"});
  const glowGeo=new THREE.BoxGeometry(w*1.9,h*1.04,w*1.9); glowGeo.translate(0,h*0.52,0);
  const glow=new THREE.Mesh(glowGeo,new THREE.MeshBasicMaterial({color:new THREE.Color(SCOL[c.sector]).convertSRGBToLinear(),transparent:true,opacity:0.16,blending:THREE.AdditiveBlending,depthWrite:false})); place(glow,c.lat,c.lon,lift(2.2),{mode:"pin"});
  const halo=new THREE.Mesh(new THREE.RingGeometry(0.09,0.12,32),new THREE.MeshBasicMaterial({color:0x35d6ff,side:THREE.DoubleSide,transparent:true,opacity:0})); halo.geometry.rotateX(-Math.PI/2); place(halo,c.lat,c.lon,lift(2.4),{mode:"pin"});
  bars.push({c,m,glow,halo,h});
}

/* view: a target on the surface, a distance above it, a tilt that grows as you come in; one continuous zoom */
const D_MIN=0.012, D_MAX=1.35, D_HOME=0.26;            // 0.26 ≈ 165 km above the corridor; 1.35 shows Chicago to Cleveland
const view={lat:LATC,lon:LONC,dist:D_HOME}; const home={...view};
function tiltFor(d){return 0.58*(1-THREE.MathUtils.smoothstep(Math.log(d),Math.log(0.12),Math.log(1.3)))+0.08}
function layout(){const d=view.dist, screen=d/D_HOME;
  for(const o of placed){const L=o.userData.lay;if(L.mode==="map")continue;o.scale.copy(L.base).multiplyScalar(L.mode==="pin"?Math.min(screen,2.2):screen)}
  near.visible=d<0.55; mid.visible=d>0.45; far.visible=d>0.7; if(dome)dome.visible=d<0.09;
  hud.innerHTML=`<span>ALT</span> ${(d*KM).toFixed(d<0.05?1:0)} km &nbsp; <span>CTR</span> ${view.lat.toFixed(3)}°N ${(-view.lon).toFixed(3)}°W &nbsp; <span>SPAN</span> ${(2*d*Math.tan(0.3665)*KM).toFixed(0)} km`}
function applyView(){layout(); const d=view.dist, t=tiltFor(d);
  globe.rotation.set(view.lat*RAD,-view.lon*RAD,0);
  camera.near=Math.max(0.0005,d*0.04); camera.far=d*60+2*R; camera.updateProjectionMatrix();
  camera.position.set(0,-d*Math.sin(t),R+d*Math.cos(t)); camera.lookAt(0,0,R)}
const ray=new THREE.Raycaster(), ndc=new THREE.Vector2();
const pickSphere=new THREE.Mesh(new THREE.SphereGeometry(R,64,32),new THREE.MeshBasicMaterial({visible:false})); globe.add(pickSphere);
function surfaceAt(e){const r=renderer.domElement.getBoundingClientRect();ndc.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(ndc,camera);const h=ray.intersectObject(pickSphere,false)[0];return h?latLonOf(globe.worldToLocal(h.point.clone())):null}
let drag=null;
box.addEventListener("pointerdown",e=>{if(e.target.closest(".mm-ctl"))return;drag={x:e.clientX,y:e.clientY,lat:view.lat,lon:view.lon,moved:false};box.setPointerCapture(e.pointerId)});
box.addEventListener("pointermove",e=>{if(drag){const r=renderer.domElement.getBoundingClientRect();const k=(2*view.dist*Math.tan(0.3665)/r.height)/(R*RAD);
    view.lat=THREE.MathUtils.clamp(drag.lat+(e.clientY-drag.y)*k,36,48);view.lon=THREE.MathUtils.clamp(drag.lon-(e.clientX-drag.x)*k/Math.cos(view.lat*RAD),-95,-77);
    if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>4)drag.moved=true;applyView();tip.style.opacity=0}else hover(e)});
box.addEventListener("pointerup",e=>{if(drag&&!drag.moved){const b=pick(e);if(b)select(b.c.id)}drag=null});
box.addEventListener("pointerleave",()=>{tip.style.opacity=0});
function zoomBy(f,e){const d0=view.dist,d1=THREE.MathUtils.clamp(d0*f,D_MIN,D_MAX);
  if(e&&d1!==d0){const ll=surfaceAt(e);if(ll){const k=1-d1/d0;view.lat+= (ll[0]-view.lat)*k;view.lon+=(ll[1]-view.lon)*k}}
  view.dist=d1;applyView()}
box.addEventListener("wheel",e=>{e.preventDefault();zoomBy(Math.exp(Math.sign(e.deltaY)*0.12),e)},{passive:false});
let pinch=null; box.addEventListener("touchstart",e=>{if(e.touches.length===2)pinch=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY)},{passive:true});
box.addEventListener("touchmove",e=>{if(e.touches.length===2&&pinch){const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY);zoomBy(pinch/d);pinch=d}},{passive:true});
document.getElementById("zin").onclick=()=>zoomBy(0.7);
document.getElementById("zout").onclick=()=>zoomBy(1/0.7);
document.getElementById("reset").onclick=()=>{Object.assign(view,home);applyView()};
document.getElementById("campus").onclick=()=>{view.lat=DATA.landmark.lat;view.lon=DATA.landmark.lon;view.dist=0.018;applyView()};
function pick(e){const r=renderer.domElement.getBoundingClientRect();ndc.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(ndc,camera);
  const hit=ray.intersectObjects(bars.map(b=>b.m),false)[0];return hit?bars.find(b=>b.m===hit.object):null}
let hoverId=null;
function hover(e){const b=pick(e); const id=b?b.c.id:null; if(id!==hoverId){hoverId=id;paintBars()}
  if(b){const top=b.m.localToWorld(new THREE.Vector3(0,b.h,0)).project(camera);const r=renderer.domElement.getBoundingClientRect();
    tip.innerHTML=`<b>${esc(b.c.name)}</b>${esc(b.c.city)}, ${esc(b.c.state)} · ${esc(b.c.sector)}<div class="m">${esc(fmtEmp(b.c))} employees</div>`;
    tip.style.left=((top.x+1)/2*r.width)+"px";tip.style.top=((1-top.y)/2*r.height)+"px";tip.style.opacity=1;box.style.cursor="pointer"}
  else{tip.style.opacity=0;box.style.cursor=drag?"grabbing":"grab"}}
function paintBars(){for(const b of bars){const v=visible(b.c),h=hotMatch(b.c),on=st.hot?(v&&h):v,lit=(hoverId===b.c.id||st.sel===b.c.id||(st.hot&&on));
  b.m.material.opacity=on?(b.c.emp?1:0.5):0.07; b.m.material.color.copy(lit?LIT:WHITE); b.glow.material.opacity=on?(lit?0.4:0.16):0; b.halo.material.opacity=st.sel===b.c.id?0.9:0}}
function resize(){const w=box.clientWidth,h=Math.max(360,Math.min(640,Math.round(w*0.64)));box.style.height=h+"px";renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}
new ResizeObserver(resize).observe(box); resize(); applyView();
let t0=performance.now(); (function loop(){requestAnimationFrame(loop);
  if(!reduced&&!drag){const t=(performance.now()-t0)/1000; if(t<2.8){const k=1-Math.pow(1-Math.min(t/2.8,1),3); view.dist=Math.exp(Math.log(D_MAX)+(Math.log(home.dist)-Math.log(D_MAX))*k); applyView()}}
  renderer.render(scene,camera)})();

/* ---------- filters, histograms, roster ---------- */
function select(id){st.sel=(st.sel===id?null:id);try{history.replaceState(null,"",st.sel?"#"+st.sel:location.pathname)}catch(e){}render();
  if(st.sel){const row=document.getElementById("row-"+st.sel);if(row)row.scrollIntoView({block:"nearest",behavior:reduced?"auto":"smooth"})}}
document.getElementById("clear").addEventListener("click",()=>{st.sec.clear();st.tag.clear();st.sel=null;st.q="";document.getElementById("tagsearch").value="";render()});
document.getElementById("tagsearch").addEventListener("input",e=>{st.q=e.target.value.trim().toLowerCase();renderTags()});
const fmtK=v=>v>=10000?Math.round(v/1000)+"k":v>=1000?(v/1000).toFixed(1)+"k":String(v);
const empSum=list=>list.reduce((a,c)=>a+(c.emp||0),0);
function bar(cls,label,n,max,e,emax,pressed,extra,col){return `<button type="button" class="mm-bar ${cls} ${n?"":"zero"}" aria-pressed="${pressed}" ${extra} ${col?`style="--c:${col}"`:""}><span class="lab">${col?`<span class="dot" style="background:${col};color:${col}"></span>`:""}<span>${esc(label)}</span><span class="trk"><span class="fil" style="width:${max?Math.round(100*n/max):0}%"></span><span class="fil2" style="width:${emax?Math.round(100*e/emax):0}%"></span></span></span><span class="n">${n}</span><span class="e">${e?fmtK(e):"–"}</span></button>`}
const ARROW=d=>d<0?" ▾":" ▴";
function HH(kind){const s=st.sort[kind];return `<div class="mm-hh"><span>sort by</span><button type="button" data-kind="${kind}" data-sort="n" aria-pressed="${s.key==="n"}" title="Sort by number of companies">cos${s.key==="n"?ARROW(s.dir):""}</button><button type="button" data-kind="${kind}" data-sort="e" aria-pressed="${s.key==="e"}" title="Sort by staff">staff${s.key==="e"?ARROW(s.dir):""}</button></div>`}
const sorter=kind=>{const s=st.sort[kind],i=s.key==="n"?1:2,j=s.key==="n"?2:1;return (a,b)=>(a[i]-b[i])*s.dir||(a[j]-b[j])*s.dir||a[0].localeCompare(b[0])};
function renderSectors(){const base=C.filter(c=>matchRel(c)&&matchTag(c));const counts=DATA.sectors.map(s=>{const l=base.filter(c=>c.sector===s);return [s,l.length,empSum(l)]}).sort(sorter("sec"));const max=Math.max(1,...counts.map(x=>x[1])),emax=Math.max(1,...counts.map(x=>x[2]));
  document.getElementById("sectors").innerHTML=HH("sec")+counts.map(([s,n,e])=>bar("sec",s,n,max,e,emax,st.sec.has(s),`data-sec="${esc(s)}"`,SCOL[s])).join("")}
function renderTags(){const base=C.filter(c=>matchRel(c)&&matchSec(c));let counts=TAGS.map(t=>{const l=base.filter(c=>c.tags.includes(t));return [t,l.length,empSum(l)]}).sort(sorter("tag"));
  if(st.q)counts=counts.filter(([t])=>t.toLowerCase().includes(st.q));const max=Math.max(1,...counts.map(x=>x[1])),emax=Math.max(1,...counts.map(x=>x[2]));
  document.getElementById("tags").innerHTML=HH("tag")+counts.map(([t,n,e])=>bar("tag",t,n,max,e,emax,st.tag.has(t),`data-tag="${esc(t)}"`)).join("")||`<p class="mm-count">No product matches "${esc(st.q)}".</p>`;
  document.getElementById("tagcount").textContent=`${TAGS.length} categories`}
document.addEventListener("click",e=>{const h=e.target.closest("[data-sort]");if(h){const s=st.sort[h.dataset.kind];if(s.key===h.dataset.sort)s.dir=-s.dir;else{s.key=h.dataset.sort;s.dir=-1}if(h.dataset.kind==="sec")renderSectors();else renderTags();return}
  const b=e.target.closest(".mm-bar");if(!b)return;if(b.dataset.sec){const s=b.dataset.sec;st.sec.has(s)?st.sec.delete(s):st.sec.add(s)}else if(b.dataset.tag){const t=b.dataset.tag;st.tag.has(t)?st.tag.delete(t):st.tag.add(t)}render()});
document.addEventListener("mouseover",e=>{const b=e.target.closest(".mm-bar");if(!b)return;st.hot=b.dataset.sec?{sec:b.dataset.sec}:{tag:b.dataset.tag};paintBars()});
document.addEventListener("mouseout",e=>{const b=e.target.closest(".mm-bar");if(!b)return;st.hot=null;paintBars()});
function renderDetail(){const d=document.getElementById("detail");const c=C.find(x=>x.id===st.sel);
  if(!c){d.innerHTML=`<p class="mm-empty">Select a company on the map or in the roster.</p>`;return}
  d.innerHTML=`<h3><span class="mm-dot" style="background:${SCOL[c.sector]};color:${SCOL[c.sector]}"></span>${esc(c.name)}</h3>
  <div><div class="k">What they do</div>${esc(c.blurb)||"–"}<div class="k">Products &amp; services</div>${esc(c.tags.join(", "))}</div>
  <div><div class="k">Employees</div>${esc(fmtEmp(c))}${c.emp_note?" · "+esc(c.emp_note):""}<div class="k">Location</div>${esc(c.addr||c.city+", "+c.state)}${c.prec==="city"?" (city-level position)":""}${c.website?`<div class="k">Website</div><a href="${esc(c.website)}" rel="noopener">${esc(c.website.replace(/^https?:\/\/(www\.)?/,""))}</a>`:""}</div>`}
function renderTable(){const tb=document.querySelector("#table tbody");const rows=C.filter(visible).sort((a,b)=>a.sector.localeCompare(b.sector)||(b.emp||0)-(a.emp||0)||a.name.localeCompare(b.name));
  tb.innerHTML=rows.map(c=>`<tr id="row-${c.id}" class="${st.sel===c.id?"sel":""}" data-id="${c.id}"><td class="name">${esc(c.name)}<small>${esc(c.city)}, ${esc(c.state)}</small></td><td><span class="mm-dot" style="background:${SCOL[c.sector]};color:${SCOL[c.sector]}"></span>${esc(c.sector)}</td><td class="num">${c.emp?c.emp.toLocaleString():"–"}${c.emp&&c.emp_scope==="company"?"*":""}</td><td class="tags">${esc(c.tags.join(", "))}</td><td>${c.website?`<a href="${esc(c.website)}" rel="noopener">${esc(c.website.replace(/^https?:\/\/(www\.)?/,"").replace(/\/$/,""))}</a>`:"–"}</td></tr>`).join("")||`<tr><td colspan="5" class="mm-count">No company matches these filters.</td></tr>`;
  document.getElementById("shown").textContent=`${rows.length} of ${C.length} shown`}
document.querySelector("#table tbody").addEventListener("click",e=>{if(e.target.closest("a"))return;const r=e.target.closest("tr[data-id]");if(r)select(r.dataset.id)});
function render(){renderSectors();renderTags();paintBars();renderDetail();renderTable()}
document.getElementById("legend").innerHTML=DATA.sectors.map(s=>`<span><i class="mm-sw" style="background:${SCOL[s]};color:${SCOL[s]}"></i>${esc(s)}</span>`).join("")+
  `<span>column height = employees, log scale <i class="mm-hl"><i style="height:6px"></i><i style="height:10px"></i><i style="height:14px"></i><i style="height:18px"></i></i>10 · 100 · 1,000 · 10,000</span><span>dim: headcount unknown</span><span>panels: companies (blue) and staff (amber, sum of known headcounts)</span>`;
const withEmp=C.filter(c=>c.emp).length, siteEmp=C.filter(c=>c.emp&&c.emp_scope!=="company").length;
document.getElementById("foot").textContent=`${C.length} companies and organizations, built ${DATA.built}. Company facts, products and headcounts come from public sources: company websites, filings, press and business directories; headcounts are approximate (${withEmp} known, ${siteEmp} for the local site and the rest company-wide, marked * in the roster). Positions are geocoded street addresses on a true-scale globe. County boundaries: U.S. Census Bureau; shorelines: Natural Earth. The Main Building model is schematic at ten times its footprint and appears only at the closest zoom. Sectors and product tags are editorial groupings.`;
render();
