/* ═══════════ APP SHELL ═══════════
   侧边栏导航、加载状态、全局配置 */
const PAL = ['#58a6ff','#f778ba','#3fb950','#d29922','#a371f7','#39c5cf','#f0883e','#e3b341','#8b949e','#7ee787','#79c0ff','#ffa657'];
const COLORS = { positive:'#3fb950', negative:'#f85149', neutral:'#d29922' };
const baseOpt = () => ({backgroundColor:'transparent',textStyle:{color:'#9198a1',fontFamily:"-apple-system,'PingFang SC','Microsoft YaHei',sans-serif"},grid:{top:40,right:20,bottom:40,left:56,containLabel:true}});

const D = (typeof DASHBOARD_DATA !== 'undefined') ? DASHBOARD_DATA : null;
if(!D){document.querySelector('.page-container').innerHTML='<div style="text-align:center;margin-top:30vh;color:#58a6ff">请先运行 python generate_stats.py</div>'}

const chartInstances = {};

/* ═══════ HIDE LOADING + SIDEBAR INFO ═══════ */
window.addEventListener('load',()=>{
  const lo=document.getElementById('loadingOverlay');
  if(lo){lo.classList.add('hidden');setTimeout(()=>lo.remove(),400)}
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
setTimeout(()=>{const lo=document.getElementById('loadingOverlay');if(lo){lo.classList.add('hidden');setTimeout(()=>lo.remove(),400)}},3000);

/* ═══════ NAVIGATION ═══════ */
const navItems=document.querySelectorAll('.nav-item');
const pages=document.querySelectorAll('.page');

navItems.forEach(item=>{
  item.addEventListener('click',()=>{
    const target=item.dataset.page;
    navItems.forEach(n=>n.classList.remove('active'));
    item.classList.add('active');
    pages.forEach(p=>{p.classList.remove('active');if(p.id==='page-'+target)p.classList.add('active')});
    setTimeout(()=>{Object.values(chartInstances).forEach(c=>{if(c&&!c.isDisposed())c.resize()})},60);
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
function animNum(el,target,dur=1000){
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
