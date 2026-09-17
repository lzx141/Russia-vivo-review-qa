/* Application shell, navigation and shared chart tokens. */
const PAL=['#4fd1ff','#7c6cff','#39d98a','#f5b942','#a47cff','#3bb8d4','#ff8a65','#f6cf65','#8fa1b8','#62e6aa','#8fdfff','#ff9a72'];
const COLORS={positive:'#39d98a',negative:'#ff6b7a',neutral:'#f5b942'};
const baseOpt=()=>({backgroundColor:'transparent',textStyle:{color:'#9aa8bd',fontFamily:"Inter,'PingFang SC','Microsoft YaHei',sans-serif"},animationDuration:700,animationEasing:'cubicOut',grid:{top:42,right:20,bottom:38,left:48,containLabel:true}});
const D=typeof DASHBOARD_DATA!=='undefined'?DASHBOARD_DATA:null;
const chartInstances={};
const ROUTES=['overview','sentiment','products','geography','timeline','qa','diagnosis','governance'];
const PAGE_TITLES={overview:'市场总览',sentiment:'情感洞察',products:'产品分析',geography:'地域分析',timeline:'时间趋势',qa:'问答洞察',diagnosis:'差评诊断',governance:'数据治理'};

function byId(id){return document.getElementById(id)}
function setText(id,value){const el=byId(id);if(el)el.textContent=value||'—'}
function setDrawer(open){document.body.classList.toggle('nav-open',Boolean(open));byId('mobileMenu')?.setAttribute('aria-expanded',String(Boolean(open)))}
function initializePage(route){const names={overview:'initOverview',sentiment:'initSentiment',products:'initProducts',geography:'initGeography',timeline:'initTimeline',qa:'initQA',diagnosis:'initDiagnosis',governance:'initGovernance'};const fn=globalThis[names[route]];if(typeof fn==='function')fn()}
function navigateTo(route,{updateHash=true}={}){
  const target=DashboardCore.normalizeRoute(`#${route}`,ROUTES);
  document.querySelectorAll('.nav-item').forEach(item=>{const active=item.dataset.page===target;item.classList.toggle('active',active);if(active)item.setAttribute('aria-current','page');else item.removeAttribute('aria-current')});
  document.querySelectorAll('.page').forEach(page=>page.classList.toggle('active',page.id===`page-${target}`));
  setText('currentPageTitle',PAGE_TITLES[target]);setDrawer(false);initializePage(target);
  if(updateHash&&location.hash!==`#${target}`)history.pushState(null,'',`#${target}`);
  requestAnimationFrame(()=>Object.values(chartInstances).forEach(chart=>{if(chart&&!chart.isDisposed())chart.resize()}));return target;
}
function hideLoading(){const el=byId('loadingOverlay');if(!el)return;el.classList.add('hidden');setTimeout(()=>el.remove(),360)}
function renderFatalDataState(){const main=byId('mainContent');if(main)main.innerHTML='<article class="card empty-state"><div><div class="empty-icon">!</div><h3>数据文件尚未生成</h3><p>请先生成 dashboard_data.js，再重新加载页面。</p><code class="command">python src/dashboard/generate_stats.py</code></div></article>'}
function hydrateMetadata(){if(!D)return;const kpi=D.kpi||{},meta=D.meta||{};const range=kpi.date_range_start&&kpi.date_range_end?`${kpi.date_range_start} — ${kpi.date_range_end}`:'—',updated=meta.generated_at||'—';['dateRange','topDateRange'].forEach(id=>setText(id,range));['updateTime','topUpdateTime'].forEach(id=>setText(id,updated));setText('overviewPlatforms',kpi.platforms?`${kpi.platforms} 个平台`:'—');setText('overviewPeriod',range)}
function animNum(el,target,duration=900){const number=Number(target);if(!Number.isFinite(number)){el.textContent='—';return}const decimals=String(target).includes('.')?1:0;if(matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=number.toLocaleString('zh-CN',{maximumFractionDigits:decimals});return}const start=performance.now();function update(now){const p=Math.min((now-start)/duration,1),value=number*(1-Math.pow(1-p,3));el.textContent=value.toLocaleString('zh-CN',{minimumFractionDigits:decimals,maximumFractionDigits:decimals});if(p<1)requestAnimationFrame(update)}requestAnimationFrame(update)}
function closeModal(){byId('modalOverlay')?.classList.remove('show')}
function bindEvents(){
  document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('click',()=>navigateTo(item.dataset.page)));
  byId('mobileMenu')?.addEventListener('click',()=>setDrawer(!document.body.classList.contains('nav-open')));byId('navBackdrop')?.addEventListener('click',()=>setDrawer(false));byId('modalClose')?.addEventListener('click',closeModal);byId('modalOverlay')?.addEventListener('click',event=>{if(event.target===byId('modalOverlay'))closeModal()});
  document.querySelectorAll('[data-sentiment-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-sentiment-filter]').forEach(item=>item.classList.remove('active'));button.classList.add('active');if(typeof applySentimentFilter==='function')applySentimentFilter(button.dataset.sentimentFilter)}));
  addEventListener('hashchange',()=>navigateTo(DashboardCore.normalizeRoute(location.hash,ROUTES),{updateHash:false}));addEventListener('resize',()=>Object.values(chartInstances).forEach(chart=>{if(chart&&!chart.isDisposed())chart.resize()}));document.addEventListener('keydown',event=>{if(event.key==='Escape'){setDrawer(false);closeModal()}});
}
document.addEventListener('DOMContentLoaded',()=>{bindEvents();if(!D){renderFatalDataState();hideLoading();return}hydrateMetadata();navigateTo(DashboardCore.normalizeRoute(location.hash,ROUTES),{updateHash:false});hideLoading()});
setTimeout(hideLoading,3000);
globalThis.DashboardApp={navigateTo,setDrawer,closeModal};
