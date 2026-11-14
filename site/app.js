/* Michiana Manufacturing — the map. Data comes from data.js (built from companies/*.toml by scripts/build.py).
   Sections: data and state · theme · globe and layers · view and input · panels · roster · wiring. */
(function(){
"use strict";
const DATA=window.MM_DATA, SCOL=DATA.sectorColors, C=DATA.companies;
const byId=Object.fromEntries(C.map(c=>[c.id,c]));
const TAGS=[...new Set(C.flatMap(c=>c.tags))].sort((a,b)=>a.localeCompare(b));
/* multi-site companies: c.group is shared by all plants of one company; c.parent is its display name */
const GROUPS={};for(const c of C)(GROUPS[c.group]=GROUPS[c.group]||{id:c.group,name:c.parent||c.name,sites:[]}).sites.push(c);
const groupOf=c=>GROUPS[c.group];
const nGroups=list=>new Set(list.filter(c=>c.mfg).map(c=>c.group)).size;   /* counts manufacturers only: R&D, software, investors and universities are on the map but not counted */
const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmtK=v=>v>=10000?Math.round(v/1000)+"k":v>=1000?(v/1000).toFixed(1)+"k":String(v);
const fmtUSD=v=>v>=1e9?"$"+(v/1e9).toFixed(1)+"B":v>=1e6?"$"+(v/1e6).toFixed(1)+"M":v>=1e3?"$"+Math.round(v/1e3)+"k":"$"+Math.round(v);
const empSum=list=>list.reduce((a,c)=>a+(c.emp||0),0);
const shortYear=y=>y?"’"+String(y).slice(2):"";
function fmtEmp(c){if(!c.emp)return "unknown";const bits=[c.emp_year,c.emp_quality,c.emp_scope==="company"?"company-wide":""].filter(Boolean);return (c.emp_quality==="estimate"?"about ":"")+c.emp.toLocaleString()+(bits.length?" ("+bits.join(", ")+")":"")}

/* ---------- state, addressable through the URL hash ---------- */
const st={sec:new Set(),tag:new Set(),cap:new Set(),fed:false,fda:false,rings:false,radius:0,sel:null,hot:null,q:"",open:new Set(),
  sort:{sec:{key:"n",dir:-1},tag:{key:"n",dir:-1},cap:{key:"n",dir:-1},fed:{key:"e",dir:-1},roster:{key:"emp",dir:-1},ev:{key:"date",dir:-1},spec:{key:"lq",dir:-1},occ:{key:"emp",dir:-1},ue:{key:"rate",dir:-1},hum:{key:"cost",dir:-1},opp:{key:"impact",dir:-1},cmp:{key:"index",dir:-1},ndr:{key:"start",dir:-1}},ndrAll:false,wv:"spec",hum:null,hb:"related",rlim:20,rpage:0,
  evKind:"all",evYear:null,evMore:0,qv:"county",qs:"abs",tab:"companies"};
const TABS=["companies","occupations","outlook","humanoid"];
function readHash(){st.sec.clear();st.tag.clear();st.cap.clear();st.fed=st.fda=st.rings=false;st.radius=0;st.sel=null;st.hum=null;st.tab="companies";
  try{const raw=location.hash.slice(1),h=decodeURIComponent(raw);if(h&&byId[h]){st.sel=h;return}
    for(const kv of raw.split("&")){const i=kv.indexOf("=");if(i<0)continue;const k=kv.slice(0,i),v=decodeURIComponent(kv.slice(i+1));if(!v)continue;const vals=kv.slice(i+1).split("|").map(decodeURIComponent);
      if(k==="sec")vals.forEach(x=>st.sec.add(x));else if(k==="tag")vals.forEach(x=>st.tag.add(x));else if(k==="cap")vals.forEach(x=>st.cap.add(x));
      else if(k==="fed")st.fed=v==="1";else if(k==="fda")st.fda=v==="1";else if(k==="rings")st.rings=v==="1";
      else if(k==="r")st.radius=+v||0;else if(k==="hum"&&/^[gk]:[a-z]+$/.test(v))st.hum=v;else if(k==="sel"&&byId[v])st.sel=v;else if(k==="tab"){const t=v==="readiness"?"outlook":v;if(TABS.includes(t))st.tab=t}}}catch(e){}}
const enc=set=>[...set].map(encodeURIComponent).join("|");
function hashState(withTab=true){const p=[];if(withTab&&st.tab!=="companies")p.push("tab="+st.tab);if(st.sec.size)p.push("sec="+enc(st.sec));if(st.tag.size)p.push("tag="+enc(st.tag));if(st.cap.size)p.push("cap="+enc(st.cap));
  if(st.fed)p.push("fed=1");if(st.fda)p.push("fda=1");if(st.rings)p.push("rings=1");if(st.radius)p.push("r="+st.radius);if(st.hum)p.push("hum="+st.hum);if(st.sel)p.push("sel="+st.sel);
  return p.length?"#"+p.join("&"):""}
function updateHash(){try{history.replaceState(null,"",hashState()||location.pathname)}catch(e){}}
readHash();

/* ---------- filters ---------- */
const RAD=Math.PI/180;
function km(aLat,aLon,bLat,bLon){const dLa=(bLat-aLat)*RAD,dLo=(bLon-aLon)*RAD;const s=Math.sin(dLa/2)**2+Math.cos(aLat*RAD)*Math.cos(bLat*RAD)*Math.sin(dLo/2)**2;return 12742*Math.asin(Math.sqrt(s))}
const center=()=>{const c=st.sel&&byId[st.sel];return c?{lat:c.lat,lon:c.lon,name:c.name}:{lat:DATA.landmark.lat,lon:DATA.landmark.lon,name:"the campus"}};
const matchSec=c=>!st.sec.size||st.sec.has(c.sector), matchTag=c=>!st.tag.size||c.tags.some(t=>st.tag.has(t)), matchCap=c=>!st.cap.size||c.caps.some(k=>st.cap.has(k));
const matchFed=c=>!st.fed||!!c.federal, matchFda=c=>!st.fda||!!c.fda;
let _ctr=center();const matchRad=c=>!st.radius||km(_ctr.lat,_ctr.lon,c.lat,c.lon)<=st.radius;
const HUM=DATA.humanoid||{groups:[],components:[],funding:{},progress:{}},HCOMP=Object.fromEntries(HUM.components.map(c=>[c.id,c])),HGROUP=Object.fromEntries(HUM.groups.map(g=>[g.id,g]));
const matchHum=c=>{if(!st.hum)return true;const [t,k]=st.hum.split(":");return t==="g"?c.hum.some(x=>HCOMP[x]&&HCOMP[x].group===k):c.hum.includes(k)};
const visibleExcept=skip=>c=>matchHum(c)&&(skip==="sec"||matchSec(c))&&(skip==="tag"||matchTag(c))&&(skip==="cap"||matchCap(c))&&matchFed(c)&&matchFda(c)&&matchRad(c);
const visible=visibleExcept("");
const hotMatch=c=>st.hot&&(st.hot.sec?c.sector===st.hot.sec:st.hot.cap?c.caps.includes(st.hot.cap):c.tags.includes(st.hot.tag));

/* ---------- theme: dark by default; follows the page's Light/Dark switch ---------- */
const THEMES={
  dark:{bg:"#071629",ground:0x0a1c33,groundMetal:0.7,grat:0x173254,lakeFill:"#0d2f55",lakeStroke:"rgba(53,160,214,0.9)",core:0x163a5e,far:0x0f2644,landMetal:0.6,
    coreLine:0x35d6ff,coreLineOp:0.75,farLine:0x2a4150,cityDot:0xe6edf3,dotMajor:0xffb020,dotMinor:0x9fb0c0,ring:0x35d6ff,halo:0x35d6ff,hemi:[0x9fd6ff,0x0a0f16,0.8],key:0.9,
    glow:0.09,dimMix:null,dimK:0.3,dimOp:0.12,
    labels:{city:["#dfe9f2"],county:["#35d6ff"],metroMajor:["#ffd280","#ffb020"],metroMinor:["#b8c6d4"],state:["#4f6478"],region:["#35d6ff","#35d6ff"],ring:["#35d6ff"],landmark:["#ffd280","#ffb020"]}},
  light:{bg:"#e8edf2",ground:0xdbe2e9,groundMetal:0.05,grat:0xc6d0da,lakeFill:"#bcd6ea",lakeStroke:"rgba(30,100,150,0.85)",core:0xfbfcfd,far:0xe9eef2,landMetal:0.05,
    coreLine:0x0a7fa8,coreLineOp:0.85,farLine:0xb3c0cc,cityDot:0x1b2733,dotMajor:0xb86e00,dotMinor:0x5d6b78,ring:0x0a7fa8,halo:0x0a6f93,hemi:[0xffffff,0xb8c2cc,1.05],key:0.55,
    glow:0,dimMix:"#ffffff",dimK:0.55,dimOp:0.22,
    labels:{city:["#1b2733"],county:["#0a6f93"],metroMajor:["#8a4b00"],metroMinor:["#3d4a57"],state:["#8794a1"],region:["#0a6f93"],ring:["#0a6f93"],landmark:["#8a5a00"]}}};
let TH=THEMES.dark;
const themeName=()=>document.body.getAttribute("data-theme")==="light"?"light":"dark";

/* ---------- globe ---------- */
const R=10, KM=6371/R;
const [LATC,LONC]=DATA.center;
const P=(lat,lon,h=0)=>{const la=lat*RAD,lo=lon*RAD,r=R+h;return new THREE.Vector3(r*Math.cos(la)*Math.sin(lo),r*Math.sin(la),r*Math.cos(la)*Math.cos(lo))};
const latLonOf=p=>{const r=p.length();return [Math.asin(p.y/r)/RAD,Math.atan2(p.x,p.z)/RAD]};
const box=document.getElementById("scene"), tip=document.getElementById("tip"), hud=document.getElementById("hud");
/* without WebGL (turned off, or no GPU) the page still works: the map shows a notice, every other panel renders */
let renderer,NOGL=false;
try{renderer=new THREE.WebGLRenderer({antialias:true,logarithmicDepthBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputEncoding=THREE.sRGBEncoding}
catch(e){NOGL=true;const d=document.createElement("div");d.className="mm-nogl";d.innerHTML="<p><b>The 3D map needs WebGL</b>, which this browser has turned off or does not support. The roster, filters and the other tabs work without it.</p>";
  renderer={domElement:d,setSize(){},render(){},setPixelRatio(){},capabilities:{getMaxAnisotropy:()=>1}}}
box.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.background=new THREE.Color(TH.bg);
const camera=new THREE.PerspectiveCamera(42,1.6,0.001,100);
const globe=new THREE.Group(); scene.add(globe);
const hemi=new THREE.HemisphereLight(0x9fd6ff,0x0a0f16,0.8); scene.add(hemi);
const key=new THREE.DirectionalLight(0xbfe9ff,0.9); key.position.set(-4,6,10); scene.add(key);
const lift=k=>k*1e-4;                                     // layer lifts in true scale: 1e-4 R = 0.64 km

const groundMat=new THREE.MeshStandardMaterial({color:TH.ground,metalness:0.7,roughness:0.55});
globe.add(new THREE.Mesh(new THREE.SphereGeometry(R,256,128),groundMat));
const gratMat=new THREE.LineBasicMaterial({color:TH.grat,transparent:true,opacity:0.9});
for(let lon=-96;lon<=-76;lon+=0.5){const pts=[];for(let la=35;la<=49;la+=0.25)pts.push(P(la,lon,lift(0.5)));globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),gratMat))}
for(let la=35;la<=49;la+=0.5){const pts=[];for(let lon=-96;lon<=-76;lon+=0.25)pts.push(P(la,lon,lift(0.5)));globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),gratMat))}

function panel(ring,mat,h){if(ring.length>3&&ring[0][0]===ring[ring.length-1][0]&&ring[0][1]===ring[ring.length-1][1])ring=ring.slice(0,-1);
  const pts2=ring.map(([la,lo])=>new THREE.Vector2(lo,la));let tris;try{tris=THREE.ShapeUtils.triangulateShape(pts2,[])}catch(e){return}
  const pos=[];for(const t of tris)for(const i of t){const p=P(ring[i][0],ring[i][1],h);pos.push(p.x,p.y,p.z)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));g.computeVertexNormals();globe.add(new THREE.Mesh(g,mat))}
function outline(ring,mat,h){globe.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ring.map(([la,lo])=>P(la,lo,h))),mat))}

/* the Great Lakes, painted onto a canvas texture on a surface patch; repainted when the theme changes */
const lakeCanvas=document.createElement("canvas"), LK={LAT0:37,LAT1:49,LON0:-93.5,LON1:-75.5,W:4096,H:2736};
lakeCanvas.width=LK.W;lakeCanvas.height=LK.H;
const lakeTex=new THREE.CanvasTexture(lakeCanvas);lakeTex.encoding=THREE.sRGBEncoding;lakeTex.anisotropy=8;lakeTex.minFilter=THREE.LinearMipmapLinearFilter;
function paintLakes(){const cx=lakeCanvas.getContext("2d"),X=lo=>(lo-LK.LON0)/(LK.LON1-LK.LON0)*LK.W,Y=la=>(LK.LAT1-la)/(LK.LAT1-LK.LAT0)*LK.H;
  cx.clearRect(0,0,LK.W,LK.H);cx.beginPath();for(const ring of DATA.lakes){ring.forEach(([la,lo],i)=>i?cx.lineTo(X(lo),Y(la)):cx.moveTo(X(lo),Y(la)));cx.closePath()}
  cx.fillStyle=TH.lakeFill;cx.fill("evenodd");cx.lineWidth=3;cx.strokeStyle=TH.lakeStroke;cx.stroke();lakeTex.needsUpdate=true}
(function lakes(){const NX=180,NY=120,pos=[],uv=[],idx=[];
  for(let j=0;j<=NY;j++)for(let i=0;i<=NX;i++){const la=LK.LAT0+(LK.LAT1-LK.LAT0)*j/NY,lo=LK.LON0+(LK.LON1-LK.LON0)*i/NX;const p=P(la,lo,lift(0.8));pos.push(p.x,p.y,p.z);uv.push(i/NX,j/NY)}
  for(let j=0;j<NY;j++)for(let i=0;i<NX;i++){const a=j*(NX+1)+i,b=a+1,c=a+NX+1,d=c+1;idx.push(a,b,c,b,d,c)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));g.setAttribute("uv",new THREE.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();
  globe.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({map:lakeTex,transparent:true,depthWrite:false})));paintLakes()})();

const coreMat=new THREE.MeshStandardMaterial({color:TH.core,metalness:0.6,roughness:0.5,polygonOffset:true,polygonOffsetFactor:-1});
const farMat=new THREE.MeshStandardMaterial({color:TH.far,metalness:0.6,roughness:0.6,polygonOffset:true,polygonOffsetFactor:-1});
const coreLine=new THREE.LineBasicMaterial({color:TH.coreLine,transparent:true,opacity:0.75}), farLine=new THREE.LineBasicMaterial({color:TH.farLine,transparent:true,opacity:0.9});
for(const k of DATA.counties)for(const ring of k.rings){panel(ring,k.core?coreMat:farMat,lift(1));outline(ring,k.core?coreLine:farLine,lift(k.core?1.6:1.4))}

/* labels: canvas sprites whose color comes from the theme by role; screen-constant size */
const placed=[], KREF=0.052, labels=[];
function place(obj,lat,lon,h,o={}){const mode=o.mode||"screen";if(mode!=="map")obj.scale.multiplyScalar(KREF);obj.userData.lay={lat,lon,h,base:obj.scale.clone(),mode};
  const p=P(lat,lon,h);obj.position.copy(p);if(!obj.isSprite)obj.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),p.clone().normalize());placed.push(obj);(o.group||globe).add(obj);return obj}
function drawLabel(sp){const {text,role,size,weight}=sp.userData.spec,[color,glow]=TH.labels[role]||["#e6edf3"],pad=10,cv=sp.userData.canvas,cx=cv.getContext("2d");
  const font=`${weight} ${size}px Rajdhani, Inter, system-ui, sans-serif`;cx.setTransform(1,0,0,1,0,0);cx.clearRect(0,0,cv.width,cv.height);cx.scale(2,2);cx.font=font;
  if(glow){cx.shadowColor=glow;cx.shadowBlur=12}else{cx.shadowBlur=0}
  cx.fillStyle=color;cx.textBaseline="middle";cx.fillText(text,pad,(size+pad*2)/2);sp.material.map.needsUpdate=true}
function label(text,role,o={}){const size=o.size||22,weight=o.weight||600,pad=10,cv=document.createElement("canvas"),cx=cv.getContext("2d");cx.font=`${weight} ${size}px Rajdhani, Inter, system-ui, sans-serif`;
  const w=Math.ceil(cx.measureText(text).width)+pad*2+8;cv.width=w*2;cv.height=(size+pad*2)*2;
  const t=new THREE.CanvasTexture(cv);t.minFilter=THREE.LinearFilter;const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,depthTest:false,opacity:o.opacity??1}));
  sp.userData.spec={text,role,size,weight};sp.userData.canvas=cv;drawLabel(sp);labels.push(sp);
  const k=o.scale||0.006;sp.scale.set(w*k,(size+pad*2)*k,1);sp.center.set(o.cx??0,0.5);return sp}
const near=new THREE.Group(), mid=new THREE.Group(), far=new THREE.Group(); globe.add(near,mid,far);
const cityDotMat=new THREE.MeshBasicMaterial({color:TH.cityDot}), majorDotMat=new THREE.MeshBasicMaterial({color:TH.dotMajor}), minorDotMat=new THREE.MeshBasicMaterial({color:TH.dotMinor});
for(const [n,[la,lo]] of Object.entries(DATA.cities)){place(new THREE.Mesh(new THREE.SphereGeometry(0.03,10,10),cityDotMat),la,lo,lift(2),{group:near});
  const l=label(n,"city");l.center.set(-0.1,0.5);place(l,la,lo,lift(2),{group:near})}
for(const k of DATA.counties){if(!k.core)continue;const la=k.rings[0].reduce((a,p)=>a+p[0],0)/k.rings[0].length,lo=k.rings[0].reduce((a,p)=>a+p[1],0)/k.rings[0].length;
  place(label(k.name.toUpperCase(),"county",{size:18,weight:500,opacity:0.75,scale:0.0055,cx:0.5}),la,lo,lift(2),{group:near})}
for(const [n,[la,lo,big]] of Object.entries(DATA.metros)){place(new THREE.Mesh(new THREE.SphereGeometry(big?0.05:0.035,12,12),big?majorDotMat:minorDotMat),la,lo,lift(2),{group:big?globe:mid});
  const l=label(n,big?"metroMajor":"metroMinor",{size:big?28:22,weight:big?700:500});l.center.set(-0.1,0.5);place(l,la,lo,lift(2),{group:big?globe:mid})}
for(const [n,[la,lo]] of Object.entries(DATA.states))place(label(n,"state",{size:30,weight:500,opacity:0.8,scale:0.009,cx:0.5}),la,lo,lift(2),{group:far});
place(label("SOUTH BEND–ELKHART","region",{weight:700,cx:0.5}),LATC-0.28,LONC+0.1,lift(3),{group:far});

/* Notre Dame Main Building: schematic, ten times its footprint, compass-oriented, shown only at the closest zoom */
/* the Main Building, textured from a CC BY-SA photo of its south front (see img/LICENSE-landmark.txt).
   Local frame: x east, y up, z south. The front is a cut-out photo of the facade; the sides, wings and drum
   repeat bays and faces of the same photo; the dome stays modeled gold so it catches the light. */
const dome=(function(){const g=new THREE.Group(),B=0.0016,TL=new THREE.TextureLoader(),aniso=renderer.capabilities.getMaxAnisotropy();
  const tex=(n,rep)=>{const t=TL.load("img/landmark-"+n+".webp");t.encoding=THREE.sRGBEncoding;t.anisotropy=aniso;if(rep)t.wrapS=t.wrapT=THREE.RepeatWrapping;return t};
  const T={facade:tex("facade"),bay:tex("bay",1),roof:tex("roof",1),drum:tex("drum",1)};
  const photo=(map,shade,o)=>new THREE.MeshBasicMaterial(Object.assign({map,color:new THREE.Color(shade,shade,shade)},o||{}));
  const uv=(geo,su,sv)=>{const a=geo.attributes.uv;for(let i=0;i<a.count;i++)a.setXY(i,a.getX(i)*su,a.getY(i)*sv);return geo};
  const add=(geo,mat,x,y,z)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x*B,y*B,z*B);g.add(m);return m};
  /* polished gold: metal only shines when it has something to reflect, so the gold gets its own small studio
     environment (sky gradient, warm horizon, bright soft-box highlights) prefiltered for image-based lighting */
  const env=(function(){const cv=document.createElement("canvas");cv.width=1024;cv.height=512;const x=cv.getContext("2d");
    const g=x.createLinearGradient(0,0,0,512);g.addColorStop(0,"#ffffff");g.addColorStop(0.3,"#e4eeff");g.addColorStop(0.48,"#fff6dc");g.addColorStop(0.53,"#ffd98a");g.addColorStop(0.62,"#d9a441");g.addColorStop(1,"#8a6424");
    x.fillStyle=g;x.fillRect(0,0,1024,512);
    for(const [cx,cy,r,a] of [[180,120,70,1],[560,90,55,0.95],[860,150,80,1],[360,210,40,0.8],[720,230,35,0.7],[90,330,60,0.6],[620,360,70,0.55]]){const rg=x.createRadialGradient(cx,cy,0,cx,cy,r);rg.addColorStop(0,"rgba(255,255,255,"+a+")");rg.addColorStop(1,"rgba(255,255,255,0)");x.fillStyle=rg;x.fillRect(cx-r,cy-r,2*r,2*r)}
    const t=new THREE.CanvasTexture(cv);t.mapping=THREE.EquirectangularReflectionMapping;t.encoding=THREE.sRGBEncoding;
    if(NOGL)return t;const pm=new THREE.PMREMGenerator(renderer);const out=pm.fromEquirectangular(t).texture;pm.dispose();t.dispose();return out})();
  const gold=new THREE.MeshStandardMaterial({color:0xffc94a,metalness:1,roughness:0.1,envMap:env,envMapIntensity:2.4,emissive:0x5a3c00,emissiveIntensity:0.22});
  /* plan from an aerial photo, heights from the frontal photo, in units of B (origin at the dome, x east, z south):
     a long east-west range crossed by a north-south spine; the spine ends south in the wide front pavilion
     (the photographed facade, 0.62 wide) and north in a short arm. Wall cornice 0.383, mansard top 0.44, a window
     bay 0.0556 wide; the drum is an octagon 0.25 across under the gold dome. */
  const HC=0.383,HM=0.44,BAY=0.0556,FW=0.62,FH=FW*853/1024;
  const wall=(w,h,x,y,z,rot,shade)=>{const geo=uv(new THREE.PlaneGeometry(w*B,h*B),Math.max(1,Math.round(w/BAY)),1);geo.rotateY(rot);return add(geo,photo(T.bay,shade),x,y,z)};
  const box4=(cx,cz,w,d)=>{wall(w,HC,cx,HC/2,cz+d/2,0,1);wall(w,HC,cx,HC/2,cz-d/2,Math.PI,0.62);wall(d,HC,cx+w/2,HC/2,cz,Math.PI/2,0.8);wall(d,HC,cx-w/2,HC/2,cz,-Math.PI/2,0.8)};
  const slate=photo(T.roof,0.92),slateTop=new THREE.MeshBasicMaterial({color:0x4a5258});
  const mansard=(cx,cz,w,d)=>{const geo=uv(new THREE.CylinderGeometry(0.8,1,(HM-HC)*B,4,1,true,Math.PI/4),8,1);geo.scale(w*B/2/Math.SQRT1_2,1,d*B/2/Math.SQRT1_2);
    add(geo,slate,cx,(HC+HM)/2,cz);const top=new THREE.PlaneGeometry(w*B*0.8,d*B*0.8);top.rotateX(-Math.PI/2);add(top,slateTop,cx,HM+0.001,cz)};
  const block=(x0,x1,z0,z1)=>{box4((x0+x1)/2,(z0+z1)/2,x1-x0,z1-z0);mansard((x0+x1)/2,(z0+z1)/2,x1-x0,z1-z0)};
  block(-0.87,-0.6,-0.19,0.17);block(0.55,0.81,-0.16,0.17);                 /* end pavilions of the east-west range */
  block(-0.6,-0.17,-0.2,0.25);block(0.17,0.55,-0.24,0.21);                  /* the range between them and the crossing */
  block(-0.18,0.18,-0.41,0.32);                                             /* the spine: north arm, crossing, south arm */
  block(-FW/2,FW/2,0.32,0.63);                                              /* the front pavilion */
  add(new THREE.PlaneGeometry(FW*B,FH*B),photo(T.facade,1,{alphaTest:0.5}),0,FH/2,0.632);
  const ridge=new THREE.CylinderGeometry(1,1,0.3*B,3);ridge.rotateX(-Math.PI/2);const sx=0.54*FW/2/0.866,sy=(FH-0.407)/1.5;ridge.scale(sx*B,sy*B,1);
  add(uv(ridge,4,1),slate,0,0.407+0.5*sy,0.475);
  /* drum: a plain octagon up from the roof, then the photo's drum face repeated on its eight sides */
  const R=0.125,drumBase=new THREE.MeshBasicMaterial({color:0xb9b3a3});
  const oct=(h,mat,y,rTop,rBot)=>{const geo=new THREE.CylinderGeometry((rTop||R)*B,(rBot||R)*B,h*B,8,1,true,Math.PI/8);return add(geo,mat,0,y,0)};
  oct(0.535-HM+0.01,drumBase,(HM+0.535)/2-0.005);
  const face=oct(0.076,photo(T.drum,1,{alphaTest:0.5}),0.573);uv(face.geometry,8,1);
  oct(0.009,new THREE.MeshBasicMaterial({color:0xe6dfcc}),0.615,R*0.95,R*1.04);
  /* the gold dome, octagonal in plan like the drum, its lantern and statue */
  const dm=add(new THREE.SphereGeometry(0.112*B,8,24,Math.PI/8,Math.PI*2,0,Math.PI/2),gold,0,0.619,0);dm.scale.y=1.3;
  add(new THREE.CylinderGeometry(0.026*B,0.03*B,0.045*B,8,1,false,Math.PI/8),gold,0,0.786,0);add(new THREE.CylinderGeometry(0.007*B,0.015*B,0.045*B,8),gold,0,0.83,0);add(new THREE.SphereGeometry(0.01*B,10,8),gold,0,0.858,0);
  const glint=new THREE.PointLight(0xfff2c0,1.4,B*8);glint.position.set(-0.6*B,1.6*B,1.2*B);g.add(glint);
  place(g,DATA.landmark.lat,DATA.landmark.lon,lift(1.8),{mode:"map"});
  const lo=DATA.landmark.lon*RAD,east=new THREE.Vector3(Math.cos(lo),0,-Math.sin(lo)),upv=P(DATA.landmark.lat,DATA.landmark.lon).normalize(),south=new THREE.Vector3().crossVectors(east,upv).normalize();
  g.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(east,upv,south));
  place(label(DATA.landmark.name.toUpperCase(),"landmark",{size:18,weight:700,scale:0.0055,cx:0.5}),DATA.landmark.lat,DATA.landmark.lon,0.003,{group:near});return g})();

/* company columns: instanced. barMesh = in the filter, glowMesh = its glow, dimMesh = the rest (dark or pale, mostly transparent) */
const barH=c=>c.emp?0.08+0.15*Math.log10(Math.max(c.emp,10)):0.09;
function shadedUnit(w){const g=new THREE.BoxGeometry(w,1,w);g.translate(0,0.5,0);const shade=[0.72,0.72,1,0.5,0.86,0.86],col=new Float32Array(72);
  for(let f=0;f<6;f++)for(let v=0;v<4;v++){const i=f*4+v;col[3*i]=col[3*i+1]=col[3*i+2]=shade[f]}g.setAttribute("color",new THREE.BufferAttribute(col,3));return g}
const NB=C.length, W=0.045;
const barMesh=new THREE.InstancedMesh(shadedUnit(W),new THREE.MeshBasicMaterial({vertexColors:true}),NB);
const dimMesh=new THREE.InstancedMesh(shadedUnit(W),new THREE.MeshBasicMaterial({vertexColors:true,transparent:true,opacity:0.12,depthWrite:false}),NB);
const glowMesh=new THREE.InstancedMesh((()=>{const g=new THREE.BoxGeometry(W*1.9,1.04,W*1.9);g.translate(0,0.52,0);return g})(),new THREE.MeshBasicMaterial({transparent:true,opacity:0.09,blending:THREE.AdditiveBlending,depthWrite:false}),NB);
for(const m of [barMesh,dimMesh,glowMesh])m.instanceColor=new THREE.InstancedBufferAttribute(new Float32Array(NB*3),3);
globe.add(dimMesh,barMesh,glowMesh);
const bars=C.map((c,i)=>{const p=P(c.lat,c.lon,lift(2.2));return {c,i,h:barH(c),pos:p,quat:new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),p.clone().normalize()),color:new THREE.Color(SCOL[c.sector]).convertSRGBToLinear()}});
let onList=[], offList=[], lastK=KREF;
const halo=new THREE.Mesh(new THREE.RingGeometry(0.09,0.12,32),new THREE.MeshBasicMaterial({color:TH.halo,side:THREE.DoubleSide,transparent:true,opacity:0}));halo.geometry.rotateX(-Math.PI/2);halo.scale.setScalar(KREF);globe.add(halo);
const _m=new THREE.Matrix4(),_s=new THREE.Vector3(),_c=new THREE.Color(),_w=new THREE.Color();
function assignBars(){onList=[];offList=[];for(const b of bars){const on=st.hot?(visible(b.c)&&hotMatch(b.c)):visible(b.c);b.oi=(on?onList:offList).length;(on?onList:offList).push(b)}
  barMesh.count=glowMesh.count=onList.length;dimMesh.count=offList.length}
function layoutBars(k){lastK=k;const set=(mesh,list)=>{list.forEach((b,i)=>{_s.set(k,k*b.h,k);_m.compose(b.pos,b.quat,_s);mesh.setMatrixAt(i,_m)});mesh.instanceMatrix.needsUpdate=true};
  set(barMesh,onList);set(glowMesh,onList);set(dimMesh,offList);
  const sel=st.sel&&bars[C.indexOf(byId[st.sel])];if(sel){halo.position.copy(P(sel.c.lat,sel.c.lon,lift(2.4)));halo.quaternion.copy(sel.quat);halo.scale.setScalar(k)}}
function paintBars(){assignBars();
  onList.forEach((b,i)=>{const lit=hoverId===b.c.id||st.sel===b.c.id||!!st.hot;_c.copy(b.color).multiplyScalar(lit?1.6:(b.c.emp?1:0.55));barMesh.setColorAt(i,_c);_c.copy(b.color).multiplyScalar(lit?2.2:1);glowMesh.setColorAt(i,_c)});
  if(TH.dimMix)_w.set(TH.dimMix).convertSRGBToLinear();
  offList.forEach((b,i)=>{_c.copy(b.color);if(TH.dimMix)_c.lerp(_w,TH.dimK);else _c.multiplyScalar(TH.dimK);dimMesh.setColorAt(i,_c)});
  for(const m of [barMesh,glowMesh,dimMesh])m.instanceColor.needsUpdate=true;
  halo.material.opacity=st.sel?0.9:0;layoutBars(lastK)}


/* distance rings, centered on the selected company or the campus */
const ringGroup=new THREE.Group();ringGroup.visible=false;globe.add(ringGroup);
const ringMat=new THREE.LineDashedMaterial({color:TH.ring,dashSize:0.004,gapSize:0.003,transparent:true,opacity:0.75});
let ringKey="";
function buildRings(){const c=center(),k=c.lat+":"+c.lon;if(k===ringKey)return;ringKey=k;
  for(const o of [...ringGroup.children]){ringGroup.remove(o);const i=placed.indexOf(o);if(i>=0)placed.splice(i,1);const j=labels.indexOf(o);if(j>=0)labels.splice(j,1)}
  const la0=c.lat*RAD,lo0=c.lon*RAD;
  for(const r of [25,50,100]){const pts=[],dr=r/6371;
    for(let i=0;i<=180;i++){const brg=i*2*RAD,la=Math.asin(Math.sin(la0)*Math.cos(dr)+Math.cos(la0)*Math.sin(dr)*Math.cos(brg)),lo=lo0+Math.atan2(Math.sin(brg)*Math.sin(dr)*Math.cos(la0),Math.cos(dr)-Math.sin(la0)*Math.sin(la));pts.push(P(la/RAD,lo/RAD,lift(2.6)))}
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),ringMat);line.computeLineDistances();ringGroup.add(line);
    const la=Math.asin(Math.sin(la0)*Math.cos(dr)+Math.cos(la0)*Math.sin(dr));place(label(r+" km","ring",{size:18,scale:0.0055,cx:0.5}),la/RAD,c.lon,lift(3),{group:ringGroup})}
  layout()}

function applyTheme(){TH=THEMES[themeName()];scene.background.set(TH.bg);hemi.color.setHex(TH.hemi[0]);hemi.groundColor.setHex(TH.hemi[1]);hemi.intensity=TH.hemi[2];key.intensity=TH.key;
  groundMat.color.setHex(TH.ground);groundMat.metalness=TH.groundMetal;gratMat.color.setHex(TH.grat);
  coreMat.color.setHex(TH.core);farMat.color.setHex(TH.far);coreMat.metalness=farMat.metalness=TH.landMetal;coreLine.color.setHex(TH.coreLine);coreLine.opacity=TH.coreLineOp;farLine.color.setHex(TH.farLine);
  cityDotMat.color.setHex(TH.cityDot);majorDotMat.color.setHex(TH.dotMajor);minorDotMat.color.setHex(TH.dotMinor);ringMat.color.setHex(TH.ring);halo.material.color.setHex(TH.halo);
  glowMesh.material.opacity=TH.glow;glowMesh.visible=TH.glow>0;dimMesh.material.opacity=TH.dimOp;
  paintLakes();labels.forEach(drawLabel);paintBars();if(typeof renderQcew==="function")renderQcew()}

/* ---------- view: one continuous zoom on a true-scale globe ---------- */
const D_MIN=0.005, D_MAX=1.35, D_HOME=0.26;            // 0.005 ≈ 3 km up, close enough to see the dome
const view={lat:LATC,lon:LONC,dist:D_HOME}, home={...view};
const tiltFor=d=>0.58*(1-THREE.MathUtils.smoothstep(Math.log(d),Math.log(0.12),Math.log(1.3)))+0.08;
function layout(){const d=view.dist,screen=d/D_HOME;
  for(const o of placed){const L=o.userData.lay;if(L.mode==="map")continue;o.scale.copy(L.base).multiplyScalar(screen)}
  layoutBars(KREF*Math.min(screen,2.2));
  glowMesh.visible=TH.glow>0;
  near.visible=d<0.55;mid.visible=d>0.45;far.visible=d>0.7;dome.visible=d<0.09;ringGroup.visible=st.rings;
  hud.innerHTML=`<span>ALT</span> ${(d*KM).toFixed(d<0.05?1:0)} km &nbsp; <span>CTR</span> ${view.lat.toFixed(3)}°N ${(-view.lon).toFixed(3)}°W &nbsp; <span>SPAN</span> ${(2*d*Math.tan(0.3665)*KM).toFixed(0)} km`}
function applyView(){layout();const d=view.dist,t=tiltFor(d);globe.rotation.set(view.lat*RAD,-view.lon*RAD,0);
  camera.near=Math.max(0.0005,d*0.04);camera.far=d*60+2*R;camera.updateProjectionMatrix();camera.position.set(0,-d*Math.sin(t),R+d*Math.cos(t));camera.lookAt(0,0,R)}
let tween=null;
function flyTo(lat,lon,dist){const from={...view},to={lat,lon,dist:dist??view.dist};if(reduced){Object.assign(view,to);applyView();return}
  tween={from,to,t0:performance.now(),dur:700}}
const ray=new THREE.Raycaster(),ndc=new THREE.Vector2();
const pickSphere=new THREE.Mesh(new THREE.SphereGeometry(R,64,32),new THREE.MeshBasicMaterial({visible:false}));globe.add(pickSphere);
function toNdc(e){const r=renderer.domElement.getBoundingClientRect();ndc.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(ndc,camera)}
function surfaceAt(e){toNdc(e);const h=ray.intersectObject(pickSphere,false)[0];return h?latLonOf(globe.worldToLocal(h.point.clone())):null}
function pick(e){toNdc(e);
  const hit=ray.intersectObject(barMesh,false)[0];return hit&&hit.instanceId!=null?onList[hit.instanceId]:null}
let drag=null,hoverId=null;
box.addEventListener("pointerdown",e=>{if(e.target.closest(".mm-ctl"))return;tween=null;drag={x:e.clientX,y:e.clientY,lat:view.lat,lon:view.lon,moved:false};box.setPointerCapture(e.pointerId)});
box.addEventListener("pointermove",e=>{if(drag){const r=renderer.domElement.getBoundingClientRect(),k=(2*view.dist*Math.tan(0.3665)/r.height)/(R*RAD);
    view.lat=THREE.MathUtils.clamp(drag.lat+(e.clientY-drag.y)*k,36,48);view.lon=THREE.MathUtils.clamp(drag.lon-(e.clientX-drag.x)*k/Math.cos(view.lat*RAD),-95,-77);
    if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>4)drag.moved=true;applyView();tip.style.opacity=0}else hover(e)});
box.addEventListener("pointerup",e=>{if(drag&&!drag.moved){const b=pick(e);if(b)select(b.c.id)}drag=null});
box.addEventListener("pointerleave",()=>{tip.style.opacity=0});
function zoomBy(f,e){tween=null;const d0=view.dist,d1=THREE.MathUtils.clamp(d0*f,D_MIN,D_MAX);
  if(e&&d1!==d0){const ll=surfaceAt(e);if(ll){const k=1-d1/d0;view.lat+=(ll[0]-view.lat)*k;view.lon+=(ll[1]-view.lon)*k}}view.dist=d1;applyView()}
box.addEventListener("wheel",e=>{e.preventDefault();zoomBy(Math.exp(Math.sign(e.deltaY)*0.12),e)},{passive:false});
let pinch=null;box.addEventListener("touchstart",e=>{if(e.touches.length===2)pinch=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY)},{passive:true});
box.addEventListener("touchmove",e=>{if(e.touches.length===2&&pinch){const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY);zoomBy(pinch/d);pinch=d}},{passive:true});
document.getElementById("zin").onclick=()=>zoomBy(0.7);document.getElementById("zout").onclick=()=>zoomBy(1/0.7);
document.getElementById("reset").onclick=()=>flyTo(home.lat,home.lon,home.dist);
document.getElementById("campus").onclick=()=>flyTo(DATA.landmark.lat,DATA.landmark.lon,0.008);
function hover(e){const b=pick(e);const id=b&&b.c?b.c.id:null;if(id!==hoverId){hoverId=id;paintBars()}
  const r=renderer.domElement.getBoundingClientRect();
  if(b){barMesh.getMatrixAt(b.oi,_m);const top=new THREE.Vector3(0,1,0).applyMatrix4(_m).applyMatrix4(globe.matrixWorld).project(camera);const g=groupOf(b.c);
    tip.innerHTML=`<b>${esc(b.c.name)}</b>${esc(b.c.city)}, ${esc(b.c.state)} · ${esc(b.c.sector)}${g.sites.length>1?`<div class="m">one of ${g.sites.length} sites of ${esc(g.name)}</div>`:""}<div class="m">${esc(fmtEmp(b.c))} employees</div>`;
    tip.style.left=((top.x+1)/2*r.width)+"px";tip.style.top=((1-top.y)/2*r.height)+"px";tip.style.opacity=1;box.style.cursor="pointer"}
  else{tip.style.opacity=0;box.style.cursor=drag?"grabbing":"grab"}}
function resize(){if(!box.clientWidth)return;const w=box.clientWidth,h=Math.max(360,Math.min(640,Math.round(w*0.64)));box.style.height=h+"px";renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}

/* ---------- company search ---------- */
const find=document.getElementById("find"),sug=document.getElementById("find-list");let sugItems=[],sugIdx=-1;
function searchItems(q){q=q.trim().toLowerCase();if(q.length<2)return [];const out=[],seen=new Set();
  for(const g of Object.values(GROUPS))if(g.sites.length>1&&g.name.toLowerCase().includes(q)){out.push({kind:"group",g});seen.add(g.id)}
  for(const c of C){if(out.length>=40)break;if(c.name.toLowerCase().includes(q)||(c.formerly&&c.formerly.toLowerCase().includes(q))||c.city.toLowerCase().startsWith(q))out.push({kind:"site",c})}
  return out.sort((a,b)=>{const na=(a.g?a.g.name:a.c.name).toLowerCase(),nb=(b.g?b.g.name:b.c.name).toLowerCase();return (nb.startsWith(q)-na.startsWith(q))||(a.kind==="group"?-1:0)-(b.kind==="group"?-1:0)||na.localeCompare(nb)}).slice(0,10)}
function showSug(){sugItems=searchItems(find.value);sugIdx=sugItems.length?0:-1;
  sug.innerHTML=sugItems.map((it,i)=>it.kind==="group"?`<div class="mm-sugi" role="option" id="sug-${i}" data-i="${i}" aria-selected="${i===sugIdx}"><b>${esc(it.g.name)}</b><span>${it.g.sites.length} sites</span></div>`
    :`<div class="mm-sugi" role="option" id="sug-${i}" data-i="${i}" aria-selected="${i===sugIdx}"><b>${esc(it.c.name)}</b><span>${it.c.formerly?"formerly "+esc(it.c.formerly)+" · ":""}${esc(it.c.city)} · ${esc(it.c.sector)}</span></div>`).join("")||(find.value.trim().length>1?`<div class="mm-sugi none">No company matches “${esc(find.value)}”.</div>`:"");
  sug.hidden=!sug.innerHTML;find.setAttribute("aria-expanded",String(!sug.hidden));find.setAttribute("aria-activedescendant",sugIdx>=0?"sug-"+sugIdx:"")}
function choose(it){if(!it)return;sug.hidden=true;find.setAttribute("aria-expanded","false");
  if(it.kind==="group"){const s=it.g.sites,la=s.reduce((a,c)=>a+c.lat,0)/s.length,lo=s.reduce((a,c)=>a+c.lon,0)/s.length,ext=Math.max(...s.map(c=>km(la,lo,c.lat,c.lon)));
    st.open.add(it.g.id);const big=s.slice().sort((a,b)=>(b.emp||0)-(a.emp||0))[0];st.sel=big.id;flyTo(la,lo,THREE.MathUtils.clamp(ext/KM*2.6,0.04,1.2));render()}
  else{st.sel=it.c.id;if(groupOf(it.c).sites.length>1)st.open.add(it.c.group);flyTo(it.c.lat,it.c.lon,Math.min(view.dist,0.05));render()}
  find.value="";const row=st.sel&&document.getElementById("row-"+st.sel);if(row)row.scrollIntoView({block:"nearest"})}
find.addEventListener("input",showSug);find.addEventListener("focus",showSug);
find.addEventListener("keydown",e=>{if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();if(!sugItems.length)return;sugIdx=(sugIdx+(e.key==="ArrowDown"?1:-1)+sugItems.length)%sugItems.length;
    sug.querySelectorAll(".mm-sugi").forEach((el,i)=>el.setAttribute("aria-selected",String(i===sugIdx)));find.setAttribute("aria-activedescendant","sug-"+sugIdx)}
  else if(e.key==="Enter"){e.preventDefault();choose(sugItems[sugIdx])}else if(e.key==="Escape"){sug.hidden=true;find.setAttribute("aria-expanded","false")}});
sug.addEventListener("mousedown",e=>{const el=e.target.closest("[data-i]");if(el){e.preventDefault();choose(sugItems[+el.dataset.i])}});
find.addEventListener("blur",()=>setTimeout(()=>{sug.hidden=true;find.setAttribute("aria-expanded","false")},120));

/* ---------- panels ---------- */
const ARROW=d=>d<0?" ▾":" ▴";
function HH(kind,cols,lead){const s=st.sort[kind];return `<div class="mm-hh"><span>${lead||"sort by"}</span>`+cols.map(c=>`<button type="button" data-kind="${kind}" data-sort="${c.key}" aria-pressed="${s.key===c.key}" title="Sort by ${esc(c.title||c.label)}">${esc(c.label)}${s.key===c.key?ARROW(s.dir):""}</button>`).join("")+`</div>`}
const sorter=kind=>{const s=st.sort[kind];return (a,b)=>{const va=a[s.key],vb=b[s.key];const r=typeof va==="string"?va.localeCompare(vb):((va||0)-(vb||0));return r*s.dir||(b.n||0)-(a.n||0)||(b.e||0)-(a.e||0)||String(a.label||"").localeCompare(String(b.label||""))}};
const SORTCOLS=[{key:"n",label:"cos",title:"number of companies"},{key:"e",label:"staff"}];
function bar(cls,label,n,max,e,emax,pressed,extra,col,eText){return `<button type="button" class="mm-bar ${cls} ${n?"":"zero"}" aria-pressed="${pressed}" ${extra} ${col?`style="--c:${col}"`:""}><span class="lab">${col?`<span class="mm-dot" style="background:${col};color:${col}"></span>`:""}<span>${label}</span><span class="trk"><span class="fil" style="width:${max?Math.round(100*n/max):0}%"></span><span class="fil2" style="width:${emax?Math.round(100*e/emax):0}%"></span></span></span><span class="n">${n}</span><span class="e">${eText??(e?fmtK(e):"–")}</span></button>`}
function renderSectors(){const base=C.filter(visibleExcept("sec"));const rows=DATA.sectors.map(s=>{const l=base.filter(c=>c.sector===s);return {label:s,n:nGroups(l),e:empSum(l)}}).sort(sorter("sec"));
  const max=Math.max(1,...rows.map(x=>x.n)),emax=Math.max(1,...rows.map(x=>x.e));
  document.getElementById("sectors").innerHTML=HH("sec",SORTCOLS)+rows.map(({label:s,n,e})=>bar("sec",esc(s),n,max,e,emax,st.sec.has(s),`data-sec="${esc(s)}"`,SCOL[s])).join("")}
function renderTags(){const base=C.filter(visibleExcept("tag"));let rows=TAGS.map(t=>{const l=base.filter(c=>c.tags.includes(t));return {label:t,n:nGroups(l),e:empSum(l)}}).sort(sorter("tag"));
  if(st.q)rows=rows.filter(x=>x.label.toLowerCase().includes(st.q));const max=Math.max(1,...rows.map(x=>x.n)),emax=Math.max(1,...rows.map(x=>x.e));
  document.getElementById("tags").innerHTML=HH("tag",SORTCOLS)+(rows.slice(0,150).map(({label:t,n,e})=>bar("tag",esc(t),n,max,e,emax,st.tag.has(t),`data-tag="${esc(t)}"`)).join("")||`<p class="mm-count">No product matches “${esc(st.q)}”.</p>`);
  document.getElementById("tagcount").textContent=`${TAGS.length} categories`}
function renderFederal(){const rows=C.filter(visible),withFed=rows.filter(c=>c.federal),total=withFed.reduce((a,c)=>a+c.federal.total,0);
  const bySec=DATA.sectors.map(s=>{const l=withFed.filter(c=>c.sector===s);return {label:s,e:l.reduce((a,c)=>a+c.federal.total,0),n:nGroups(l)}}).filter(x=>x.e>0).sort(sorter("fed"));
  const smax=Math.max(1,...bySec.map(x=>x.e)),ag=DATA.federalAgencies.slice(0,8),amax=Math.max(1,...ag.map(a=>a.contracts+a.grants));
  const sbirN=rows.filter(c=>c.sbir),patN=rows.filter(c=>c.patents);
  document.getElementById("fedcount").textContent=DATA.federalPulled?`USAspending, FY2016 to ${DATA.federalPulled.slice(0,4)}`:"";
  document.getElementById("federal").innerHTML=`<p class="mm-fedsum"><b>${nGroups(withFed)}</b> of the ${nGroups(rows)} companies shown hold federal contracts or grants since FY2016, <b>${fmtUSD(total)}</b> in all; <b>${nGroups(sbirN)}</b> hold SBIR/STTR awards${patN.length?`; <b>${nGroups(patN)}</b> hold patents granted since 2015`:""}.</p>`
    +HH("fed",[{key:"n",label:"cos",title:"number of companies"},{key:"e",label:"$",title:"federal dollars"}],"by sector (companies shown)")
    +bySec.map(({label:s,e:v,n})=>bar("sec",esc(s),v,smax,0,0,st.sec.has(s),`data-sec="${esc(s)}"`,SCOL[s],fmtUSD(v)).replace(`<span class="n">${v}</span>`,`<span class="n">${n}</span>`)).join("")
    +`<div class="mm-hh" style="margin-top:8px"><span>region-wide, by awarding agency (all recipients, work performed here)</span><span></span><span>$</span></div>`
    +ag.map(a=>`<div class="mm-bar ag" style="cursor:default"><span class="lab"><span>${esc(a.name)}</span><span class="trk"><span class="fil" style="width:${Math.round(100*(a.contracts+a.grants)/amax)}%;background:var(--accent-2)"></span></span></span><span class="n"></span><span class="e">${fmtUSD(a.contracts+a.grants)}</span></div>`).join("")}
function renderCaps(){const base=C.filter(visibleExcept("cap"));
  const rows=DATA.capabilities.map(k=>{const l=base.filter(c=>c.caps.includes(k));const big=l.slice().sort((a,b)=>(b.emp||0)-(a.emp||0))[0];return {label:k,n:nGroups(l),e:empSum(l),big}}).sort(sorter("cap"));
  const max=Math.max(1,...rows.map(x=>x.n)),emax=Math.max(1,...rows.map(x=>x.e));
  document.getElementById("caps").innerHTML=HH("cap",SORTCOLS,"process capability · largest site")+rows.map(({label:k,n,e,big})=>bar(n<=1?"gap":"",esc(k)+(n<=1?' <span class="g">gap</span>':"")+(big?` <span class="mm-count">· ${esc(groupOf(big).name)}</span>`:""),n,max,e,emax,st.cap.has(k),`data-cap="${esc(k)}"`)).join("")}
function renderQcew(){const el=document.getElementById("qcew");document.querySelectorAll("[data-qv]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.qv===st.qv)));
  document.querySelectorAll("[data-qs]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.qs===st.qs)));
  const core=["18141","18039","18099","18091","18085"],ccols=["#3b8ff0","#a78bfa","#1fd28c","#ffc233","#ff6a2a"],dimc=getComputedStyle(document.getElementById("mm-app")).getPropertyValue("--fg-3").trim()||"#627386";
  let series=[];
  if(st.qv==="county"){const q=DATA.qcew||{};series=Object.keys(q).map(k=>{const ci=core.indexOf(k);return {name:q[k].name.replace(", IN","").replace(", MI"," (MI)"),pts:Object.fromEntries(Object.entries(q[k].years).map(([y,v])=>[+y,v.emp])),color:ci<0?dimc:ccols[ci],main:ci>=0,order:ci<0?99:ci}})}
  else{const q=DATA.qcewSectors||{};series=Object.keys(q).map(s=>({name:s,pts:Object.fromEntries(Object.entries(q[s]).map(([y,v])=>[+y,v])),color:SCOL[s]||dimc,main:true,order:DATA.sectors.indexOf(s)}))}
  series=series.filter(s=>Object.keys(s.pts).length>1);if(!series.length){el.innerHTML=`<p class="mm-count">No employment data yet.</p>`;return}
  const years=[...new Set(series.flatMap(s=>Object.keys(s.pts).map(Number)))].sort((a,b)=>a-b),y0=years[0],y1=years[years.length-1];
  if(st.qs==="idx")for(const s of series){const b=s.pts[y0]||Object.values(s.pts)[0];s.pts=Object.fromEntries(Object.entries(s.pts).map(([y,v])=>[+y,b?100*v/b:0]))}
  const all=series.flatMap(s=>Object.values(s.pts)),vmax=Math.max(...all),vmin=st.qs==="idx"?Math.min(...all,100):0;
  const Wd=600,Hd=250,L=46,Rr=st.qv==="sector"?190:128,T=10,B=26,X=y=>L+(y-y0)/(y1-y0||1)*(Wd-L-Rr),Y=v=>T+(1-(v-vmin)/((vmax-vmin)||1))*(Hd-T-B);
  let svg=`<svg viewBox="0 0 ${Wd} ${Hd}" role="img" aria-label="Manufacturing employment ${st.qv==="county"?"by county":"by sector"}, ${y0} to ${y1}${st.qs==="idx"?", indexed to "+y0+" = 100":""}">`;
  for(let i=0;i<=4;i++){const v=vmin+(vmax-vmin)*i/4;svg+=`<line class="gr" x1="${L}" x2="${Wd-Rr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L-6}" y="${Y(v)+3}" text-anchor="end">${st.qs==="idx"?Math.round(v):fmtK(Math.round(v))}</text>`}
  for(const y of years)if((y-y0)%3===0||y===y1)svg+=`<text x="${X(y)}" y="${Hd-8}" text-anchor="middle">${y}</text>`;
  const ends=[];for(const s of series.slice().sort((a,b)=>b.order-a.order)){const ys=years.filter(y=>s.pts[y]!=null);
    svg+=`<polyline class="ln ${s.main?"":"dim"}" points="${ys.map(y=>X(y).toFixed(1)+","+Y(s.pts[y]).toFixed(1)).join(" ")}" stroke="${s.color}"/>`;
    if(s.main){const ly=ys[ys.length-1];ends.push({y:Y(s.pts[ly]),x:X(ly),s,v:s.pts[ly]})}}
  ends.sort((a,b)=>a.y-b.y);for(let i=1;i<ends.length;i++)if(ends[i].y-ends[i-1].y<11)ends[i].y=ends[i-1].y+11;
  for(const e of ends)svg+=`<text class="lbl" x="${e.x+6}" y="${e.y+3}" fill="${e.s.color}">${esc(e.s.name)} ${st.qs==="idx"?Math.round(e.v):fmtK(Math.round(e.v))}</text>`;
  el.innerHTML=svg+`</svg>`;
  document.getElementById("qcewnote").textContent=`BLS QCEW, private, ${y0}–${y1}${st.qv==="sector"?" · lower bound, withheld cells":""}${st.qs==="idx"?" · "+y0+" = 100":""}`}
/* ---------- humanoid deployment benefit index: five pillars against the U.S. (= 100); local supply against a fixed target ---------- */
const GRADES=[["A",150],["B",125],["C",105],["D",95],["E",80],["F",60],["G",-Infinity]],grade=v=>v==null?null:GRADES.find(([,t])=>v>=t)[0];
const BAND=["far ahead of the U.S.","well ahead of the U.S.","ahead of the U.S.","about the U.S. level","behind the U.S.","well behind the U.S.","far behind the U.S."],
  gbadge=v=>{const g=grade(v);if(!g)return "";const t=`${Math.round(v)}: ${BAND[GRADES.findIndex(x=>x[0]===g)]} (100 = the U.S. level; for local supply, half the robot available locally)`;return `<span class="mm-gsw g${g}" role="img" aria-label="${t}" title="${t}"></span>`};
/* Notre Dame's physical-AI research awards (federal prime awards and subawards) */
function ndResearch(){const R=DATA.ndResearch;if(!R||!R.awards||!R.awards.length)return "";
  const A=R.awards,tot=A.reduce((a,x)=>a+x.amount,0),today=new Date().toISOString().slice(0,10),active=A.filter(x=>x.end&&x.end>=today),
    ag={};for(const x of A){const k=x.agency.replace("National Science Foundation","NSF").replace("National Aeronautics and Space Administration","NASA").replace("Department of Defense","DoD").replace("Department of Health and Human Services","NIH/HHS").replace("Department of Energy","DOE");ag[k]=(ag[k]||0)+x.amount}
  const yr={};for(const x of A){const y=x.start.slice(0,4);if(y)yr[y]=(yr[y]||0)+x.amount}const ys=Object.keys(yr).sort(),ymax=Math.max(1,...Object.values(yr));
  const tp={};for(const x of A)for(const t of x.topics)tp[t]=(tp[t]||0)+1;
  const rows=A.map(x=>({...x,agencyShort:x.agency.replace("National Science Foundation","NSF").replace("National Aeronautics and Space Administration","NASA").replace("Department of Defense","DoD").replace("Department of Health and Human Services","NIH/HHS"),type:x.kind==="subaward"?"subaward via "+x.via:x.kind}));
  const shown=st.ndrAll?rows:null;
  return `<h3 class="mm-wh" style="margin-top:16px">Notre Dame physical-AI research</h3>
    <div class="mm-htiles" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      <div class="mm-htile"><div class="k">Federal awards since FY2016</div><div class="v">${fmtUSD(tot)}</div><div class="s">${A.length} awards on robots, autonomy, prosthetics and exoskeletons, haptics and robotic manufacturing</div></div>
      <div class="mm-htile"><div class="k">Active now</div><div class="v">${active.length}</div><div class="s">${fmtUSD(active.reduce((a,x)=>a+x.amount,0))} on awards that have not yet ended</div></div>
      <div class="mm-htile"><div class="k">By agency</div><div class="s">${Object.entries(ag).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${esc(k)} ${fmtUSD(v)}`).join("<br>")}</div></div>
      <div class="mm-htile"><div class="k">By start year</div><div class="mm-hbars">${ys.map(y=>`<i title="${y}: ${fmtUSD(yr[y])}" style="height:${Math.max(2,Math.round(28*yr[y]/ymax))}px"></i>`).join("")}</div><div class="s">${ys[0]||""}–${ys[ys.length-1]||""}; ${Object.entries(tp).sort((a,b)=>b[1]-a[1]).map(([t,n])=>`${esc(t.toLowerCase())} ${n}`).join(", ")}</div></div></div>
    ${sortTable("ndr",[{key:"start",label:"Start",cell:r=>esc(r.start.slice(0,7))},{key:"title",label:"Award",cell:r=>`<a href="${esc(r.url)}" rel="noopener">${esc(r.title)}</a>`},
      {key:"agencyShort",label:"Agency"},{key:"pi",label:"Investigator",cell:r=>esc(r.pi||"–")},{key:"amount",label:"Amount",num:true,cell:r=>fmtUSD(r.amount)},{key:"type",label:"Type"}],
      st.ndrAll?rows:rows.slice().sort((a,b)=>b.start.localeCompare(a.start)).slice(0,8)).replace("<table","<table class=\"mm-ndr\"")}
    ${rows.length>8?`<button type="button" class="mm-chip" data-ndrall="1" style="margin-top:8px">${st.ndrAll?"Show the 8 latest":"Show all "+rows.length+" awards"}</button>`:""}
    <p class="mm-wnote">Federal grants, cooperative agreements and contracts to the University of Notre Dame du Lac since FY2016, and its subawards on other institutions' awards, from USAspending.gov (all agencies), kept when the title, or the description at least three times, is about robots, autonomy, drones, prosthetics or exoskeletons, haptics, legged or humanoid systems, or robotic manufacturing (${esc(String(R.scanned||""))} prime awards scanned). Amounts are obligations so far. Industry, foundation and state funding are not in this data. Pulled ${esc(R.pulled||"")}.</p>`}
/* history sparkline: yearly values ("2021") and monthly snapshots ("2026-11") on one time axis, a dashed line at the U.S. (100),
   a dot per point with its value on hover, and the latest point in its grade color */
function histSpark(pts,w,h){pts=pts.filter(([,v])=>v!=null).map(([k,v])=>[k,+v,k.length===4?+k+0.5:+k.slice(0,4)+(+k.slice(5,7)-0.5)/12]).sort((a,b)=>a[2]-b[2]);
  if(pts.length<2)return "";w=w||96;h=h||24;const p=3,xs=pts.map(x=>x[2]),vs=pts.map(x=>x[1]).concat(100),x0=Math.min(...xs),x1=Math.max(...xs),lo=Math.min(...vs),hi=Math.max(...vs),
    X=t=>p+(t-x0)/((x1-x0)||1)*(w-2*p),Y=v=>h-p-(v-lo)/((hi-lo)||1)*(h-2*p),last=pts[pts.length-1];
  return `<svg class="mm-hsp" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="History: ${esc(pts.map(([k,v])=>k+" "+Math.round(v)).join(", "))}">
    <line class="ref" x1="${p}" x2="${w-p}" y1="${Y(100).toFixed(1)}" y2="${Y(100).toFixed(1)}"/><polyline points="${pts.map(x=>X(x[2]).toFixed(1)+","+Y(x[1]).toFixed(1)).join(" ")}"/>
    ${pts.map(([k,v,t])=>`<circle class="hit" cx="${X(t).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="5"><title>${esc(k)}: ${Math.round(v)} (100 = the benchmark)</title></circle>`).join("")}
    <circle class="end g${grade(last[1])}" cx="${X(last[2]).toFixed(1)}" cy="${Y(last[1]).toFixed(1)}" r="2.6"/></svg>`};
const lab=k=>k.length===4?k:monthName(k);
const span=pts=>{const q=pts.filter(([,v])=>v!=null).slice().sort((a,b)=>a[0].localeCompare(b[0]));if(q.length<2)return "";const f=q[0],l=q[q.length-1];
  return `${esc(lab(f[0]))} <b>${Math.round(f[1])}</b> → ${esc(lab(l[0]))} <b>${Math.round(l[1])}</b>`};
function renderOpportunity(){const el=document.getElementById("opp"),O=DATA.opportunity;if(!el||!O||!O.pillars)return;
  const fmt=(v,u)=>v==null?"–":u==="share"?(100*v).toFixed(1)+"%":u==="pct"?Math.round(v)+"%":u==="%"?v.toFixed(1)+"%":u==="growth"?(v>=0?"+":"−")+(100*Math.abs(v)).toFixed(1)+"%":u==="usd"?"$"+Math.round(v).toLocaleString():String(v);
  const max=Math.max(200,...O.pillars.map(p=>p.score||0)),bar=v=>v==null?`<span class="mm-count">not yet available</span>`:`<span class="mm-ratio"><span class="trk"><span class="fil g${grade(v)}" style="width:${Math.min(100,100*v/max).toFixed(1)}%"></span><span class="one" style="left:${(100*100/max).toFixed(1)}%"></span></span><span class="v">${Math.round(v)}</span>${gbadge(v)}</span>`;
  const prog=Object.entries(HUM.progress||{}).filter(([,v])=>v.index!=null);
  const phist=p=>Object.entries(p.history||{}).concat(prog.filter(([,v])=>v.pillars&&v.pillars[p.id]!=null).map(([m,v])=>[m,v.pillars[p.id]]));
  const xhist=(p,i)=>Object.entries(p.parts[i].history||{}).concat(prog.filter(([,v])=>v.parts&&v.parts[p.id]&&v.parts[p.id][i]!=null).map(([m,v])=>[m,v.parts[p.id][i]]));
  const ihist=prog.map(([m,v])=>[m,v.index]);
  el.innerHTML=`<div class="mm-ohead"><div class="mm-oidx"><div class="k">Humanoid Deployment Benefit Index</div><div class="v">${O.index==null?"–":Math.round(O.index)} ${gbadge(O.index)}</div><div class="s">100 = U.S. level on five pillars · ${ihist.length>1?histSpark(ihist,170,34)+" "+span(ihist):"tracked monthly from "+esc(monthName(Object.keys(HUM.progress||{})[0]||""))+"; the index needs every pillar, so its history starts there"}</div></div>
    <p class="mm-fedsum">Where deploying humanoid robots could benefit the region's manufacturers most: how much local work is the hard, repetitive and hazardous kind a humanoid could take on, and how ready the region is to build and adopt them. Five pillars compare the region with the U.S. (= 100); <b>local supply</b> has no U.S. benchmark and is scored against a fixed target instead (half of a humanoid's cost available locally = 100). The index is their weighted geometric mean: a weak pillar pulls it down, but gains in one pillar can offset losses in another. It does not show that workers gain or keep their jobs: <b>jobs and pay</b> is one pillar, and the index can rise while it falls.</p></div>
    <div class="mm-opills">${O.pillars.map(p=>`<div class="mm-opill"><div class="hd"><b>${esc(p.name)}</b>${bar(p.score)}</div><div class="w">${esc(p.what)}</div>
      ${(()=>{const hp=phist(p);return hp.filter(([,v])=>v!=null).length>1?`<div class="mm-ohist">${histSpark(hp,220,38)}<span class="mm-olab">${span(hp)}</span></div>`:`<div class="mm-ohist"><span class="mm-mut">history starts with monthly tracking</span></div>`})()}
      ${p.parts.map((x,i)=>`<div class="pt"><span>${esc(x.name)}${x.note?` <small class="mm-mut">${esc(x.note)}</small>`:""}</span>${histSpark(xhist(p,i),84,22)}<span class="nums">${fmt(x.local,x.unit)}${x.us!=null?` <small class="mm-mut">vs U.S. ${fmt(x.us,x.unit)}</small>`:""}${x.score!=null?` <b>${Math.round(x.score)}</b> ${gbadge(x.score)}`:""}</span></div>`).join("")}</div>`).join("")}</div>
    <div class="mm-gleg">${GRADES.map(([g,t],i)=>`<span title="${BAND[i]}"><span class="mm-gsw g${g}"></span>${i===0?"150 or more":i===GRADES.length-1?"under 60":t+"–"+(GRADES[i-1][1]-1)}</span>`).join("")}<span class="mm-mut">100 = the U.S. level (local supply: half of the robot available locally) · yellow is about that level; orange and red: areas that need work</span></div>
    ${ndResearch()}
    <p class="mm-wnote">Task fit is scored per occupation on the Occupations tab. Jobs and pay: BLS OEWS May ${esc(String(O.oews_year||""))}, four metro areas. Industry, establishment and growth figures: BLS QCEW ${esc(String(O.qcew_year||""))}; age and turnover: Census Quarterly Workforce Indicators${O.qwi_quarters&&O.qwi_quarters.length?" ("+esc(O.qwi_quarters[O.qwi_quarters.length-1])+" to "+esc(O.qwi_quarters[0])+")":""}; value added: BEA ${esc(String(O.bea_year||""))}. Weights and lists are editable in data/opportunity.toml.</p>`}
function renderOccHelp(){const el=document.getElementById("occ-help"),O=DATA.opportunity;if(!el||!O||!O.occupations)return;
  const rows=(O.occupations||[]).map(r=>({...r,impact:r.fit!=null?r.jobs*r.fit/100:null,role:r.readiness?"deploys automation":"production",traitsText:r.traits.join(", ")}));
  el.innerHTML=`${sortTable("opp",[{key:"name",label:"Occupation",cell:r=>`<b>${esc(r.name)}</b>${r.readiness?' <small class="mm-mut">deploys automation</small>':""}`},
      {key:"jobs",label:"Jobs",num:true,cell:r=>Math.round(r.jobs).toLocaleString()},{key:"per1000",label:"Per 1,000 jobs",num:true,cell:r=>r.per1000==null?"–":r.per1000.toFixed(1)},
      {key:"fit",label:"Task fit",title:"0 to 100, from O*NET task traits",cell:r=>r.fit==null?"–":`<span class="mm-ratio"><span class="trk"><span class="fil" style="width:${r.fit}%"></span></span><span class="v">${Math.round(r.fit)}</span></span>`},
      {key:"impact",label:"Jobs × fit",title:"local jobs weighted by task fit: where humanoids would help the most people",num:true,cell:r=>r.impact==null?"–":Math.round(r.impact).toLocaleString()},
      {key:"traitsText",label:"Work a humanoid could take on",cell:r=>esc(r.traitsText||"–")},
      {key:"median",label:"Median pay",num:true,cell:r=>usd(r.median)},{key:"us_median",label:"U.S. median",num:true,cell:r=>usd(r.us_median)}],rows)}
    <p class="mm-wnote">Task fit scores how much of an occupation's work is handling and moving parts, repetitive motion, awkward postures and hazards (O*NET 31.0, 0 to 100); it marks the tasks a humanoid could relieve people of, not jobs to cut. Jobs and pay: BLS OEWS May ${esc(String(O.oews_year||""))}, four metro areas. "Deploys automation" marks the occupations counted in adoption readiness.</p>`}
/* ---------- region comparison: the same index for similar regions (scripts/compare_regions.py) ---------- */
function renderComparison(){const el=document.getElementById("cmp"),X=DATA.comparison;if(!el)return;
  if(!X||!X.regions){document.getElementById("comparison").hidden=true;return}
  const P=[["task","Task fit"],["highmix","High-mix"],["labor","Labor"],["readiness","Readiness"],["supply","Supply"],["prosperity","Jobs & pay"]];
  const full=Object.fromEntries(((DATA.opportunity||{}).pillars||[]).map(p=>[p.id,p.name]));
  const rank=Object.fromEntries((X.ranking||[]).map((n,i)=>[n,i+1]));
  const rows=Object.entries(X.regions).map(([n,v])=>({name:n,university:v.university,index:v.index,rank:rank[n]??null,home:v.home,cls:v.home?"mm-home":"",...Object.fromEntries(P.map(([k])=>[k,v.pillars[k]]))}));
  const max=Math.max(150,...rows.map(r=>r.index||0));
  const sc=v=>v==null?"–":`${Math.round(v)}${gbadge(v)}`;
  const months=Object.keys(X.history||{}).sort(),I=X.inputs||{};
  document.getElementById("cmpnote").textContent=`${rows.length} regions · 100 = the U.S. level (local supply: a fixed target) · updated ${X.updated||""}`;
  el.innerHTML=`<p class="mm-fedsum">The Humanoid Deployment Benefit Index for metro areas of similar size, each with a well-known research university, computed the same way and from the same public sources as the region's own index above. Michiana is highlighted.</p>
    ${sortTable("cmp",[{key:"rank",label:"#",num:true,cell:r=>r.rank??"–"},
      {key:"name",label:"Region",cell:r=>`<b>${esc(r.name)}</b><br><small class="mm-mut">${esc(r.university||"")}</small>`},
      {key:"index",label:"Index",title:"Humanoid Deployment Benefit Index",cell:r=>r.index==null?"–":`<span class="mm-ratio"><span class="trk"><span class="fil g${grade(r.index)}" style="width:${Math.min(100,100*r.index/max).toFixed(1)}%"></span><span class="one" style="left:${(100*100/max).toFixed(1)}%"></span></span><span class="v">${Math.round(r.index)}</span>${gbadge(r.index)}</span>`},
      ...P.map(([k,l])=>({key:k,label:l,title:full[k]||l,num:true,cell:r=>sc(r[k])}))],rows)}
    <p class="mm-wnote">Each region is a set of counties (jobs, establishments, pay, unemployment, workforce age and turnover, value added) and the BLS metro areas that cover them (occupations). Sources: BLS QCEW ${esc(String(I.qcew_year||""))}, OEWS May ${esc(String(I.oews_year||""))}, LAUS (latest month), Census QWI, BEA ${esc(String(I.value_added_year||""))}. Michigan has published no Census workforce quarters since 2023, so Ann Arbor and Lansing score labor pressure on unemployment alone, and Michiana's Michigan counties are left out of its age and turnover figures. Local supply counts build-to-print parts with two or more establishments in their industries, so it tops out at 38 for every region. Recomputed every month${months.length?" since "+esc(monthName(months[0])):""}; the regions are listed in data/regions.toml.</p>`}
/* ---------- humanoid coverage: which parts of a humanoid local companies could supply ---------- */
const TIERS=["no supplier","one supplier","2–4 suppliers","5 or more"],tierOf=n=>n===0?0:n===1?1:n<5?2:3;
function humStats(){const comp={};for(const k of Object.keys(HCOMP))comp[k]={all:new Map(),conf:new Map()};
  for(const c of C)if(c.mfg)for(const k of c.hum){const g=groupOf(c),e=comp[k];if(!e)continue;if(!e.all.has(g.id))e.all.set(g.id,{g,c});if(c.hum_ev==="confirmed"&&!e.conf.has(g.id))e.conf.set(g.id,{g,c})}
  for(const [k,e] of Object.entries(comp)){e.n=e.all.size;e.nc=e.conf.size;e.na=HCOMP[k].build_to_print?e.n:e.nc;e.top=[...e.all.values()].sort((a,b)=>(empSum(b.g.sites)||0)-(empSum(a.g.sites)||0)).slice(0,3)}
  return comp}
/* the figure: one path per body segment, left side drawn and right side mirrored */
const humSvg=()=>{const mir=d=>d.replace(/(-?[\d.]+),(-?[\d.]+)/g,(m,x,y)=>(260-x)+","+y),
    P=(g,d,label)=>`<path data-hum="g:${g}" data-hg="${g}" d="${d}" aria-label="${esc(label)}"/>`,P2=(g,d,label)=>P(g,d,label)+P(g,mir(d),label),
    J=(x,y,r)=>`<circle data-hum="g:actuators" data-hg="actuators" class="jt" cx="${x}" cy="${y}" r="${r}"/>`,J2=(x,y,r)=>J(x,y,r)+J(260-x,y,r);
  return `<svg class="mm-hfig" viewBox="0 0 260 486" role="img" aria-label="Humanoid robot, each region shaded by how many local companies could supply its parts">
  <defs><pattern id="hhatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" class="hh"/></pattern></defs>
  <rect data-hum="g:integration" data-hg="integration" class="plate" x="56" y="470" width="148" height="10" rx="3" aria-label="Integration and test: the whole robot"/>
  ${P("perception","M130,8 C151,8 161,22 161,40 L161,53 C161,64 151,73 139,75 L121,75 C109,73 99,64 99,53 L99,40 C99,22 109,8 130,8 Z","Head: perception")}
  ${P2("perception","M99,33 L95,34 C92,35 91,38 91,41 L91,49 C91,52 92,54 95,55 L99,56 Z","Head: perception, side sensor")}
  ${P("structure","M122,75 L138,75 L141,91 L119,91 Z","Neck: structure")}
  ${P("compute","M88,96 C100,92 113,90 121,90 L139,90 C147,90 160,92 172,96 C178,98 180,104 178,111 L172,150 C170,166 160,176 148,178 L112,178 C100,176 90,166 88,150 L82,111 C80,104 82,98 88,96 Z","Chest: compute and electronics")}
  ${P("power","M98,182 L162,182 C166,182 168,184 167,188 L164,222 C164,225 162,226 159,226 L101,226 C98,226 96,225 96,222 L93,188 C92,184 94,182 98,182 Z","Abdomen: power")}
  ${P("structure","M96,232 L164,232 C168,232 170,235 169,239 L160,264 C159,267 156,268 153,268 L107,268 C104,268 101,267 100,264 L91,239 C90,235 92,232 96,232 Z","Pelvis: structure")}
  ${P2("structure","M51,106 C51,96 77,96 77,106 C79,130 76,150 73,172 C72,178 57,178 56,172 C53,150 49,130 51,106 Z","Upper arm: structure")}
  ${P2("structure","M53,192 C53,185 75,185 75,192 C76,215 72,240 70,256 C69,260 59,260 58,256 C56,240 52,215 53,192 Z","Forearm: structure")}
  ${P2("hands","M54,268 L74,268 C77,268 78,270 78,273 L78,280 C82,281 85,284 84,289 C83,292 80,292 78,291 L77,294 L76,302 C76,305 71,305 71,302 L70,296 L69,305 C69,308 64,308 64,305 L63,297 L62,306 C62,309 57,309 57,306 L56,297 L55,303 C55,306 50,306 50,303 L51,292 L52,273 C52,270 53,268 54,268 Z","Hand")}
  ${P2("structure","M95,285 C95,276 125,276 125,285 C126,310 123,340 121,358 C120,364 100,364 99,358 C96,340 93,310 95,285 Z","Thigh: structure")}
  ${P2("structure","M98,377 C98,370 122,370 122,377 C123,400 120,425 118,442 C117,446 103,446 102,442 C98,425 95,400 98,377 Z","Shin: structure")}
  ${P2("hands","M98,454 L122,454 C126,455 128,458 129,462 L130,466 L88,466 L89,462 C90,458 94,455 98,454 Z","Foot: force sensing")}
  <path class="visor" d="M105,31 C117,27 143,27 155,31 L155,42 C143,46 117,46 105,42 Z" pointer-events="none"/>
  ${J2(64,99,13)}${J2(64,182,9)}${J2(64,263,7)}${J(130,84,7)}${J(130,229,9)}${J2(110,272,11)}${J2(110,366,10)}${J2(110,448,8)}
  </svg>`};
function renderHumanoid(){const el=document.getElementById("hum");if(!el||!HUM.components.length)return;
  const S=humStats(),conf=st.hb==="available",n=k=>conf?S[k].na:S[k].n;
  document.querySelectorAll("[data-hb]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.hb===st.hb)));
  /* a group's shade: the cost-weighted tier of its components */
  const gt={};for(const g of HUM.groups){const cs=HUM.components.filter(c=>c.group===g.id),w=cs.reduce((a,c)=>a+c.cost,0);gt[g.id]=Math.round(cs.reduce((a,c)=>a+c.cost*tierOf(n(c.id)),0)/(w||1))}
  const share=(f,key)=>HUM.components.filter(c=>f(key==="avail"?S[c.id].na:S[c.id].n)).reduce((a,c)=>a+c.cost,0);
  const gaps=HUM.components.filter(c=>!S[c.id].n),sup=new Set(C.filter(c=>c.mfg&&c.hum.length).map(c=>groupOf(c).id)),supc=new Set(C.filter(c=>c.mfg&&c.hum.length&&c.hum_ev==="confirmed").map(c=>groupOf(c).id));
  const fy=Object.entries(HUM.funding||{}).filter(([y])=>+y>=2016),ftot=fy.reduce((a,[,v])=>a+v.amount,0),fmax=Math.max(1,...fy.map(([,v])=>v.amount));
  const prog=Object.entries(HUM.progress||{}),p0=prog[0];
  const tiles=`<div class="mm-htiles">
    <div class="mm-htile"><div class="k">Related local capability</div><div class="v">${share(x=>x>=2,"all")}%</div><div class="s">of the cost has two or more local companies in a related line of work; ${share(x=>x===1,"all")}% has one${gaps.length?`; gap: ${esc(gaps.map(c=>c.name.split(" (")[0].toLowerCase()).join(", "))}`:""}</div></div>
    <div class="mm-htile"><div class="k">Available now</div><div class="v">${share(x=>x>=2,"avail")}%</div><div class="s">of the cost has two or more local suppliers today: contract shops for build-to-print parts, confirmed makers for the rest</div></div>
    <div class="mm-htile"><div class="k">Manufacturers</div><div class="v">${sup.size}</div><div class="s">with a related capability; ${supc.size} confirmed for a humanoid part</div></div>
    <div class="mm-htile"><div class="k">Robotics-related awards since 2016</div><div class="v">${fmtUSD(ftot)}</div><div class="mm-hbars">${fy.map(([y,v])=>`<i title="${y}: ${fmtUSD(v.amount)}, ${v.n} award${v.n===1?"":"s"}" style="height:${Math.max(2,Math.round(28*v.amount/fmax))}px"></i>`).join("")}</div><div class="s">federal awards of $250k+ and SBIR/STTR awards mentioning robots, actuators or sensors${fy.length?`, ${fy[0][0]}–${fy[fy.length-1][0]}`:""}</div></div>
    <div class="mm-htile"><div class="k">Tracking since</div><div class="v">${p0?esc(monthName(p0[0])):"–"}</div><div class="s">${prog.length>1?prog.map(([m,v])=>`${esc(monthName(m))}: ${v.available_two_plus??v.confirmed_two_plus}% available, ${v.two_plus}% related`).slice(-3).join("<br>"):"a snapshot is saved every month; the trend appears from the second month"}</div></div></div>`;
  const glist=HUM.groups.map(g=>{const cs=HUM.components.filter(c=>c.group===g.id),gp=cs.filter(c=>!n(c.id)).length,w=cs.reduce((a,c)=>a+c.cost,0);
    return `<button type="button" class="mm-hg${st.hum==="g:"+g.id?" on":""}" data-hum="g:${g.id}" data-hg="${g.id}"><i class="sw t${gt[g.id]}"></i><span><b>${esc(g.name)}</b><small>${esc(g.region)} · ${w}% of cost · ${esc(TIERS[gt[g.id]])}${gp?` · ${gp} gap${gp>1?"s":""}`:""}</small></span></button>`}).join("");
  const rows=HUM.components.map(c=>({id:c.id,name:c.name,btp:!!c.build_to_print,group:HGROUP[c.group].name,cost:c.cost,n:S[c.id].n,nc:S[c.id].na,tier:tierOf(n(c.id)),top:S[c.id].top,toplabel:S[c.id].top.map(t=>t.g.name).join(", ")}));
  el.innerHTML=`${tiles}<div class="mm-hmain"><div class="mm-hfigwrap">${humSvg()}<div class="mm-hleg">${TIERS.map((t,i)=>`<span><i class="sw t${i}"></i>${t}</span>`).join("")}</div></div>
    <div class="mm-hside"><p class="mm-wnote" style="margin-top:0">Each region is shaded by the cost-weighted depth of local supply for its parts${conf?", counting contract shops for build-to-print parts and only confirmed makers for the rest":", counting every company in a related line of work"}. Click a region or a group to show its companies on the map and in the roster.</p>${glist}</div></div>
    ${st.hum?`<p class="mm-hfilter">Map and roster show companies for <b>${esc(st.hum[0]==="g"?HGROUP[st.hum.slice(2)].name:HCOMP[st.hum.slice(2)].name)}</b>. <button type="button" class="mm-chip" data-tab="companies" data-map="1">Show on the map</button> <button type="button" class="mm-chip" data-hum="${esc(st.hum)}">Show all companies</button></p>`:""}
    ${sortTable("hum",[{key:"name",label:"Component",cell:r=>`<button type="button" class="mm-hk${st.hum==="k:"+r.id?" on":""}" data-hum="k:${r.id}">${esc(r.name)}</button>${r.btp?' <small class="mm-mut" title="any capable contract shop counts as available">build to print</small>':""}`},{key:"group",label:"Group"},
      {key:"cost",label:"Share of cost",num:true,cell:r=>r.cost+"%"},{key:"n",label:"Related",title:"local companies with a related capability",num:true,cell:r=>String(r.n)},
      {key:"nc",label:"Available",title:"contract shops for build-to-print parts, confirmed makers for the rest",num:true,cell:r=>String(r.nc)},{key:"tier",label:"Depth",cell:r=>`<span class="mm-ht"><i class="sw t${r.tier}"></i>${esc(TIERS[r.tier])}</span>`},
      {key:"toplabel",label:"Largest related companies",cell:r=>r.top.map(t=>`<button type="button" class="mm-link" data-sel="${t.c.id}">${esc(t.g.sites.length>1?t.g.name:t.c.name)}</button>`).join(", ")||"–"}],rows)}
    <p class="mm-wnote">Costs are rough shares of a humanoid's bill of materials from public teardown estimates, editable in data/humanoid.toml with the matching rules. "Related" is inferred from industry codes and product descriptions: a company that rebuilds industrial motors counts toward motors, though it may not make humanoid joint motors. Parts marked "build to print" are made to the robot maker's drawings, so any capable local contract shop counts as available; other parts count as available only once a company confirms it makes them (humanoid_evidence = "confirmed" in its file).</p>`;
  const fig=el.querySelector(".mm-hfig");fig.querySelectorAll("[data-hg]").forEach(r=>{const g=r.dataset.hg;r.setAttribute("class",(r.getAttribute("class")||"")+" t"+gt[g]+(st.hum==="g:"+g?" on":""))});
  const tip=document.getElementById("htip");
  fig.addEventListener("pointermove",e=>{const r=e.target.closest("[data-hg]");if(!r){tip.style.opacity=0;return}const g=r.dataset.hg,cs=HUM.components.filter(c=>c.group===g);
    tip.innerHTML=`<b>${esc(HGROUP[g].name)}</b>${esc(HGROUP[g].region)}`+cs.map(c=>`<div class="m">${esc(c.name)}: ${S[c.id].n} related, ${S[c.id].na} available${c.build_to_print?" (build to print)":""}</div>`).join("")+`<div class="m">click to show them on the map</div>`;
    const b=el.getBoundingClientRect();tip.style.left=(e.clientX-b.left)+"px";tip.style.top=(e.clientY-b.top)+"px";tip.style.opacity=1});
  fig.addEventListener("pointerleave",()=>{tip.style.opacity=0})}
/* ---------- workforce: BLS specialization, occupations and the latest month ---------- */
const MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],monthName=ym=>{const [y,m]=ym.split("-");return MONTHS[+m-1]+" "+y};
const usd=v=>v==null?"–":"$"+Math.round(v).toLocaleString();
/* a sortable table: cols {key,label,title,num,cell(row)}; header buttons use the shared [data-sort] handler */
function sortTable(kind,cols,rows){const s=st.sort[kind];rows=rows.slice().sort((a,b)=>{const va=a[s.key],vb=b[s.key];if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;return (typeof va==="string"?va.localeCompare(vb):va-vb)*s.dir});
  return `<div class="mm-tblwrap"><table><thead><tr>${cols.map(c=>`<th${c.num?' class="num"':""}><button type="button" data-kind="${kind}" data-sort="${c.key}" aria-pressed="${s.key===c.key}" title="Sort by ${esc(c.title||c.label)}">${esc(c.label)}${s.key===c.key?ARROW(s.dir):""}</button></th>`).join("")}</tr></thead>
  <tbody>${rows.map(r=>`<tr class="${r.cls||""}">${cols.map(c=>`<td class="${c.num?"num":""} ${c.cls||""}">${c.cell?c.cell(r):esc(r[c.key]??"–")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`}
/* a ratio against the U.S. (1 = same as the U.S.) as a bar with a tick at 1 */
const ratioBar=(v,max)=>v==null?"–":`<span class="mm-ratio" title="${v.toFixed(2)} times the U.S. level"><span class="trk"><span class="fil" style="width:${Math.min(100,100*v/max).toFixed(1)}%"></span><span class="one" style="left:${(100/max).toFixed(1)}%"></span></span><span class="v">${v<10?v.toFixed(1):Math.round(v)}×</span></span>`;
function renderWork(){const el=document.getElementById("work"),note=document.getElementById("worknote");if(!el)return;
  document.querySelectorAll("[data-wv]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.wv===st.wv)));
  const B=DATA.bls||{},S=DATA.qcewSpec||{};
  if(st.wv==="spec"){if(!S.industries){el.innerHTML=`<p class="mm-count">No specialization data yet.</p>`;return}const t=S.total,max=Math.max(...S.industries.map(r=>r.lq||0));
    note.textContent=`BLS QCEW, private, ${S.year} annual averages`;
    el.innerHTML=`<p class="mm-fedsum">In ${S.year} manufacturing held <b>${(100*t.share).toFixed(0)}%</b> of the region's private jobs, <b>${t.lq.toFixed(1)}×</b> the U.S. share of ${(100*t.us_share).toFixed(0)}%. Average manufacturing pay was <b>${usd(t.pay)}</b>, against ${usd(t.us_pay)} nationally.</p>`
      +sortTable("spec",[{key:"name",label:"Industry",title:"industry (3-digit NAICS)",cell:r=>`<b>${esc(r.name)}</b> <small class="mm-mut">${r.naics}</small>`},
        {key:"lq",label:"Specialization",title:"location quotient: regional share of private jobs over the U.S. share",cell:r=>ratioBar(r.lq,max)},
        {key:"emp",label:"Jobs",num:true,cell:r=>(r.withheld?'<span class="q" title="lower bound: BLS withholds some county figures">≥</span>':"")+r.emp.toLocaleString()},
        {key:"estab",label:"Sites",title:"establishments",num:true,cell:r=>r.estab.toLocaleString()},
        {key:"pay",label:"Avg pay",title:"average annual pay in the region",num:true,cell:r=>usd(r.pay)},
        {key:"us_pay",label:"U.S. pay",title:"average annual pay in the U.S.",num:true,cell:r=>usd(r.us_pay)},
        {key:"top_lq",label:"Most concentrated in",title:"county with the highest BLS location quotient",cell:r=>r.top_county?`${esc(r.top_county)} <small class="mm-mut">${r.top_lq}×</small>`:"–"}],S.industries)
      +`<p class="mm-wnote">Specialization is the industry's share of the region's private jobs divided by its share nationally; 1× (the tick) matches the U.S. Region-wide figures add the counties; BLS withholds cells that would reveal one employer, so marked job counts are lower bounds.</p>`;return}
  if(st.wv==="occ"){const O=B.occupations;if(!O){el.innerHTML=`<p class="mm-count">No occupation data yet.</p>`;return}
    const all=O.list.find(o=>o.code==="000000"),regAll=Object.values(all.metros).reduce((a,m)=>a+(m.emp||0),0),usAll=all.us.emp;
    const rows=O.list.filter(o=>o.code!=="000000"&&Object.keys(o.metros).length).map(o=>{const ms=Object.entries(o.metros),emp=ms.reduce((a,[,m])=>a+(m.emp||0),0),wm=ms.filter(([,m])=>m.emp&&m.median);
      const med=wm.length?wm.reduce((a,[,m])=>a+m.emp*m.median,0)/wm.reduce((a,[,m])=>a+m.emp,0):null,per=1000*emp/regAll,usPer=o.us.emp?1000*o.us.emp/usAll:null;
      const top=ms.filter(([,m])=>m.emp).sort((a,b)=>b[1].emp-a[1].emp)[0];
      return {name:o.name,emp,per,ratio:usPer?per/usPer:null,med,us:o.us.median,cls:/\(all\)$/.test(o.name)?"agg":"",top:top?O.metros[top[0]]:"",
        detail:ms.map(([k,m])=>`${O.metros[k]}: ${m.emp!=null?m.emp.toLocaleString():"not published"}`).join(" · ")}});
    const max=Math.max(...rows.map(r=>r.ratio||0));
    note.textContent=`BLS OEWS, May ${O.year}, four metro areas`;
    el.innerHTML=`<p class="mm-fedsum">Jobs and median pay in the South Bend–Mishawaka, Elkhart–Goshen, Niles and Michigan City–La Porte metro areas, <b>${regAll.toLocaleString()}</b> jobs in all.</p>`
      +sortTable("occ",[{key:"name",label:"Occupation",cell:r=>`<b title="${esc(r.detail)}">${esc(r.name)}</b>`},
        {key:"emp",label:"Jobs",num:true,cell:r=>`<span title="${esc(r.detail)}">${r.emp.toLocaleString()}</span>`},
        {key:"per",label:"Per 1,000 jobs",num:true,cell:r=>r.per.toFixed(1)},
        {key:"ratio",label:"vs U.S.",title:"jobs per 1,000 compared with the U.S.",cell:r=>ratioBar(r.ratio,max)},
        {key:"med",label:"Median pay",title:"annual median, weighted across the metros",num:true,cell:r=>usd(r.med)},
        {key:"us",label:"U.S. median",num:true,cell:r=>usd(r.us)},
        {key:"top",label:"Largest in"}],rows)
      +`<p class="mm-wnote">Hover a job count for each metro. Small metros' estimates that BLS cannot publish reliably are left out, so totals are lower bounds. Kosciusko, Starke and other counties outside these metros are not included.</p>`;return}
  /* latest month: manufacturing jobs per metro (small multiples) and unemployment by county */
  const ces=Object.values(B.ces||{}).filter(m=>m.months.length).sort((a,b)=>b.months[b.months.length-1][1]-a.months[a.months.length-1][1]),L=B.laus;if(!ces.length||!L){el.innerHTML=`<p class="mm-count">No monthly data yet.</p>`;return}
  const last=ces[0].months[ces[0].months.length-1][0];note.textContent=`BLS CES and LAUS, through ${monthName(last)}, not seasonally adjusted`;
  const spark=(m,i)=>{const pts=m.months.filter(p=>p[1]!=null),v=pts.map(p=>p[1]),lo=Math.min(...v),hi=Math.max(...v),W=260,H=74,pad=4,X=j=>pad+j*(W-2*pad)/(pts.length-1),Y=x=>H-pad-(x-lo)/((hi-lo)||1)*(H-2*pad);
    const lp=pts[pts.length-1],yr=pts.find(p=>p[0]===(+lp[0].slice(0,4)-1)+lp[0].slice(4)),ch=yr?lp[1]-yr[1]:null;
    return `<div class="mm-spark" data-spark="${i}"><div class="hd"><b>${esc(m.name)}</b><span class="rd" data-def="${esc(monthName(lp[0]))}: ${(lp[1]*1000).toLocaleString()} jobs">${esc(monthName(lp[0]))}: ${(lp[1]*1000).toLocaleString()} jobs</span></div>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(m.name)} manufacturing jobs by month, ${esc(monthName(pts[0][0]))} to ${esc(monthName(lp[0]))}"><line class="gr" x1="0" x2="${W}" y1="${H-pad}" y2="${H-pad}"/><polyline class="ln" points="${pts.map((p,j)=>X(j).toFixed(1)+","+Y(p[1]).toFixed(1)).join(" ")}"/><line class="xh" x1="0" x2="0" y1="0" y2="${H}" style="opacity:0"/><circle class="pt" r="4" cx="${X(pts.length-1)}" cy="${Y(lp[1])}"/></svg>
      <div class="ft">${ch==null?"":`${ch>=0?"+":"−"}${Math.abs(Math.round(ch*1000)).toLocaleString()} jobs on a year earlier`} · range ${(lo*1000/1000).toFixed(1)}k–${hi.toFixed(1)}k</div></div>`};
  const usR=L.us_rate||[],usLast=usR[usR.length-1];
  const rows=Object.values(L.counties).filter(c=>c.rate&&c.rate.length).map(c=>{const r=c.rate.filter(p=>p[1]!=null),lp=r[r.length-1],yr=r.find(p=>p[0]===(+lp[0].slice(0,4)-1)+lp[0].slice(4)),f=(c.force||[]).filter(p=>p[1]!=null);
    return {name:c.name,rate:lp[1],ago:yr?yr[1]:null,chg:yr?lp[1]-yr[1]:null,force:f.length?f[f.length-1][1]:null,month:lp[0]}});
  el.innerHTML=`<div class="mm-wcols"><div><h3 class="mm-wh">Manufacturing jobs by metro area</h3><div class="mm-sparks">${ces.map(spark).join("")}</div></div>
    <div><h3 class="mm-wh">Unemployment by county, ${esc(monthName(rows[0]?rows[0].month:last))}${usLast?` · U.S. ${usLast[1].toFixed(1)}% (${esc(monthName(usLast[0]))})`:""}</h3>
    ${sortTable("ue",[{key:"name",label:"County"},{key:"rate",label:"Rate",num:true,cell:r=>r.rate.toFixed(1)+"%"},{key:"ago",label:"Year earlier",num:true,cell:r=>r.ago==null?"–":r.ago.toFixed(1)+"%"},
      {key:"chg",label:"Change",num:true,cell:r=>r.chg==null?"–":(r.chg>0?"+":r.chg<0?"−":"±")+Math.abs(r.chg).toFixed(1)},{key:"force",label:"Labor force",num:true,cell:r=>r.force==null?"–":Math.round(r.force).toLocaleString()}],rows)}</div></div>
    <p class="mm-wnote">Preliminary for the latest month. Metro jobs are payroll jobs at establishments in each metro area; county rates count residents.</p>`;
  el.querySelectorAll("[data-spark]").forEach(card=>{const m=ces[+card.dataset.spark],pts=m.months.filter(p=>p[1]!=null),svg=card.querySelector("svg"),xh=card.querySelector(".xh"),pt=card.querySelector(".pt"),rd=card.querySelector(".rd");
    const W=260,H=74,pad=4,v=pts.map(p=>p[1]),lo=Math.min(...v),hi=Math.max(...v),X=j=>pad+j*(W-2*pad)/(pts.length-1),Y=x=>H-pad-(x-lo)/((hi-lo)||1)*(H-2*pad);
    const at=j=>{xh.setAttribute("x1",X(j));xh.setAttribute("x2",X(j));xh.style.opacity=1;pt.setAttribute("cx",X(j));pt.setAttribute("cy",Y(pts[j][1]));rd.textContent=`${monthName(pts[j][0])}: ${Math.round(pts[j][1]*1000).toLocaleString()} jobs`};
    svg.addEventListener("pointermove",e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W;at(Math.max(0,Math.min(pts.length-1,Math.round((x-pad)/((W-2*pad)/(pts.length-1))))))});
    svg.addEventListener("pointerleave",()=>{xh.style.opacity=0;pt.setAttribute("cx",X(pts.length-1));pt.setAttribute("cy",Y(pts[pts.length-1][1]));rd.textContent=rd.dataset.def})})}
const EVKINDS=[["all","All"],["federal","Federal awards"],["sbir","SBIR/STTR"],["patent","Patents"],["research","Notre Dame research"],["milestone","Milestones"],["warn","Layoff & closing notices"]];
function renderEvents(){const vis=new Set(C.filter(visible).map(c=>c.id));let evs=DATA.events.filter(e=>!e.company||vis.has(e.company));
  const kinds=EVKINDS.filter(([k])=>k==="all"||DATA.events.some(e=>e.kind===k)),counts=Object.fromEntries(kinds.map(([k])=>[k,k==="all"?evs.length:evs.filter(e=>e.kind===k).length]));
  if(st.evKind!=="all")evs=evs.filter(e=>e.kind===st.evKind);
  const years={};for(const e of evs){const y=+String(e.date).slice(0,4);if(y)years[y]=(years[y]||0)+1}const ys=Object.keys(years).map(Number).sort(),ymax=Math.max(1,...Object.values(years));
  if(st.evYear)evs=evs.filter(e=>+String(e.date).slice(0,4)===st.evYear);
  const s=st.sort.ev;evs=evs.slice().sort((a,b)=>(s.key==="amount"?((a.amount||0)-(b.amount||0)):String(a.date).localeCompare(String(b.date)))*s.dir);
  document.getElementById("evcount").textContent=`${evs.length} events for the companies shown`;
  document.getElementById("evkinds").innerHTML=kinds.map(([k,l])=>`<button type="button" class="mm-chip" data-evkind="${k}" aria-pressed="${st.evKind===k}">${l} <span class="mm-count">${counts[k]}</span></button>`).join("");
  document.getElementById("evyears").innerHTML=ys.map(y=>`<button type="button" data-evyear="${y}" aria-pressed="${st.evYear===y}" title="${years[y]} events in ${y}"><i style="height:${Math.max(2,Math.round(34*years[y]/ymax))}px"></i><span>${String(y).slice(2)}</span></button>`).join("");
  const shown=evs.slice(0,60+st.evMore);
  document.getElementById("events").innerHTML=HH("ev",[{key:"date",label:"date"},{key:"amount",label:"$",title:"amount"}])
    +(shown.map(e=>{const c=e.company?byId[e.company]:null;return `<div class="mm-ev" data-id="${esc(e.company||"")}"><span class="d">${esc(String(e.date))}</span><span class="t">${c?`<span class="c">${esc(c.name)}</span> · `:""}${esc(e.title)}<span class="k">${esc(e.kind)}</span>${e.source?` <a href="${esc(e.source)}" rel="noopener">source</a>`:""}</span><span class="a">${e.amount?fmtUSD(e.amount):""}</span></div>`}).join("")||`<p class="mm-count">No events for this selection.</p>`)
    +(evs.length>shown.length?`<button type="button" class="mm-chip mm-more" id="evmore">Show ${Math.min(60,evs.length-shown.length)} more of ${evs.length}</button>`:"")}
function renderDetail(){const d=document.getElementById("detail"),c=st.sel&&byId[st.sel];
  if(!c){d.innerHTML=`<p class="mm-empty">Select a company on the map or in the roster, or find one by name above the map.</p>`;return}
  const g=groupOf(c),sib=g.sites.filter(s=>s!==c).sort((a,b)=>(b.emp||0)-(a.emp||0));const site=u=>u?esc(u.replace(/^https?:\/\/(www\.)?/,"").replace(/\/$/,"")):"";
  d.innerHTML=`<h3><span class="mm-dot" style="background:${SCOL[c.sector]};color:${SCOL[c.sector]}"></span>${esc(c.name)}</h3>${c.formerly?`<p class="mm-note">formerly ${esc(c.formerly)}</p>`:""}${c.status?`<p class="mm-note">${esc(c.status)}</p>`:""}
  ${g.sites.length>1?`<div class="mm-grp"><div class="k">Part of ${esc(g.name)}: ${g.sites.length} sites, ${fmtK(empSum(g.sites))} staff known</div>${sib.slice(0,12).map(s=>`<button type="button" class="mm-sib" data-sel="${s.id}">${esc(s.city)}${s.emp?" · "+fmtK(s.emp):""}<span>${esc(s.name.replace(g.name,"").replace(/^[,\s]+/,"")||s.addr||"site")}</span></button>`).join("")}${sib.length>12?`<span class="mm-count">and ${sib.length-12} more</span>`:""}</div>`:""}
  <div><div class="k">What they do</div>${esc(c.blurb)||"–"}<div class="k">Products &amp; services</div>${esc(c.tags.join(", "))}${c.naics?`<div class="k">NAICS</div>${esc(c.naics)}`:""}${c.caps.length?`<div class="k">Capabilities</div>${esc(c.caps.join(", "))}`:""}${c.hum.length?`<div class="k">Humanoid parts (${c.hum_ev==="confirmed"?"confirmed":c.hum_ev==="self-reported"?"self-reported":"inferred"})</div>${esc(c.hum.map(k=>HCOMP[k]?HCOMP[k].name.split(" (")[0]:k).join(", "))}${c.hum_note?`<div class="mm-note">${esc(c.hum_note)}</div>`:""}`:""}</div>
  <div><div class="k">Employees</div>${esc(fmtEmp(c))}${c.emp_note?`<div class="mm-note">${esc(c.emp_note)}</div>`:""}<div class="k">Location</div>${esc(c.addr||c.city+", "+c.state)}${c.prec==="city"?" (placed at the city center)":""}
  ${c.website?`<div class="k">Website</div><a href="${esc(c.website)}" rel="noopener">${site(c.website)}</a>`:""}${c.uei?`<div class="k">UEI</div>${esc(c.uei)}`:""}</div>
  <div>${c.federal?`<div class="k">Federal awards since FY2016</div>contracts ${fmtUSD(c.federal.contracts)} · grants ${fmtUSD(c.federal.grants)} (USAspending)`:""}${c.sbir?`<div class="k">SBIR/STTR</div>${c.sbir.count} awards, ${fmtUSD(c.sbir.amount)} (${esc(c.sbir.agencies.join(", "))})`:""}
  ${c.patents?`<div class="k">Patents since 2015</div>${c.patents.count}${c.patents.latest.length?": "+c.patents.latest.slice(0,3).map(p=>esc(p.title)).join("; "):""}`:""}
  ${(c.occupant?`<div class="k">Also at this address</div>${esc(c.occupant)}<div class="mm-note">Another name filed with OSHA here: a successor, a renamed company or a new tenant. Not yet reviewed.</div>`:"")+(c.warn?`<div class="k">WARN notices</div>${c.warn.map(w=>esc(`${w.type[0].toUpperCase()+w.type.slice(1)}, notice ${w.date}${w.effective?", effective "+w.effective:""}${w.workers?", "+w.workers+" workers":""}`)).join("<br>")}`:"")+(c.fda?`<div class="k">FDA device establishment</div>${esc([...c.fda.types,...c.fda.devices].join(", ")||"registered")}`:"")}${c.certs.filter(x=>!/^FDA/.test(x)).length?`<div class="k">Certifications</div>${esc(c.certs.filter(x=>!/^FDA/.test(x)).join(", "))}`:""}</div>
  <div><div class="k">Source</div>${esc(c.source)}${c.updated?" · as of "+esc(c.updated):""}</div>`}

/* ---------- roster: multi-site companies collapse under their name ---------- */
function empCell(list){const n=empSum(list),k=list.filter(c=>c.emp);if(!n)return "–";if(list.length>1)return fmtK(n);const c=list[0];
  return `${c.emp_quality==="estimate"?'<span class="q" title="estimate">~</span>':""}${c.emp.toLocaleString()}${c.emp_scope==="company"?'<span class="q" title="company-wide">*</span>':""}${c.emp_year?`<span class="yr" title="year of the figure">${shortYear(c.emp_year)}</span>`:""}`}
function renderTable(){const tb=document.querySelector("#table tbody"),rs=st.sort.roster,vis=C.filter(visible);
  const groups={};for(const c of vis)(groups[c.group]=groups[c.group]||[]).push(c);
  const rows=Object.entries(groups).map(([gid,list])=>({gid,list,name:list.length>1?GROUPS[gid].name:list[0].name,sector:list[0].sector,emp:empSum(list),fed:list.reduce((a,c)=>a+(c.federal?c.federal.total:0),0)}));
  rows.sort((a,b)=>{const va=a[rs.key],vb=b[rs.key];const r=typeof va==="string"?va.localeCompare(vb):va-vb;return r*rs.dir||b.emp-a.emp||a.name.localeCompare(b.name)});
  document.querySelectorAll("[data-rsort]").forEach(b=>{b.setAttribute("aria-pressed",String(b.dataset.rsort===rs.key));b.textContent=b.textContent.replace(/ [▾▴]$/,"")+(b.dataset.rsort===rs.key?ARROW(rs.dir):"")});
  const web=u=>u?`<a href="${esc(u)}" rel="noopener">${esc(u.replace(/^https?:\/\/(www\.)?/,"").replace(/\/$/,""))}</a>`:"–";
  const siteRow=(c,child)=>`<tr id="row-${c.id}" class="${st.sel===c.id?"sel":""}${child?" child":""}" data-id="${c.id}"><td class="name">${esc(c.name)}<small>${esc(c.city)}, ${esc(c.state)}</small></td><td><span class="mm-dot" style="background:${SCOL[c.sector]};color:${SCOL[c.sector]}"></span>${esc(c.sector)}</td><td class="num">${empCell([c])}</td><td class="tags">${esc(c.tags.join(", "))}</td><td class="num">${c.federal?fmtUSD(c.federal.total):"–"}${c.fda?'<span class="mm-badge fda">FDA</span>':""}${c.sbir?'<span class="mm-badge fed">SBIR</span>':""}</td><td>${web(c.website)}</td></tr>`;
  const pages=Math.max(1,Math.ceil(rows.length/st.rlim));st.rpage=Math.min(st.rpage,pages-1);const first=st.rlim===Infinity?0:st.rpage*st.rlim;
  let html="";for(const r of rows.slice(first,first+st.rlim)){
    if(r.list.length===1){html+=siteRow(r.list[0],false);continue}
    const open=st.open.has(r.gid),cities=[...new Set(r.list.map(c=>c.city))];
    html+=`<tr class="grp${r.list.some(c=>c.id===st.sel)?" sel":""}" data-group="${esc(r.gid)}"><td class="name"><button type="button" class="mm-caret" aria-expanded="${open}" aria-label="${open?"Collapse":"Expand"} ${esc(r.name)}">${open?"▾":"▸"}</button>${esc(r.name)}<small>${r.list.length} sites · ${esc(cities.slice(0,3).join(", "))}${cities.length>3?" …":""}</small></td><td><span class="mm-dot" style="background:${SCOL[r.sector]};color:${SCOL[r.sector]}"></span>${esc(r.sector)}</td><td class="num">${empCell(r.list)}</td><td class="tags">${esc([...new Set(r.list.flatMap(c=>c.tags))].slice(0,4).join(", "))}</td><td class="num">${r.fed?fmtUSD(r.fed):"–"}</td><td>${web(r.list.find(c=>c.website)?.website)}</td></tr>`;
    if(open)for(const c of r.list.slice().sort((a,b)=>(b.emp||0)-(a.emp||0)))html+=siteRow(c,true)}
  const last=Math.min(rows.length,first+st.rlim),nav=pages>1?`<button type="button" class="mm-chip mm-pg" data-rpage="${st.rpage-1}" aria-label="Previous page" ${st.rpage===0?"disabled":""}>‹</button><span class="mm-count">${(first+1).toLocaleString()}–${last.toLocaleString()} of ${rows.length.toLocaleString()} companies · page ${st.rpage+1} of ${pages}</span><button type="button" class="mm-chip mm-pg" data-rpage="${st.rpage+1}" aria-label="Next page" ${st.rpage>=pages-1?"disabled":""}>›</button>`:`<span class="mm-count">${rows.length.toLocaleString()} companies</span>`;
  const more=rows.length>20?`<tr class="mm-more"><td colspan="6">${nav}<span class="mm-lb">Per page</span>${[[20,"20"],[100,"100"],[Infinity,"All"]].map(([n,l])=>`<button type="button" class="mm-chip" data-rlim="${n}" aria-pressed="${st.rlim===n}">${l}</button>`).join("")}</td></tr>`:"";
  tb.innerHTML=(html||`<tr><td colspan="6" class="mm-count">No company matches these filters.</td></tr>`)+more;
  const ms=l=>l.filter(c=>c.mfg).length,ov=vis.length-ms(vis);
  const txt=`${nGroups(vis)} manufacturers at ${ms(vis)} sites shown, of ${nGroups(C)} at ${ms(C)}${ov?` · plus ${ov} other organization${ov>1?"s":""}`:""}`;document.getElementById("shown").textContent=txt;document.getElementById("rostercount").textContent=txt}

/* ---------- wiring ---------- */
function select(id){st.sel=(st.sel===id?null:id);_ctr=center();if(st.rings||st.radius)buildRings();render();
  if(st.sel){const row=document.getElementById("row-"+st.sel);if(row)row.scrollIntoView({block:"nearest",behavior:reduced?"auto":"smooth"})}}
function clearAll(){Object.assign(st,{evKind:"all",evYear:null,evMore:0,fed:false,fda:false,radius:0,sel:null,q:"",hum:null});st.cap.clear();st.sec.clear();st.tag.clear();
  document.getElementById("tagsearch").value="";_ctr=center();render()}
document.getElementById("clear").addEventListener("click",clearAll);document.getElementById("resetall").addEventListener("click",clearAll);
document.getElementById("tagsearch").addEventListener("input",e=>{st.q=e.target.value.trim().toLowerCase();renderTags()});
document.getElementById("radius").addEventListener("change",e=>{st.radius=+e.target.value;_ctr=center();buildRings();render()});
for(const [id,k] of [["lay-rings","rings"],["f-fed","fed"],["f-fda","fda"]])document.getElementById(id).addEventListener("click",()=>{st[k]=!st[k];if(k==="rings")buildRings();render()});
/* tabs: Companies, Occupations, Physical AI outlook, Humanoid supply chain; the open tab is part of the URL */
function applyTab(){for(const t of TABS){const on=st.tab===t,b=document.getElementById("t-"+t);b.setAttribute("aria-selected",String(on));b.tabIndex=on?0:-1;document.getElementById("tab-"+t).hidden=!on}
  if(st.tab==="companies")resize()}
function setTab(t,focus){if(!TABS.includes(t)||st.tab===t)return;st.tab=t;applyTab();updateHash();if(focus)document.getElementById("t-"+t).focus();
  const bar=document.querySelector(".mm-tabs");if(bar.getBoundingClientRect().top<parseFloat(getComputedStyle(bar).scrollMarginTop))bar.scrollIntoView({block:"start"})}
document.querySelector(".mm-tabs").addEventListener("keydown",e=>{const i=TABS.indexOf(st.tab),n=TABS.length;
  const j=e.key==="ArrowRight"?(i+1)%n:e.key==="ArrowLeft"?(i+n-1)%n:e.key==="Home"?0:e.key==="End"?n-1:-1;if(j<0)return;e.preventDefault();setTab(TABS[j],true)});
document.addEventListener("click",e=>{
  const tb=e.target.closest("[data-tab]");if(tb){const t=tb.dataset.tab;setTab(t);if(t==="companies"&&tb.dataset.map)document.getElementById("scene").scrollIntoView({block:"center",behavior:reduced?"auto":"smooth"});return}
  const rl=e.target.closest("[data-rlim]");if(rl){st.rlim=rl.dataset.rlim==="Infinity"?Infinity:+rl.dataset.rlim;st.rpage=0;renderTable();return}
  const rp=e.target.closest("[data-rpage]");if(rp&&!rp.disabled){st.rpage=Math.max(0,+rp.dataset.rpage);renderTable();document.querySelector(".mm-roster").scrollIntoView({block:"start"});return}
  const hb=e.target.closest("[data-hb]");if(hb){st.hb=hb.dataset.hb;renderHumanoid();return}
  const hg=e.target.closest("[data-hum]");if(hg){const v=hg.dataset.hum;st.hum=st.hum===v?null:v;render();return}
  const na=e.target.closest("[data-ndrall]");if(na){st.ndrAll=!st.ndrAll;renderOpportunity();return}
  const wv=e.target.closest("[data-wv]");if(wv){st.wv=wv.dataset.wv;renderWork();return}
  const q=e.target.closest("[data-qv],[data-qs]");if(q){if(q.dataset.qv)st.qv=q.dataset.qv;if(q.dataset.qs)st.qs=q.dataset.qs;renderQcew();return}
  const sib=e.target.closest("[data-sel]");if(sib){const c=byId[sib.dataset.sel],away=st.tab!=="companies";setTab("companies");if(st.sel!==c.id)select(c.id);flyTo(c.lat,c.lon,Math.min(view.dist,0.05));if(away)document.getElementById("scene").scrollIntoView({block:"center"});return}
  const cb=e.target.closest("[data-cap]");if(cb){const k=cb.dataset.cap;st.cap.has(k)?st.cap.delete(k):st.cap.add(k);render();return}
  const h=e.target.closest("[data-sort]");if(h){const s=st.sort[h.dataset.kind];if(s.key===h.dataset.sort)s.dir=-s.dir;else{s.key=h.dataset.sort;s.dir=-1}render();return}
  const rs=e.target.closest("[data-rsort]");if(rs){const s=st.sort.roster;if(s.key===rs.dataset.rsort)s.dir=-s.dir;else{s.key=rs.dataset.rsort;s.dir=rs.dataset.rsort==="emp"||rs.dataset.rsort==="fed"?-1:1}st.rpage=0;renderTable();return}
  const yb=e.target.closest("[data-evyear]");if(yb){const y=+yb.dataset.evyear;st.evYear=st.evYear===y?null:y;st.evMore=0;renderEvents();return}
  const kb=e.target.closest("[data-evkind]");if(kb){st.evKind=kb.dataset.evkind;st.evMore=0;renderEvents();return}
  if(e.target.id==="evmore"){st.evMore+=60;renderEvents();return}
  const b=e.target.closest(".mm-bar");if(!b)return;if(b.dataset.sec){const s=b.dataset.sec;st.sec.has(s)?st.sec.delete(s):st.sec.add(s)}else if(b.dataset.tag){const t=b.dataset.tag;st.tag.has(t)?st.tag.delete(t):st.tag.add(t)}else return;render()});
document.addEventListener("mouseover",e=>{const b=e.target.closest(".mm-bar");if(!b||b.classList.contains("ag"))return;st.hot=b.dataset.sec?{sec:b.dataset.sec}:b.dataset.cap?{cap:b.dataset.cap}:{tag:b.dataset.tag};paintBars()});
document.addEventListener("mouseout",e=>{const b=e.target.closest(".mm-bar");if(!b||!st.hot)return;st.hot=null;paintBars()});
document.querySelector("#table tbody").addEventListener("click",e=>{if(e.target.closest("a"))return;
  const g=e.target.closest("tr.grp");if(g){const id=g.dataset.group;st.open.has(id)?st.open.delete(id):st.open.add(id);renderTable();return}
  const r=e.target.closest("tr[data-id]");if(r)select(r.dataset.id)});
document.getElementById("events").addEventListener("click",e=>{if(e.target.closest("a"))return;const r=e.target.closest(".mm-ev");if(r&&r.dataset.id&&byId[r.dataset.id]){const c=byId[r.dataset.id];st.sel=null;select(c.id);flyTo(c.lat,c.lon,Math.min(view.dist,0.12))}});
function toast(msg){let t=document.querySelector(".mm-toast");if(!t){t=document.createElement("div");t.className="mm-toast";document.body.appendChild(t)}t.textContent=msg;t.classList.add("on");setTimeout(()=>t.classList.remove("on"),1800)}
document.getElementById("copylink").addEventListener("click",()=>{const url=location.origin+location.pathname+hashState();(navigator.clipboard?navigator.clipboard.writeText(url):Promise.reject()).then(()=>toast("Link copied")).catch(()=>prompt("Copy this link",url))});
document.getElementById("csv").addEventListener("click",()=>{const rows=C.filter(visible),q=v=>'"'+String(v??"").replace(/"/g,'""')+'"';
  const head=["name","company_group","group_sites","kind","city","state","address","lat","lon","location_precision","sector","products","naics","capabilities","employees","employees_scope","employees_year","employees_quality","employees_note","uei","federal_contracts_usd","federal_grants_usd","sbir_awards","sbir_usd","patents_since_2015","fda_registered","certifications","humanoid_parts","humanoid_evidence","formerly","status_note","website","source","updated"];
  const lines=[head.join(",")].concat(rows.map(c=>{const g=groupOf(c);return [c.name,g.name,g.sites.length,c.kind,c.city,c.state,c.addr,c.lat,c.lon,c.prec,c.sector,c.tags.join("; "),c.naics,c.caps.join("; "),c.emp??"",c.emp?c.emp_scope:"",c.emp_year,c.emp_quality,c.emp_note,c.uei,
    c.federal?c.federal.contracts:"",c.federal?c.federal.grants:"",c.sbir?c.sbir.count:"",c.sbir?c.sbir.amount:"",c.patents?c.patents.count:"",c.fda?"yes":"",c.certs.join("; "),c.hum.join("; "),c.hum.length?c.hum_ev:"",c.formerly,c.status,c.website,c.source,c.updated].map(q).join(",")}));
  const blob=new Blob(["﻿"+lines.join("\n")],{type:"text/csv;charset=utf-8"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="michiana-manufacturing-"+(hashState(false)?"filtered":"all")+".csv";document.body.appendChild(a);a.click();a.remove();toast(`${rows.length} rows downloaded`)});
const chip=(id,on)=>document.getElementById(id).setAttribute("aria-pressed",String(on));
function render(){chip("lay-rings",st.rings);chip("f-fed",st.fed);chip("f-fda",st.fda);document.getElementById("radius").value=String(st.radius);
  _ctr=center();document.getElementById("radius-of").textContent="of "+(st.sel?_ctr.name:"the campus");if(st.rings||st.radius)buildRings();
  document.getElementById("brieflink").href="brief.html"+(st.sec.size?"#sec="+[...st.sec].map(encodeURIComponent).join("|"):"");
  renderSectors();renderTags();renderFederal();renderCaps();renderEvents();renderWork();renderOccHelp();renderOpportunity();renderHumanoid();renderComparison();paintBars();renderDetail();renderTable();layout();updateHash()}
window.addEventListener("hashchange",()=>{if(location.hash!==hashState()){readHash();applyTab();render()}});
document.getElementById("legend").innerHTML=DATA.sectors.map(s=>`<span><i class="mm-sw" style="background:${SCOL[s]};color:${SCOL[s]}"></i>${esc(s)}</span>`).join("")
  +`<span>column height = employees, log scale <i class="mm-hl"><i style="height:6px"></i><i style="height:10px"></i><i style="height:14px"></i><i style="height:18px"></i></i>10 · 100 · 1,000 · 10,000</span><span>~ estimate · ’22 year of the figure · * company-wide</span>`;
const known=C.filter(c=>c.emp).length;
document.getElementById("foot").innerHTML=`${nGroups(C)} companies at ${C.length} sites, built ${esc(DATA.built)}. Every figure comes from a public source; headcounts are approximate and dated (${known} known). Methods, sources and known gaps: <a href="about.html">About the data</a>. Main Building textures adapted from <a href="https://commons.wikimedia.org/wiki/File:Golden_Dome_frontal.jpg">a photo by Eccekevin</a>, <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.`;

/* theme: follow the page's Light/Dark switch (body[data-theme]) */
new MutationObserver(applyTheme).observe(document.body,{attributes:true,attributeFilter:["data-theme"]});
assignBars();applyTab();new ResizeObserver(resize).observe(box);resize();applyTheme();applyView();render();
if(st.sel){const c=byId[st.sel];view.lat=c.lat;view.lon=c.lon;view.dist=0.06}
let t0=performance.now(),intro=!st.sel&&!reduced;
(function loop(now){requestAnimationFrame(loop);
  if(intro&&!drag){const t=(now-t0)/1000;if(t<2.8){const k=1-Math.pow(1-Math.min(t/2.8,1),3);view.dist=Math.exp(Math.log(D_MAX)+(Math.log(home.dist)-Math.log(D_MAX))*k);applyView()}else intro=false}
  if(tween){const k=Math.min(1,(now-tween.t0)/tween.dur),e=k<0.5?2*k*k:1-Math.pow(-2*k+2,2)/2;view.lat=tween.from.lat+(tween.to.lat-tween.from.lat)*e;view.lon=tween.from.lon+(tween.to.lon-tween.from.lon)*e;
    view.dist=Math.exp(Math.log(tween.from.dist)+(Math.log(tween.to.dist)-Math.log(tween.from.dist))*e);applyView();if(k>=1)tween=null}
  renderer.render(scene,camera)})(performance.now());
})();
