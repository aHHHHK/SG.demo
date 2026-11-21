import * as THREE from './vendor/three.module.js';

const $ = id => document.getElementById(id);
// The endpoint is public configuration; the access code stays in this tab only.
let apiOrigin = localStorage.getItem('sg-api-origin') || '';
let accessToken = sessionStorage.getItem('sg-access-token') || '';
const connection = document.createElement('form');
connection.style.cssText = 'padding:12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center';
connection.innerHTML = '<label>后端地址 <input name="endpoint" type="url" placeholder="https://xxx.trycloudflare.com" aria-label="后端 HTTPS 地址"></label><label>访问码 <input name="token" type="password" autocomplete="off" aria-label="后端访问码"></label><button type="submit">保存并连接</button><span>本机运行可留空；访问码仅保存在当前标签页</span>';
connection.elements.endpoint.value = apiOrigin;
connection.elements.token.value = accessToken;
document.body.prepend(connection);
connection.onsubmit = event => {
  event.preventDefault();
  const endpoint = connection.elements.endpoint.value.trim();
  if (endpoint) {
    const url = new URL(endpoint);
    if (url.protocol !== 'https:' || url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
      alert('请输入纯 HTTPS 后端地址，不要包含路径、账号或参数'); return;
    }
    localStorage.setItem('sg-api-origin', url.origin);
  } else localStorage.removeItem('sg-api-origin');
  sessionStorage.setItem('sg-access-token', connection.elements.token.value.trim());
  location.reload();
};
let session, current, history = [], running = false, busy = false, replaying = false;
let nextTick = 0;
const controls = ['q_f','q_s','t_f','t_av'];
function showError(message) { $('error').hidden = !message; $('error').textContent = message; }
async function api(path, data = {}) {
  const headers = {'Content-Type':'application/json'};
  if (accessToken) headers.Authorization = 'Bearer ' + accessToken;
  const response = await fetch(apiOrigin + '/api/' + path, {method:'POST', headers, body:JSON.stringify({session, ...data})});
  if (!response.headers.get('Content-Type')?.includes('application/json')) {
    throw new Error('接口没有返回 JSON，请在页面顶部设置正确的后端地址，并确认隧道仍在运行');
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '服务器请求失败');
  return result;
}
function readControls() {
  const c = Object.fromEntries(controls.map(id => [id, Number($(id).value)]));
  return {...c, mode:$('mode').value, setpoint:current.derived.reference_level + Number($('offset').value)};
}
function updateOutputs() {
  $('q_f-out').textContent = Number($('q_f').value).toFixed(1)+' kg/s';
  $('q_s-out').textContent = Number($('q_s').value).toFixed(1)+' kg/s';
  $('offset-out').textContent = Number($('offset').value).toFixed(2)+' m';
  const target=Number($('t_av').value)+Number($('t_f').value)*Number($('ratio').value);
  $('temp-reference').textContent=Number.isFinite(target)?target.toFixed(3)+' °C':'—';
  for (const id of [...controls,'offset']) $(id).disabled = $('mode').value !== 'manual';
}
document.querySelectorAll('input,select').forEach(el => el.addEventListener('input', updateOutputs));
updateOutputs();
function setRunning(value) {
  running = value;
  $('run').textContent = running ? 'Ⅱ 暂停仿真' : '▶ 开始仿真';
  $('step').disabled = running || busy;
  $('replay').disabled = running || history.length < 2;
  $('status').textContent = running ? '● 仿真运行中' : '● 模型已连接 · 已暂停';
  if (running) { replaying = false; renderSnapshot(current); nextTick = performance.now(); }
}
async function step() {
  if (busy || !session || replaying) return;
  busy = true; $('step').disabled = true; $('reset').disabled = true;
  const start = performance.now();
  try {
    const result = await api('step', {dt:1, controls:readControls()});
    current = result.snapshot; history.push(current);
    if (history.length > 12000) history.shift();
    $('replay').max = history.length-1; $('replay').value = history.length-1;
    renderSnapshot(current); showError('');
    $('compute').textContent = `Ipopt · ${(performance.now()-start).toFixed(0)} ms / 步`;
    if(current.time >= current.provenance.duration) { setRunning(false); $('status').textContent='● 原脚本实验已完成'; }
  } catch(error) { setRunning(false); showError('计算已停止，保留上一个有效状态。'+error.message); }
  finally { busy = false; $('step').disabled = running; $('reset').disabled = false; $('replay').disabled = running || history.length < 2; }
}
$('run').onclick = () => setRunning(!running);
$('step').onclick = () => { replaying = false; step(); };
$('reset').onclick = async () => {
  if (busy) return;
  setRunning(false); busy = true; $('reset').disabled = true;
  try {
    const result = await api('reset', {profile:$('profile').value, ratio:Number($('ratio').value),variant:$('variant').value}); current = result.snapshot; history = [current]; replaying = false;
    controls.forEach(id => $(id).value = current.controls[id]);
    $('mode').value = 'baseline'; $('offset').value = 0;
    $('replay').max = 0; $('replay').value = 0; $('replay').disabled = true;
    updateOutputs(); renderSnapshot(current); showError('');
  } catch(error) { showError(error.message); }
  finally { busy = false; $('reset').disabled = false; }
};
document.querySelectorAll('[data-scenario]').forEach(button => button.onclick = async () => {
  if(busy || !current) return;
  setRunning(false); busy=true;
  try {
    const result=await api('action',{action:button.dataset.scenario,ratio:Number($('ratio').value),
      temperatures:{t_av:Number($('t_av').value),t_f:Number($('t_f').value)}});
    current=result.snapshot;history=result.history;replaying=false;
    controls.forEach(id=>$(id).value=current.inputs[id]);
    $('mode').value=current.controls.mode;
    $('replay').max=history.length-1;$('replay').value=history.length-1;
    updateOutputs();renderSnapshot(current);showError('');
    if(button.dataset.scenario==='temp'){
      $('temp-applied').textContent=current.inputs.t_av.toFixed(3)+' °C';
    } else if(button.dataset.scenario==='restore') $('temp-applied').textContent='—';
    $('status').textContent='● 操作已完成 · 已暂停';
  } catch(error){showError(error.message);}
  finally{busy=false;$('step').disabled=false;$('reset').disabled=false;}
});
$('replay').oninput = () => {
  if (running || busy) return;
  replaying = true;
  const index = Number($('replay').value);
  renderSnapshot(history[index], index);
  $('status').textContent = '◷ 历史回放 · 不推进模型';
};
$('live').onclick = () => { replaying = false; renderSnapshot(current); $('replay').value = history.length-1; setRunning(false); };
$('export').onclick = () => {
  if (!history.length) return;
  const rows = [['profile','model','experiment_mode','variant','ratio','time_s','P_MPa','level_m','delta_level_m','V_wt_m3','V_sd_m3','alpha_r','alpha_bar_v','q_f_kg_s','q_s_kg_s','setpoint_m','t_f_C','t_av_C','mass_residual_kg_s','energy_residual_kW','nmpc_objective','nmpc_slack_m']];
  for (const s of history) rows.push([s.provenance.profile,s.provenance.model,s.provenance.mode,s.provenance.variant,s.provenance.ratio,s.time,s.state.P,s.derived.level,s.derived.delta_level,s.state.V_wt,s.state.V_sd,s.state.alpha_r,s.derived.alpha_bar_v,s.inputs.q_f,s.inputs.q_s,s.controls.setpoint,s.inputs.t_f,s.inputs.t_av,s.derived.mass_equation_residual,s.derived.energy_equation_residual,s.derived.objective,s.derived.slack]);
  const url = URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row=>row.join(',')).join('\n')],{type:'text/csv;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = 'sg-lab-'+current.provenance.profile+'.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
};

// Native WebGL scene. All geometry is explicitly schematic, not a CAD claim.
const canvas = $('scene');
let renderer;
try { renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true}); }
catch(error) { showError('浏览器无法创建 WebGL 三维视图；请开启硬件加速。'+error.message); throw error; }
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36,1,0.1,100);
scene.add(new THREE.HemisphereLight(0xd8f2ff,0x1e293a,2.5));
const key = new THREE.DirectionalLight(0xc2e6ff,3); key.position.set(4,8,6); scene.add(key);
const warm = new THREE.DirectionalLight(0xffb974,1.5); warm.position.set(-4,2,-4); scene.add(warm);
const assembly = new THREE.Group(); scene.add(assembly);
const hitTargets = [];
const materials = {
  metal:new THREE.MeshStandardMaterial({color:0x7a9bad,metalness:0.75,roughness:0.28}),
  copper:new THREE.MeshStandardMaterial({color:0xe6a264,metalness:0.65,roughness:0.28}),
  blue:new THREE.MeshStandardMaterial({color:0x167fb5,transparent:true,opacity:0.38,roughness:0.22,depthWrite:false,side:THREE.DoubleSide}),
  shell:new THREE.MeshStandardMaterial({color:0x5b7c91,transparent:true,opacity:0.26,metalness:0.65,roughness:0.3,side:THREE.DoubleSide,depthWrite:false}),
  green:new THREE.MeshStandardMaterial({color:0x2cbbad,transparent:true,opacity:0.22,roughness:0.3,depthWrite:false,side:THREE.DoubleSide}),
};
const info = {
  shell:['压力边界 / 蒸发空间','外壳为示意几何。系统压力 P、物性与质量能量守恒直接来自所选原始 SG 模型，不使用旧合成演示方程替换。保持原脚本约束与求解方式。'],
  water:['蒸发空间 / 混合物占据高度','三维占据高度按 (V_wd + V_sd) / A_d 映射。V_sd 为液面下蒸汽体积。仪表指示水位 L 由式 (2-34) 压力平衡给出，不直接用此几何高度代替。'],
  tubes:['一次侧 U 形管束 / 换热','原 SG 模型采用一次侧平均温度边界。SG_tem 直接复用其对数平均温差替换函数，其他实验保留各自换热公式。管束颜色和流线仅示意，非局部温度场。'],
  riser:['上升空间 / 两相自然循环','状态 αr 是出口质量含汽率；体积含汽率由质量比例及两相密度换算。沿高度示意遵循 αm(z)=αr·z/H；气泡不是逐泡追踪结果。自然循环流量由压头与阻力关系计算。'],
  downcomer:['下降通道 / 饱和水回流','下降空间在当前模型中假设不含蒸汽。流向粒子用于表达自然循环，粒子速度经过视觉缩放，不能作为局部流速测量。'],
  steam:['蒸汽出口 / 边界流量 qs','蒸汽流量 qs 是模型边界输入。网页操作改变下一步的边界流量，压力与水位由四状态方程重新积分获得，而非预设动画。'],
};
function mesh(geometry,material,position,name) {
  const object = new THREE.Mesh(geometry,material); object.position.set(...position); assembly.add(object);
  if (name) { object.userData.part=name; hitTargets.push(object); }
  return object;
}
function pipe(points,radius,material,name) {
  const curve = new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
  return mesh(new THREE.TubeGeometry(curve,50,radius,8,false),material,[0,0,0],name);
}
const shell = mesh(new THREE.CylinderGeometry(1.22,1.22,6.5,80,1,true,Math.PI*.58,Math.PI*1.30),materials.shell,[0,3.1,0],'shell');
const cap = mesh(new THREE.SphereGeometry(1.22,48,24,0,Math.PI*2,0,Math.PI/2),materials.shell,[0,6.35,0],'shell'); cap.scale.y=.65;
const fullShellGeometry = new THREE.CylinderGeometry(1.22,1.22,6.5,80,1,true);
const cutShellGeometry = shell.geometry;
for (const y of [-.15,0.12,4.7,6.25]) {
  const ring = mesh(new THREE.TorusGeometry(1.24,.035,8,80),materials.metal,[0,y,0],'shell'); ring.rotation.x=Math.PI/2;
}
const base = mesh(new THREE.CylinderGeometry(1.23,1.23,.3,64),materials.metal,[0,-.15,0],'tubes');
mesh(new THREE.CylinderGeometry(.95,.95,.13,48),materials.metal,[0,.15,0],'tubes');
const water = mesh(new THREE.CylinderGeometry(1.12,1.12,1,64),materials.blue,[0,2,0],'water');
const surface = mesh(new THREE.CircleGeometry(1.12,64),new THREE.MeshBasicMaterial({color:0x64d7e3,transparent:true,opacity:.25,side:THREE.DoubleSide,depthWrite:false}),[0,4,0],'water'); surface.rotation.x=-Math.PI/2;
const riser = mesh(new THREE.CylinderGeometry(.88,.88,4.6,48,1,true),materials.green,[0,2.55,0],'riser');
for (let j=0;j<7;j++) {
  const z=(j-3)*.19;
  for (let i=0;i<3;i++) {
    const width=.23+i*.20; const height=3.65-Math.abs(j-3)*.13-i*.10;
    pipe([[-width,.25,z],[-width,height,z],[-width*.7,height+.35,z],[0,height+.5,z],[width*.7,height+.35,z],[width,height,z],[width,.25,z]],.028,materials.copper,'tubes');
  }
}
for (const x of [-.62,0,.62]) {
  mesh(new THREE.CylinderGeometry(.18,.24,.48,16),materials.metal,[x,5.25,0],'steam');
  const ring=mesh(new THREE.TorusGeometry(.23,.04,8,24),materials.metal,[x,5.48,0],'steam'); ring.rotation.x=Math.PI/2;
}
pipe([[0,6.4,0],[0,7,0],[.7,7.2,0],[1.7,7.2,0]],.16,materials.metal,'steam');
pipe([[-1.1,3.9,0],[-1.8,3.9,0],[-2.1,3.6,0]],.11,materials.metal,'downcomer');
pipe([[-.5,-.3,0],[-.5,-.7,0],[-1.7,-.7,0]],.16,materials.copper,'tubes');
pipe([[.5,-.3,0],[.5,-.95,0],[1.7,-.95,0]],.16,materials.copper,'tubes');
for(const x of [-.7,.7]) mesh(new THREE.CylinderGeometry(.09,.13,.65,12),materials.metal,[x,-.65,.65]);
const grid = new THREE.GridHelper(18,36,0x294355,0x162b3b); grid.position.y=-1.1; scene.add(grid);
const halo = new THREE.Mesh(new THREE.RingGeometry(1.65,1.67,90),new THREE.MeshBasicMaterial({color:0x2b726e,side:THREE.DoubleSide,transparent:true,opacity:.5})); halo.rotation.x=-Math.PI/2; halo.position.y=-1.08;scene.add(halo);
// Instanced bubbles: count/color reflect void fraction, motion is illustrative.
const bubbleCount=200;
const bubbles = new THREE.InstancedMesh(new THREE.SphereGeometry(1,7,5),new THREE.MeshBasicMaterial({color:0x8ff2e4,transparent:true,opacity:.5,depthWrite:false}),bubbleCount);
assembly.add(bubbles);
const dummy = new THREE.Object3D();
const bubbleSeeds=Array.from({length:bubbleCount},(_,i)=>({angle:i*2.39996,r:.12+((i*17)%79)/110,phase:((i*37)%199)/199,size:.017+((i*11)%23)/900}));
const arrows=[];
for(let i=0;i<18;i++){
  const outer=i>=9, theta=(i%9)/9*Math.PI*2;
  const arrow=new THREE.Mesh(new THREE.ConeGeometry(.055,.18,7),new THREE.MeshBasicMaterial({color:outer?0x50a9e5:0x4be4c5,transparent:true,opacity:.8}));
  arrow.userData={outer,theta,phase:(i%9)/9}; if(outer) arrow.rotation.z=Math.PI;assembly.add(arrow);arrows.push(arrow);
}
let azimuth=.65,elevation=.1,distance=14.8,drag=null,moved=0;
function cameraUpdate(){camera.position.set(distance*Math.sin(azimuth)*Math.cos(elevation),3+distance*Math.sin(elevation),distance*Math.cos(azimuth)*Math.cos(elevation));camera.lookAt(0,3,0);}
cameraUpdate();
canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};moved=0;canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;moved+=Math.abs(dx)+Math.abs(dy);azimuth-=dx*.007;elevation=Math.max(-.45,Math.min(.65,elevation+dy*.004));drag={x:e.clientX,y:e.clientY};cameraUpdate();});
canvas.addEventListener('pointerup',e=>{
  drag=null;if(moved>5)return;
  const rect=canvas.getBoundingClientRect();const ray=new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),camera);
  const hits=ray.intersectObjects(hitTargets).filter(h=>h.object!==shell&&h.object!==cap);
  const hit=hits[0] || ray.intersectObject(shell)[0];
  if(hit){const [title,description]=info[hit.object.userData.part];$('part-title').textContent=title;$('part-description').textContent=description;}
});
canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(9,Math.min(24,distance+e.deltaY*.012));cameraUpdate();},{passive:false});
$('home').onclick=()=>{azimuth=.65;elevation=.1;distance=14.8;cameraUpdate();};
let cutaway=true;
$('cutaway').onclick=()=>{cutaway=!cutaway;shell.geometry=cutaway?cutShellGeometry:fullShellGeometry;materials.shell.opacity=cutaway?.26:.65;$('cutaway').textContent='剖视 '+(cutaway?'ON':'OFF');$('cutaway').classList.toggle('active',cutaway);};
function resize(){const rect=canvas.getBoundingClientRect();renderer.setSize(rect.width,rect.height,false);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();if(current)drawCharts(replaying?Number($('replay').value):history.length-1);}
new ResizeObserver(resize).observe($('viewport'));
let displayed;
function renderSnapshot(s,index=history.length-1){
  if(!s)return;displayed=s;const d=s.derived;
  const openProfile=['SG_qs','SG_level','SG_tem'].includes(s.provenance.profile);
  document.querySelectorAll('[data-scenario]').forEach(button=>{
    button.disabled=!openProfile || button.dataset.scenario==='level';
    button.title=button.dataset.scenario==='level'?'开环水位为输出，请使用 PID/NMPC 水位设定值实验':(!openProfile?'此按钮仅用于三个开环模型':'');
  });
  if(!replaying && $('mode').value==='baseline'){
    controls.forEach(id=>$(id).value=s.inputs[id]);updateOutputs();
  }
  $('clock').textContent=s.time.toFixed(1);$('pressure').textContent=s.state.P.toFixed(6);$('level').textContent=d.level.toFixed(4);
  $('volume').textContent=s.state.V_wt.toFixed(3);$('vapor').textContent=s.state.V_sd.toFixed(3);
  $('quality').textContent=(s.state.alpha_r*100).toFixed(2)+' %';$('void').textContent=(d.alpha_bar_v*100).toFixed(2)+' %';
  $('thermal').textContent=d.temperature.toFixed(1)+' °C / '+(d.heat_kw/1000).toFixed(2)+' MW';
  $('circulation').textContent=d.circulation.toFixed(2)+' kg/s';$('mixture').textContent=d.mixture_height.toFixed(3)+' m';
  $('baseline-info').textContent=`${s.provenance.profile}.py · ${s.provenance.model} · ${s.provenance.mode==='original_script_baseline'?'原脚本基准':'手动干预分支'} · ΔL=${d.delta_level.toFixed(5)} m · 网页 ${s.time}s / 模型 ${s.model_time}s`;
  $('mass-residual').textContent=d.mass_equation_residual.toExponential(2);$('energy-residual').textContent=d.energy_equation_residual.toExponential(2);
  // Schematic occupancy scale only; not CAD and not the Level output.
  const height=Math.max(.02,Math.min(5.0,d.mixture_height*.5));water.scale.y=height;water.position.y=.25+height/2;surface.position.y=.25+height;
  materials.green.opacity=.1+.25*d.alpha_bar_v;
  drawCharts(index);
}
function chart(id,rows,series){
  const el=$(id),rect=el.getBoundingClientRect(),ratio=Math.min(devicePixelRatio,2);el.width=rect.width*ratio;el.height=175*ratio;
  const ctx=el.getContext('2d');ctx.scale(ratio,ratio);const w=rect.width,h=175,p={l:49,r:12,t:12,b:27};
  if(!rows.length)return;
  const values=rows.flatMap(s=>series.map(line=>line.get(s)));let low=Math.min(...values),high=Math.max(...values);
  const pad=Math.max((high-low)*.18,Math.abs(high)*.00002,.0001);low-=pad;high+=pad;
  const start=rows[0].time,end=Math.max(start+1,rows.at(-1).time);
  const x=t=>p.l+(t-start)/(end-start)*(w-p.l-p.r),y=v=>h-p.b-(v-low)/(high-low)*(h-p.t-p.b);
  ctx.font='9px Segoe UI';
  for(let i=0;i<4;i++){const value=low+(high-low)*i/3;ctx.strokeStyle='#243542';ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(p.l,y(value));ctx.lineTo(w-p.r,y(value));ctx.stroke();ctx.fillStyle='#748f9f';ctx.textAlign='right';ctx.fillText(value.toFixed(high-low<.05?4:2),p.l-7,y(value)+3);}
  ctx.textAlign='center';for(let i=0;i<3;i++){const t=start+(end-start)*i/2;ctx.fillText(t.toFixed(1)+'s',x(t),h-8);}
  for(const line of series){ctx.strokeStyle=line.color;ctx.lineWidth=1.8;ctx.setLineDash(line.dash?[4,4]:[]);ctx.beginPath();rows.forEach((s,i)=>{if(i===0)ctx.moveTo(x(s.time),y(line.get(s)));else ctx.lineTo(x(s.time),y(line.get(s)));});ctx.stroke();if(rows.length===1){ctx.fillStyle=line.color;ctx.fillRect(x(rows[0].time)-2,y(line.get(rows[0]))-2,4,4);}}
  ctx.setLineDash([]);ctx.textAlign='left';series.forEach((line,i)=>{ctx.fillStyle=line.color;ctx.fillText(line.name,p.l+i*110,10);});
}
function drawCharts(index){const rows=history.slice(Math.max(0,index-599),index+1);const relativeLevel=['SG_qs','SG_level','SG_tem'].includes(current?.provenance.profile);chart('level-chart',rows,relativeLevel?[{name:'ΔL / m（第99s归零）',color:'#e8b94d',get:s=>s.derived.delta_level}]:[{name:'指示水位',color:'#e8b94d',get:s=>s.derived.level},{name:'设定值',color:'#adbbca',dash:true,get:s=>s.controls.setpoint}]);chart('pressure-chart',rows,[{name:'系统压力',color:'#69a8ee',get:s=>s.state.P}]);chart('flow-chart',rows,[{name:'给水',color:'#e8b94d',get:s=>s.inputs.q_f},{name:'蒸汽',color:'#e87060',get:s=>s.inputs.q_s}]);}
let visualTime=0,previous=performance.now();
function animate(now){
  requestAnimationFrame(animate);const elapsed=Math.min((now-previous)/1000,.1);previous=now;
  if(running)visualTime+=elapsed*Number($('speed').value);
  if(displayed){
    const fraction=displayed.derived.alpha_bar_v;
    bubbles.count=Math.round(40+160*fraction);
    bubbleSeeds.forEach((s,i)=>{const t=(s.phase+visualTime*.13)%1;dummy.position.set(Math.cos(s.angle)*s.r,.4+t*4.25,Math.sin(s.angle)*s.r);dummy.scale.setScalar(s.size*(.6+t));dummy.updateMatrix();bubbles.setMatrixAt(i,dummy.matrix);});bubbles.instanceMatrix.needsUpdate=true;
    const flowScale=displayed.derived.circulation/214;
    arrows.forEach(a=>{a.visible=$('flows').checked;const data=a.userData;let f=(data.phase+visualTime*.13*flowScale)%1;if(data.outer)f=1-f;const r=data.outer?1.04:.55;a.position.set(Math.cos(data.theta)*r,.4+f*4.1,Math.sin(data.theta)*r);});
  }
  renderer.render(scene,camera);
  if(running&&!busy&&now>=nextTick){nextTick=now+1000/Number($('speed').value);step();}
}
requestAnimationFrame(animate);
try {
  const result=await api('session');session=result.session;current=result.snapshot;history=[current];renderSnapshot(current);
  $('profile').value=current.provenance.profile;
  controls.forEach(id=>$(id).value=current.controls[id]); updateOutputs();
  $('run').disabled=false;$('step').disabled=false;$('reset').disabled=false;setRunning(false);
} catch(error){$('status').textContent='● 模型连接失败';showError('无法连接 Python 模型：'+error.message);}
