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
const nGroups=list=>new Set(list.map(c=>c.group)).size;
const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmtK=v=>v>=10000?Math.round(v/1000)+"k":v>=1000?(v/1000).toFixed(1)+"k":String(v);
const fmtUSD=v=>v>=1e9?"$"+(v/1e9).toFixed(1)+"B":v>=1e6?"$"+(v/1e6).toFixed(1)+"M":v>=1e3?"$"+Math.round(v/1e3)+"k":"$"+Math.round(v);
const empSum=list=>list.reduce((a,c)=>a+(c.emp||0),0);
const shortYear=y=>y?"’"+String(y).slice(2):"";
function fmtEmp(c){if(!c.emp)return "unknown";const bits=[c.emp_year,c.emp_quality,c.emp_scope==="company"?"company-wide":""].filter(Boolean);return (c.emp_quality==="estimate"?"about ":"")+c.emp.toLocaleString()+(bits.length?" ("+bits.join(", ")+")":"")}

/* ---------- state, addressable through the URL hash ---------- */
const st={sec:new Set(),tag:new Set(),cap:new Set(),fed:false,fda:false,rings:false,density:false,radius:0,sel:null,hot:null,q:"",open:new Set(),
  sort:{sec:{key:"n",dir:-1},tag:{key:"n",dir:-1},cap:{key:"n",dir:-1},fed:{key:"e",dir:-1},roster:{key:"emp",dir:-1},ev:{key:"date",dir:-1}},
  evKind:"all",evYear:null,evMore:0,qv:"county",qs:"abs"};
function readHash(){st.sec.clear();st.tag.clear();st.cap.clear();st.fed=st.fda=st.rings=st.density=false;st.radius=0;st.sel=null;
  try{const raw=location.hash.slice(1),h=decodeURIComponent(raw);if(h&&byId[h]){st.sel=h;return}
    for(const kv of raw.split("&")){const i=kv.indexOf("=");if(i<0)continue;const k=kv.slice(0,i),v=decodeURIComponent(kv.slice(i+1));if(!v)continue;const vals=kv.slice(i+1).split("|").map(decodeURIComponent);
      if(k==="sec")vals.forEach(x=>st.sec.add(x));else if(k==="tag")vals.forEach(x=>st.tag.add(x));else if(k==="cap")vals.forEach(x=>st.cap.add(x));
      else if(k==="fed")st.fed=v==="1";else if(k==="fda")st.fda=v==="1";else if(k==="rings")st.rings=v==="1";else if(k==="dens")st.density=v==="1";
      else if(k==="r")st.radius=+v||0;else if(k==="sel"&&byId[v])st.sel=v}}catch(e){}}
const enc=set=>[...set].map(encodeURIComponent).join("|");
function hashState(){const p=[];if(st.sec.size)p.push("sec="+enc(st.sec));if(st.tag.size)p.push("tag="+enc(st.tag));if(st.cap.size)p.push("cap="+enc(st.cap));
  if(st.fed)p.push("fed=1");if(st.fda)p.push("fda=1");if(st.rings)p.push("rings=1");if(st.density)p.push("dens=1");if(st.radius)p.push("r="+st.radius);if(st.sel)p.push("sel="+st.sel);
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
const visibleExcept=skip=>c=>(skip==="sec"||matchSec(c))&&(skip==="tag"||matchTag(c))&&(skip==="cap"||matchCap(c))&&matchFed(c)&&matchFda(c)&&matchRad(c);
const visible=visibleExcept("");
const hotMatch=c=>st.hot&&(st.hot.sec?c.sector===st.hot.sec:st.hot.cap?c.caps.includes(st.hot.cap):c.tags.includes(st.hot.tag));

/* ---------- theme: dark by default; follows the page's Light/Dark switch ---------- */
const THEMES={
  dark:{bg:"#05070b",ground:0x0a0e14,groundMetal:0.7,grat:0x17212c,lakeFill:"#0b1b30",lakeStroke:"rgba(42,127,166,0.9)",core:0x182734,far:0x10161e,landMetal:0.6,
    coreLine:0x35d6ff,coreLineOp:0.75,farLine:0x2a4150,cityDot:0xe6edf3,dotMajor:0xffb020,dotMinor:0x9fb0c0,ring:0x35d6ff,halo:0x35d6ff,hemi:[0x9fd6ff,0x0a0f16,0.8],key:0.9,
    glow:0.09,dimMix:null,dimK:0.3,dimOp:0.12,heat:["#0d3446","#1aa3c9","#e8fbff"],
    labels:{city:["#dfe9f2"],county:["#35d6ff"],metroMajor:["#ffd280","#ffb020"],metroMinor:["#b8c6d4"],state:["#4f6478"],region:["#35d6ff","#35d6ff"],ring:["#35d6ff"],landmark:["#ffd280","#ffb020"]}},
  light:{bg:"#e8edf2",ground:0xdbe2e9,groundMetal:0.05,grat:0xc6d0da,lakeFill:"#bcd6ea",lakeStroke:"rgba(30,100,150,0.85)",core:0xfbfcfd,far:0xe9eef2,landMetal:0.05,
    coreLine:0x0a7fa8,coreLineOp:0.85,farLine:0xb3c0cc,cityDot:0x1b2733,dotMajor:0xb86e00,dotMinor:0x5d6b78,ring:0x0a7fa8,halo:0x0a6f93,hemi:[0xffffff,0xb8c2cc,1.05],key:0.55,
    glow:0,dimMix:"#ffffff",dimK:0.55,dimOp:0.22,heat:["#cfe3ee","#2a8db8","#0b2f45"],
    labels:{city:["#1b2733"],county:["#0a6f93"],metroMajor:["#8a4b00"],metroMinor:["#3d4a57"],state:["#8794a1"],region:["#0a6f93"],ring:["#0a6f93"],landmark:["#8a5a00"]}}};
let TH=THEMES.dark;
const themeName=()=>document.body.getAttribute("data-theme")==="light"?"light":"dark";

/* ---------- globe ---------- */
const R=10, KM=6371/R;
const [LATC,LONC]=DATA.center;
const P=(lat,lon,h=0)=>{const la=lat*RAD,lo=lon*RAD,r=R+h;return new THREE.Vector3(r*Math.cos(la)*Math.sin(lo),r*Math.sin(la),r*Math.cos(la)*Math.cos(lo))};
const latLonOf=p=>{const r=p.length();return [Math.asin(p.y/r)/RAD,Math.atan2(p.x,p.z)/RAD]};
const box=document.getElementById("scene"), tip=document.getElementById("tip"), hud=document.getElementById("hud");
const renderer=new THREE.WebGLRenderer({antialias:true,logarithmicDepthBuffer:true}); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.outputEncoding=THREE.sRGBEncoding; box.appendChild(renderer.domElement);
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
const dome=(function(){const g=new THREE.Group(),brick=new THREE.MeshStandardMaterial({color:0xd8c48f,roughness:0.85}),trim=new THREE.MeshStandardMaterial({color:0xf2ead6,roughness:0.7});
  /* polished gold: metal only shines when it has something to reflect, so the gold gets its own small studio
     environment (sky gradient, warm horizon, bright soft-box highlights) prefiltered for image-based lighting */
  const env=(function(){const cv=document.createElement("canvas");cv.width=1024;cv.height=512;const x=cv.getContext("2d");
    const g=x.createLinearGradient(0,0,0,512);g.addColorStop(0,"#ffffff");g.addColorStop(0.3,"#e4eeff");g.addColorStop(0.48,"#fff6dc");g.addColorStop(0.53,"#ffd98a");g.addColorStop(0.62,"#d9a441");g.addColorStop(1,"#8a6424");
    x.fillStyle=g;x.fillRect(0,0,1024,512);
    for(const [cx,cy,r,a] of [[180,120,70,1],[560,90,55,0.95],[860,150,80,1],[360,210,40,0.8],[720,230,35,0.7],[90,330,60,0.6],[620,360,70,0.55]]){const rg=x.createRadialGradient(cx,cy,0,cx,cy,r);rg.addColorStop(0,"rgba(255,255,255,"+a+")");rg.addColorStop(1,"rgba(255,255,255,0)");x.fillStyle=rg;x.fillRect(cx-r,cy-r,2*r,2*r)}
    const t=new THREE.CanvasTexture(cv);t.mapping=THREE.EquirectangularReflectionMapping;t.encoding=THREE.sRGBEncoding;
    const pm=new THREE.PMREMGenerator(renderer);const out=pm.fromEquirectangular(t).texture;pm.dispose();t.dispose();return out})();
  const gold=new THREE.MeshStandardMaterial({color:0xffc94a,metalness:1,roughness:0.1,envMap:env,envMapIntensity:2.4,emissive:0x5a3c00,emissiveIntensity:0.22}),slate=new THREE.MeshStandardMaterial({color:0x5b6670,roughness:0.9});
  const add=(geo,mat,x,y,z)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);g.add(m)};const B=0.0016;
  add(new THREE.BoxGeometry(1.9*B,0.015*B,1.1*B),new THREE.MeshStandardMaterial({color:0x1d4a2e,roughness:1}),0,0.005*B,0);
  add(new THREE.BoxGeometry(1.5*B,0.30*B,0.34*B),brick,0,0.15*B,0.2*B);add(new THREE.BoxGeometry(1.5*B,0.03*B,0.36*B),slate,0,0.315*B,0.2*B);
  add(new THREE.BoxGeometry(0.46*B,0.46*B,0.46*B),brick,0,0.23*B,0.2*B);add(new THREE.BoxGeometry(0.50*B,0.03*B,0.50*B),trim,0,0.47*B,0.2*B);
  add(new THREE.CylinderGeometry(0.17*B,0.19*B,0.20*B,24),trim,0,0.58*B,0.2*B);add(new THREE.SphereGeometry(0.19*B,32,16,0,Math.PI*2,0,Math.PI/2),gold,0,0.68*B,0.2*B);
  add(new THREE.CylinderGeometry(0.045*B,0.05*B,0.09*B,12),gold,0,0.91*B,0.2*B);add(new THREE.CylinderGeometry(0.012*B,0.025*B,0.08*B,8),gold,0,0.99*B,0.2*B);add(new THREE.SphereGeometry(0.02*B,8,8),gold,0,1.04*B,0.2*B);
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
  halo.material.opacity=st.sel?0.9:0;layoutBars(lastK);paintHeat()}

/* density: companies in the filter counted on a grid; two grids, fine (about 4.5 km) and coarse (about 13 km), by zoom */
const HEAT=[{dLa:0.04,dLo:0.054},{dLa:0.12,dLo:0.16}].map(g=>{const cells={};for(const b of bars){const k=Math.floor(b.c.lat/g.dLa)+":"+Math.floor(b.c.lon/g.dLo);
    (cells[k]=cells[k]||{la:(Math.floor(b.c.lat/g.dLa)+0.5)*g.dLa,lo:(Math.floor(b.c.lon/g.dLo)+0.5)*g.dLo,members:[]}).members.push(b.c)}
  const list=Object.values(cells),geo=new THREE.BoxGeometry(1,1,1);geo.translate(0,0.5,0);
  const mesh=new THREE.InstancedMesh(geo,new THREE.MeshBasicMaterial({transparent:true,opacity:0.88}),list.length);mesh.instanceColor=new THREE.InstancedBufferAttribute(new Float32Array(list.length*3),3);
  mesh.visible=false;globe.add(mesh);
  list.forEach(cl=>{cl.pos=P(cl.la,cl.lo,lift(2.1));cl.quat=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),cl.pos.clone().normalize());
    cl.sx=g.dLo*Math.cos(cl.la*RAD)*R*RAD*0.92;cl.sz=g.dLa*R*RAD*0.92});return {g,list,mesh}});
const heatColor=(t,out)=>{const [a,b,c]=TH.heat.map(h=>new THREE.Color(h));return t<0.5?out.copy(a).lerp(b,t*2):out.copy(b).lerp(c,(t-0.5)*2)};
function paintHeat(){for(const H of HEAT){let max=1;for(const cl of H.list){cl.n=cl.members.filter(visible).length;cl.e=empSum(cl.members.filter(visible));if(cl.n>max)max=cl.n}
  H.list.forEach((cl,i)=>{const t=cl.n?Math.log(1+cl.n)/Math.log(1+max):0;_s.set(cl.n?cl.sx:1e-6,cl.n?Math.max(lift(1),lift(40)*t):1e-6,cl.n?cl.sz:1e-6);_m.compose(cl.pos,cl.quat,_s);H.mesh.setMatrixAt(i,_m);
    heatColor(t,_c);_c.convertSRGBToLinear();H.mesh.setColorAt(i,_c)});H.mesh.instanceMatrix.needsUpdate=true;H.mesh.instanceColor.needsUpdate=true}}
const heatOn=()=>st.density||view.dist>0.55;

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
  glowMesh.material.opacity=TH.glow;glowMesh.visible=TH.glow>0&&!heatOn();dimMesh.material.opacity=TH.dimOp;
  paintLakes();labels.forEach(drawLabel);paintBars();if(typeof renderQcew==="function")renderQcew()}

/* ---------- view: one continuous zoom on a true-scale globe ---------- */
const D_MIN=0.005, D_MAX=1.35, D_HOME=0.26;            // 0.005 ≈ 3 km up, close enough to see the dome
const view={lat:LATC,lon:LONC,dist:D_HOME}, home={...view};
const tiltFor=d=>0.58*(1-THREE.MathUtils.smoothstep(Math.log(d),Math.log(0.12),Math.log(1.3)))+0.08;
function layout(){const d=view.dist,screen=d/D_HOME;
  for(const o of placed){const L=o.userData.lay;if(L.mode==="map")continue;o.scale.copy(L.base).multiplyScalar(screen)}
  layoutBars(KREF*Math.min(screen,2.2));
  const heat=heatOn(),fine=d<0.7;barMesh.visible=dimMesh.visible=!heat;glowMesh.visible=!heat&&TH.glow>0;HEAT[0].mesh.visible=heat&&fine;HEAT[1].mesh.visible=heat&&!fine;halo.visible=!heat;
  near.visible=d<0.55;mid.visible=d>0.45;far.visible=d>0.7;dome.visible=d<0.09;ringGroup.visible=st.rings;
  hud.innerHTML=`<span>ALT</span> ${(d*KM).toFixed(d<0.05?1:0)} km &nbsp; <span>CTR</span> ${view.lat.toFixed(3)}°N ${(-view.lon).toFixed(3)}°W &nbsp; <span>SPAN</span> ${(2*d*Math.tan(0.3665)*KM).toFixed(0)} km${heat?" &nbsp; <span>DENSITY</span>":""}`}
function applyView(){layout();const d=view.dist,t=tiltFor(d);globe.rotation.set(view.lat*RAD,-view.lon*RAD,0);
  camera.near=Math.max(0.0005,d*0.04);camera.far=d*60+2*R;camera.updateProjectionMatrix();camera.position.set(0,-d*Math.sin(t),R+d*Math.cos(t));camera.lookAt(0,0,R)}
let tween=null;
function flyTo(lat,lon,dist){const from={...view},to={lat,lon,dist:dist??view.dist};if(reduced){Object.assign(view,to);applyView();return}
  tween={from,to,t0:performance.now(),dur:700}}
const ray=new THREE.Raycaster(),ndc=new THREE.Vector2();
const pickSphere=new THREE.Mesh(new THREE.SphereGeometry(R,64,32),new THREE.MeshBasicMaterial({visible:false}));globe.add(pickSphere);
function toNdc(e){const r=renderer.domElement.getBoundingClientRect();ndc.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(ndc,camera)}
function surfaceAt(e){toNdc(e);const h=ray.intersectObject(pickSphere,false)[0];return h?latLonOf(globe.worldToLocal(h.point.clone())):null}
function pick(e){toNdc(e);if(heatOn()){const H=HEAT[view.dist<0.7?0:1],hit=ray.intersectObject(H.mesh,false)[0];return hit&&hit.instanceId!=null&&H.list[hit.instanceId].n?{cell:H.list[hit.instanceId],mesh:H.mesh,i:hit.instanceId}:null}
  const hit=ray.intersectObject(barMesh,false)[0];return hit&&hit.instanceId!=null?onList[hit.instanceId]:null}
let drag=null,hoverId=null;
box.addEventListener("pointerdown",e=>{if(e.target.closest(".mm-ctl"))return;tween=null;drag={x:e.clientX,y:e.clientY,lat:view.lat,lon:view.lon,moved:false};box.setPointerCapture(e.pointerId)});
box.addEventListener("pointermove",e=>{if(drag){const r=renderer.domElement.getBoundingClientRect(),k=(2*view.dist*Math.tan(0.3665)/r.height)/(R*RAD);
    view.lat=THREE.MathUtils.clamp(drag.lat+(e.clientY-drag.y)*k,36,48);view.lon=THREE.MathUtils.clamp(drag.lon-(e.clientX-drag.x)*k/Math.cos(view.lat*RAD),-95,-77);
    if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>4)drag.moved=true;applyView();tip.style.opacity=0}else hover(e)});
box.addEventListener("pointerup",e=>{if(drag&&!drag.moved){const b=pick(e);if(b&&b.cell){const cl=b.cell;flyTo(cl.la,cl.lo,0.12);if(st.density){st.density=false;render()}}else if(b)select(b.c.id)}drag=null});
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
  if(b&&b.cell){b.mesh.getMatrixAt(b.i,_m);const top=new THREE.Vector3(0,1,0).applyMatrix4(_m).applyMatrix4(globe.matrixWorld).project(camera);
    tip.innerHTML=`<b>${b.cell.n} compan${b.cell.n===1?"y":"ies"} here</b>${b.cell.e?fmtK(b.cell.e)+" staff, known headcounts":""}<div class="m">click to zoom in</div>`;
    tip.style.left=((top.x+1)/2*r.width)+"px";tip.style.top=((1-top.y)/2*r.height)+"px";tip.style.opacity=1;box.style.cursor="pointer";return}
  if(b){barMesh.getMatrixAt(b.oi,_m);const top=new THREE.Vector3(0,1,0).applyMatrix4(_m).applyMatrix4(globe.matrixWorld).project(camera);const g=groupOf(b.c);
    tip.innerHTML=`<b>${esc(b.c.name)}</b>${esc(b.c.city)}, ${esc(b.c.state)} · ${esc(b.c.sector)}${g.sites.length>1?`<div class="m">one of ${g.sites.length} sites of ${esc(g.name)}</div>`:""}<div class="m">${esc(fmtEmp(b.c))} employees</div>`;
    tip.style.left=((top.x+1)/2*r.width)+"px";tip.style.top=((1-top.y)/2*r.height)+"px";tip.style.opacity=1;box.style.cursor="pointer"}
  else{tip.style.opacity=0;box.style.cursor=drag?"grabbing":"grab"}}
function resize(){const w=box.clientWidth,h=Math.max(360,Math.min(640,Math.round(w*0.64)));box.style.height=h+"px";renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}

/* ---------- company search ---------- */
const find=document.getElementById("find"),sug=document.getElementById("find-list");let sugItems=[],sugIdx=-1;
function searchItems(q){q=q.trim().toLowerCase();if(q.length<2)return [];const out=[],seen=new Set();
  for(const g of Object.values(GROUPS))if(g.sites.length>1&&g.name.toLowerCase().includes(q)){out.push({kind:"group",g});seen.add(g.id)}
  for(const c of C){if(out.length>=40)break;if(c.name.toLowerCase().includes(q)||c.city.toLowerCase().startsWith(q))out.push({kind:"site",c})}
  return out.sort((a,b)=>{const na=(a.g?a.g.name:a.c.name).toLowerCase(),nb=(b.g?b.g.name:b.c.name).toLowerCase();return (nb.startsWith(q)-na.startsWith(q))||(a.kind==="group"?-1:0)-(b.kind==="group"?-1:0)||na.localeCompare(nb)}).slice(0,10)}
function showSug(){sugItems=searchItems(find.value);sugIdx=sugItems.length?0:-1;
  sug.innerHTML=sugItems.map((it,i)=>it.kind==="group"?`<div class="mm-sugi" role="option" id="sug-${i}" data-i="${i}" aria-selected="${i===sugIdx}"><b>${esc(it.g.name)}</b><span>${it.g.sites.length} sites</span></div>`
    :`<div class="mm-sugi" role="option" id="sug-${i}" data-i="${i}" aria-selected="${i===sugIdx}"><b>${esc(it.c.name)}</b><span>${esc(it.c.city)} · ${esc(it.c.sector)}</span></div>`).join("")||(find.value.trim().length>1?`<div class="mm-sugi none">No company matches “${esc(find.value)}”.</div>`:"");
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
    +`<div class="mm-hh" style="margin-top:8px"><span>region-wide, by awarding agency (all recipients)</span><span></span><span>$</span></div>`
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
const EVKINDS=[["all","All"],["federal","Federal awards"],["sbir","SBIR/STTR"],["patent","Patents"]];
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
  d.innerHTML=`<h3><span class="mm-dot" style="background:${SCOL[c.sector]};color:${SCOL[c.sector]}"></span>${esc(c.name)}</h3>
  ${g.sites.length>1?`<div class="mm-grp"><div class="k">Part of ${esc(g.name)}: ${g.sites.length} sites, ${fmtK(empSum(g.sites))} staff known</div>${sib.slice(0,12).map(s=>`<button type="button" class="mm-sib" data-sel="${s.id}">${esc(s.city)}${s.emp?" · "+fmtK(s.emp):""}<span>${esc(s.name.replace(g.name,"").replace(/^[,\s]+/,"")||s.addr||"site")}</span></button>`).join("")}${sib.length>12?`<span class="mm-count">and ${sib.length-12} more</span>`:""}</div>`:""}
  <div><div class="k">What they do</div>${esc(c.blurb)||"–"}<div class="k">Products &amp; services</div>${esc(c.tags.join(", "))}${c.naics?`<div class="k">NAICS</div>${esc(c.naics)}`:""}${c.caps.length?`<div class="k">Capabilities</div>${esc(c.caps.join(", "))}`:""}</div>
  <div><div class="k">Employees</div>${esc(fmtEmp(c))}${c.emp_note?`<div class="mm-note">${esc(c.emp_note)}</div>`:""}<div class="k">Location</div>${esc(c.addr||c.city+", "+c.state)}${c.prec==="city"?" (placed at the city center)":""}
  ${c.website?`<div class="k">Website</div><a href="${esc(c.website)}" rel="noopener">${site(c.website)}</a>`:""}${c.uei?`<div class="k">UEI</div>${esc(c.uei)}`:""}</div>
  <div>${c.federal?`<div class="k">Federal awards since FY2016</div>contracts ${fmtUSD(c.federal.contracts)} · grants ${fmtUSD(c.federal.grants)} (USAspending)`:""}${c.sbir?`<div class="k">SBIR/STTR</div>${c.sbir.count} awards, ${fmtUSD(c.sbir.amount)} (${esc(c.sbir.agencies.join(", "))})`:""}
  ${c.patents?`<div class="k">Patents since 2015</div>${c.patents.count}${c.patents.latest.length?": "+c.patents.latest.slice(0,3).map(p=>esc(p.title)).join("; "):""}`:""}
  ${c.fda?`<div class="k">FDA device establishment</div>${esc([...c.fda.types,...c.fda.devices].join(", ")||"registered")}`:""}${c.certs.filter(x=>!/^FDA/.test(x)).length?`<div class="k">Certifications</div>${esc(c.certs.filter(x=>!/^FDA/.test(x)).join(", "))}`:""}</div>
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
  let html="",lim=0;for(const r of rows){if(lim++>700){html+=`<tr><td colspan="6" class="mm-count">Showing the first 700 of ${rows.length}; narrow the filters to see more.</td></tr>`;break}
    if(r.list.length===1){html+=siteRow(r.list[0],false);continue}
    const open=st.open.has(r.gid),cities=[...new Set(r.list.map(c=>c.city))];
    html+=`<tr class="grp${r.list.some(c=>c.id===st.sel)?" sel":""}" data-group="${esc(r.gid)}"><td class="name"><button type="button" class="mm-caret" aria-expanded="${open}" aria-label="${open?"Collapse":"Expand"} ${esc(r.name)}">${open?"▾":"▸"}</button>${esc(r.name)}<small>${r.list.length} sites · ${esc(cities.slice(0,3).join(", "))}${cities.length>3?" …":""}</small></td><td><span class="mm-dot" style="background:${SCOL[r.sector]};color:${SCOL[r.sector]}"></span>${esc(r.sector)}</td><td class="num">${empCell(r.list)}</td><td class="tags">${esc([...new Set(r.list.flatMap(c=>c.tags))].slice(0,4).join(", "))}</td><td class="num">${r.fed?fmtUSD(r.fed):"–"}</td><td>${web(r.list.find(c=>c.website)?.website)}</td></tr>`;
    if(open)for(const c of r.list.slice().sort((a,b)=>(b.emp||0)-(a.emp||0)))html+=siteRow(c,true)}
  tb.innerHTML=html||`<tr><td colspan="6" class="mm-count">No company matches these filters.</td></tr>`;
  const txt=`${nGroups(vis)} companies at ${vis.length} sites shown, of ${nGroups(C)} at ${C.length}`;document.getElementById("shown").textContent=txt;document.getElementById("rostercount").textContent=txt}

/* ---------- wiring ---------- */
function select(id){st.sel=(st.sel===id?null:id);_ctr=center();if(st.rings||st.radius)buildRings();render();
  if(st.sel){const row=document.getElementById("row-"+st.sel);if(row)row.scrollIntoView({block:"nearest",behavior:reduced?"auto":"smooth"})}}
function clearAll(){Object.assign(st,{evKind:"all",evYear:null,evMore:0,fed:false,fda:false,density:false,radius:0,sel:null,q:""});st.cap.clear();st.sec.clear();st.tag.clear();
  document.getElementById("tagsearch").value="";_ctr=center();render()}
document.getElementById("clear").addEventListener("click",clearAll);document.getElementById("resetall").addEventListener("click",clearAll);
document.getElementById("tagsearch").addEventListener("input",e=>{st.q=e.target.value.trim().toLowerCase();renderTags()});
document.getElementById("radius").addEventListener("change",e=>{st.radius=+e.target.value;_ctr=center();buildRings();render()});
for(const [id,k] of [["lay-rings","rings"],["lay-density","density"],["f-fed","fed"],["f-fda","fda"]])document.getElementById(id).addEventListener("click",()=>{st[k]=!st[k];if(k==="rings")buildRings();render()});
document.addEventListener("click",e=>{
  const q=e.target.closest("[data-qv],[data-qs]");if(q){if(q.dataset.qv)st.qv=q.dataset.qv;if(q.dataset.qs)st.qs=q.dataset.qs;renderQcew();return}
  const sib=e.target.closest("[data-sel]");if(sib){const c=byId[sib.dataset.sel];select(c.id);flyTo(c.lat,c.lon,Math.min(view.dist,0.05));return}
  const cb=e.target.closest("[data-cap]");if(cb){const k=cb.dataset.cap;st.cap.has(k)?st.cap.delete(k):st.cap.add(k);render();return}
  const h=e.target.closest("[data-sort]");if(h){const s=st.sort[h.dataset.kind];if(s.key===h.dataset.sort)s.dir=-s.dir;else{s.key=h.dataset.sort;s.dir=-1}render();return}
  const rs=e.target.closest("[data-rsort]");if(rs){const s=st.sort.roster;if(s.key===rs.dataset.rsort)s.dir=-s.dir;else{s.key=rs.dataset.rsort;s.dir=rs.dataset.rsort==="emp"||rs.dataset.rsort==="fed"?-1:1}renderTable();return}
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
  const head=["name","company_group","group_sites","kind","city","state","address","lat","lon","location_precision","sector","products","naics","capabilities","employees","employees_scope","employees_year","employees_quality","employees_note","uei","federal_contracts_usd","federal_grants_usd","sbir_awards","sbir_usd","patents_since_2015","fda_registered","certifications","website","source","updated"];
  const lines=[head.join(",")].concat(rows.map(c=>{const g=groupOf(c);return [c.name,g.name,g.sites.length,c.kind,c.city,c.state,c.addr,c.lat,c.lon,c.prec,c.sector,c.tags.join("; "),c.naics,c.caps.join("; "),c.emp??"",c.emp?c.emp_scope:"",c.emp_year,c.emp_quality,c.emp_note,c.uei,
    c.federal?c.federal.contracts:"",c.federal?c.federal.grants:"",c.sbir?c.sbir.count:"",c.sbir?c.sbir.amount:"",c.patents?c.patents.count:"",c.fda?"yes":"",c.certs.join("; "),c.website,c.source,c.updated].map(q).join(",")}));
  const blob=new Blob(["﻿"+lines.join("\n")],{type:"text/csv;charset=utf-8"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="michiana-manufacturing-"+(hashState()?"filtered":"all")+".csv";document.body.appendChild(a);a.click();a.remove();toast(`${rows.length} rows downloaded`)});
const chip=(id,on)=>document.getElementById(id).setAttribute("aria-pressed",String(on));
function render(){chip("lay-rings",st.rings);chip("lay-density",st.density);chip("f-fed",st.fed);chip("f-fda",st.fda);document.getElementById("radius").value=String(st.radius);
  _ctr=center();document.getElementById("radius-of").textContent="of "+(st.sel?_ctr.name:"the campus");if(st.rings||st.radius)buildRings();
  document.getElementById("brieflink").href="brief.html"+(st.sec.size?"#sec="+[...st.sec].map(encodeURIComponent).join("|"):"");
  renderSectors();renderTags();renderFederal();renderCaps();renderEvents();paintBars();renderDetail();renderTable();layout();updateHash()}
window.addEventListener("hashchange",()=>{if(location.hash!==hashState()){readHash();render()}});
document.getElementById("legend").innerHTML=DATA.sectors.map(s=>`<span><i class="mm-sw" style="background:${SCOL[s]};color:${SCOL[s]}"></i>${esc(s)}</span>`).join("")
  +`<span>column height = employees, log scale <i class="mm-hl"><i style="height:6px"></i><i style="height:10px"></i><i style="height:14px"></i><i style="height:18px"></i></i>10 · 100 · 1,000 · 10,000</span><span>~ estimate · ’22 year of the figure · * company-wide</span><span>zoomed out, columns become a density grid</span>`;
const known=C.filter(c=>c.emp).length;
document.getElementById("foot").innerHTML=`${nGroups(C)} companies at ${C.length} sites, built ${esc(DATA.built)}. Every figure comes from a public source; headcounts are approximate and dated (${known} known). Methods, sources and known gaps: <a href="about.html">About the data</a>.`;

/* theme: follow the page's Light/Dark switch (body[data-theme]) */
new MutationObserver(applyTheme).observe(document.body,{attributes:true,attributeFilter:["data-theme"]});
assignBars();new ResizeObserver(resize).observe(box);resize();applyTheme();applyView();render();
if(st.sel){const c=byId[st.sel];view.lat=c.lat;view.lon=c.lon;view.dist=0.06}
let t0=performance.now(),intro=!st.sel&&!reduced;
(function loop(now){requestAnimationFrame(loop);
  if(intro&&!drag){const t=(now-t0)/1000;if(t<2.8){const k=1-Math.pow(1-Math.min(t/2.8,1),3);view.dist=Math.exp(Math.log(D_MAX)+(Math.log(home.dist)-Math.log(D_MAX))*k);applyView()}else intro=false}
  if(tween){const k=Math.min(1,(now-tween.t0)/tween.dur),e=k<0.5?2*k*k:1-Math.pow(-2*k+2,2)/2;view.lat=tween.from.lat+(tween.to.lat-tween.from.lat)*e;view.lon=tween.from.lon+(tween.to.lon-tween.from.lon)*e;
    view.dist=Math.exp(Math.log(tween.from.dist)+(Math.log(tween.to.dist)-Math.log(tween.from.dist))*e);applyView();if(k>=1)tween=null}
  renderer.render(scene,camera)})(performance.now());
})();
