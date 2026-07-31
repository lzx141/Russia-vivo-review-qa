/* ═══════════ APP SHELL ═══════════
   导航、时钟、粒子背景、全局状态 */
const PAL = ['#c4a0e0','#e0a8c8','#a0a8e0','#d0a0b8','#b8a0d0','#c890b0','#9898d0','#c080b0','#a070a0','#d0b0c0','#b0c0d0','#c0b0a0'];
const COLORS = { positive:'#a8d8a0', negative:'#e0a0a0', neutral:'#a8a0e0' };
const baseOpt = () => ({backgroundColor:'transparent',textStyle:{color:'rgba(210,190,230,0.7)',fontFamily:"'PingFang SC','Microsoft YaHei',sans-serif"},grid:{top:35,right:16,bottom:35,left:50,containLabel:true}});

const D = (typeof DASHBOARD_DATA !== 'undefined') ? DASHBOARD_DATA : null;
if(!D){document.querySelector('.page-container').innerHTML='<h2 style="text-align:center;margin-top:40vh;color:var(--accent)">请先运行 python generate_stats.py</h2>'}

/* ═══════ HIDE LOADING + FOOTER INFO ═══════ */
window.addEventListener('load',()=>{
  const lo=document.getElementById('loadingOverlay');
  if(lo){lo.classList.add('hidden');setTimeout(()=>lo.remove(),600)}
  if(D){
    const kpi=D.kpi||{};
    if(kpi.date_range_start&&kpi.date_range_end){
      const dr=document.getElementById('dateRange');
      if(dr)dr.textContent=`${kpi.date_range_start} ~ ${kpi.date_range_end}`;
    }
    const meta=D.meta||{};
    if(meta.generated_at){
      const ut=document.getElementById('updateTime');
      if(ut)ut.textContent=meta.generated_at;
    }
  }
});
/* 兜底：若资源在 load 前已就绪，立即隐藏 */
setTimeout(()=>{const lo=document.getElementById('loadingOverlay');if(lo){lo.classList.add('hidden');setTimeout(()=>lo.remove(),600)}},3000);

const chartInstances = {};

/* ═══════ PARTICLE BACKGROUND ═══════ */
(function(){
  const c=document.getElementById('particles'),ctx=c.getContext('2d');
  let w,h,pts=[];
  function resize(){w=c.width=window.innerWidth;h=c.height=window.innerHeight;pts=[];for(let i=0;i<60;i++)pts.push({x:Math.random()*w,y:Math.random()*h,r:Math.random()*1.5+.5,dx:(Math.random()-.5)*.3,dy:(Math.random()-.5)*.3,o:Math.random()*.3+.1})}
  function draw(){ctx.clearRect(0,0,w,h);pts.forEach(p=>{p.x+=p.dx;p.y+=p.dy;if(p.x<0)p.x=w;if(p.x>w)p.x=0;if(p.y<0)p.y=h;if(p.y>h)p.y=0;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(180,140,220,${p.o})`;ctx.fill()});
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){const dx=pts[i].x-pts[j].x,dy=pts[i].y-pts[j].y,dist=Math.sqrt(dx*dx+dy*dy);if(dist<120){ctx.beginPath();ctx.moveTo(pts[i].x,pts[i].y);ctx.lineTo(pts[j].x,pts[j].y);ctx.strokeStyle=`rgba(180,140,220,${0.05*(1-dist/120)})`;ctx.stroke()}}
  requestAnimationFrame(draw)}
  resize();draw();window.addEventListener('resize',resize);
})();

/* ═══════ CLOCK ═══════ */
function updateClock(){document.getElementById('clock').textContent=new Date().toLocaleString('zh-CN',{hour12:false})}
setInterval(updateClock,1000);updateClock();

/* ═══════ NAVIGATION ═══════ */
const navItems=document.querySelectorAll('.nav-item');
const pages=document.querySelectorAll('.page');

navItems.forEach(item=>{
  item.addEventListener('click',()=>{
    const target=item.dataset.page;
    navItems.forEach(n=>n.classList.remove('active'));
    item.classList.add('active');
    pages.forEach(p=>{p.classList.remove('active');if(p.id==='page-'+target)p.classList.add('active')});
    setTimeout(()=>{Object.values(chartInstances).forEach(c=>{if(c&&!c.isDisposed())c.resize()})},50);
    if(target==='sentiment')initSentiment();
    if(target==='products')initProducts();
    if(target==='geography')initGeography();
    if(target==='timeline')initTimeline();
    if(target==='qa')initQA();
    if(target==='diagnosis')initDiagnosis();
  });
});

/* ═══════ RESIZE ALL ═══════ */
window.addEventListener('resize',()=>{
  Object.values(chartInstances).forEach(c=>{if(c&&!c.isDisposed())c.resize()});
});

/* ═══════ ANIMATE NUMBER ═══════ */
function animNum(el,target,dur=1200){
  const isF=String(target).includes('.');
  const start=performance.now();
  (function u(now){
    const p=Math.min((now-start)/dur,1),e=1-Math.pow(1-p,3);
    const v=target*e;
    el.textContent=isF?v.toFixed(1):Math.floor(v).toLocaleString();
    if(p<1)requestAnimationFrame(u);
  })(performance.now());
}

/* ═══════ PRODUCT MODAL ═══════ */
document.getElementById('modalClose').addEventListener('click',()=>document.getElementById('modalOverlay').classList.remove('show'));
document.getElementById('modalOverlay').addEventListener('click',e=>{if(e.target===document.getElementById('modalOverlay'))document.getElementById('modalOverlay').classList.remove('show')});

/* ═══════ SENTIMENT FILTER ═══════ */
document.querySelectorAll('[data-sentiment-filter]').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('[data-sentiment-filter]').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    applySentimentFilter(btn.dataset.sentimentFilter);
  });
});
