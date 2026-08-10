/* ═══════════ CHART RENDERER ═══════════
   各页面图表初始化与更新 */

/* ── helper ── */
function escapeHtml(str){return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;')}
function initChart(id){
  if(chartInstances[id])return chartInstances[id];
  const el=document.getElementById(id);
  if(!el)return null;
  const c=echarts.init(el);
  chartInstances[id]=c;
  return c;
}

function disposeChart(id){
  if(chartInstances[id]){chartInstances[id].dispose();delete chartInstances[id]}
}

/* ═══════════════════════════════════
   PAGE: OVERVIEW
   ═══════════════════════════════════ */
function initOverview(){
  if(!D)return;

  // KPIs
  const kpis=[
    {label:'数据总量',value:D.kpi.total_records},
    {label:'用户评论',value:D.kpi.total_reviews},
    {label:'用户问答',value:D.kpi.total_qa},
    {label:'产品数',value:D.kpi.product_count},
    {label:'用户数',value:D.kpi.user_count},
    {label:'平均评分',value:D.kpi.avg_rating},
    {label:'好评率',value:D.kpi.positive_rate,suffix:'%'},
    {label:'五星率',value:D.kpi.five_star_rate,suffix:'%'},
  ];
  const strip=document.getElementById('kpiStrip');
  kpis.forEach(k=>{
    const d=document.createElement('div');d.className='kpi';
    d.innerHTML=`<div class="lbl">${k.label}</div><div class="val" data-target="${k.value}">0</div>`;
    strip.appendChild(d);
    setTimeout(()=>{
      const vel=d.querySelector('.val');
      animNum(vel,k.value);
      if(k.suffix)setTimeout(()=>{vel.textContent+=`<span class="unit">%</span>`},1100);
    },80);
  });

  // Trend
  if(D.monthly_trend){
    const cTrend=initChart('ovTrend');
    cTrend.setOption({...baseOpt(),tooltip:{trigger:'axis'},legend:{data:['评论','问答','平均评分'],textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},top:0},
      xAxis:{type:'category',data:D.monthly_trend.months,axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}},axisLabel:{fontSize:10,rotate:30}},
      yAxis:[{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},{type:'value',min:4,max:5,splitLine:{show:false}}],
      series:[
        {name:'评论',type:'bar',data:D.monthly_trend.reviews,itemStyle:{color:PAL[0],borderRadius:[3,3,0,0]},barMaxWidth:18},
        {name:'问答',type:'bar',data:D.monthly_trend.qa,itemStyle:{color:PAL[1],borderRadius:[3,3,0,0]},barMaxWidth:18},
        {name:'平均评分',type:'line',yAxisIndex:1,data:D.monthly_trend.avg_rating,smooth:true,lineStyle:{color:PAL[2],width:2},symbol:'circle',symbolSize:5,itemStyle:{color:PAL[2]},
         areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(163,113,247,0.12)'},{offset:1,color:'transparent'}]}}},
      ]});
  }

  // Rating
  if(D.rating_dist){
    const cRating=initChart('ovRating');
    cRating.setOption({...baseOpt(),tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'},
      series:[{type:'pie',roseType:'area',radius:['18%','72%'],center:['50%','55%'],
        itemStyle:{borderRadius:6,borderColor:'rgba(13,17,23,0.8)',borderWidth:2},
        label:{color:'rgba(230,237,243,0.7)',fontSize:11},
        data:D.rating_dist.labels.map((l,i)=>({name:l,value:D.rating_dist.values[i],itemStyle:{color:PAL[i%PAL.length]}})),
        animationType:'scale',animationEasing:'elasticOut'}]});
  }

  // Product Rank
  if(D.product_ranking){
    const cPR=initChart('ovProductRank');
    const top12=D.product_ranking.slice(0,12);
    cPR.setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:80,right:10,top:10,bottom:20},
      xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}},axisLabel:{fontSize:9}},
      yAxis:{type:'category',data:top12.map(p=>p.name).reverse(),axisLabel:{fontSize:10},axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}}},
      series:[{type:'bar',data:top12.map(p=>p.total).reverse(),
        itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:'rgba(88,166,255,0.2)'},{offset:1,color:PAL[0]}]},borderRadius:[0,4,4,0]},
        barMaxWidth:14,label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)'}}]});
  }

  // Wordcloud
  if(D.wordcloud_positive){
    initChart('ovWordcloud').setOption({tooltip:{show:true},series:[{type:'wordCloud',shape:'circle',sizeRange:[12,46],rotationRange:[-25,25],rotationStep:15,gridSize:5,
      textStyle:{fontFamily:"'PingFang SC','Microsoft YaHei'",color:()=>PAL[Math.floor(Math.random()*PAL.length)]},
      data:D.wordcloud_positive.slice(0,55)}]});
  }

  // Platform
  if(D.platform_comparison){
    const plats=Object.keys(D.platform_comparison);
    initChart('ovPlatform').setOption({...baseOpt(),tooltip:{trigger:'axis'},legend:{data:['评论','问答'],textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},top:0},
      xAxis:{type:'category',data:plats,axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}}},
      yAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      series:[
        {name:'评论',type:'bar',data:plats.map(p=>D.platform_comparison[p].reviews),itemStyle:{color:PAL[0],borderRadius:[3,3,0,0]},barMaxWidth:28},
        {name:'问答',type:'bar',data:plats.map(p=>D.platform_comparison[p].qa),itemStyle:{color:PAL[1],borderRadius:[3,3,0,0]},barMaxWidth:28}]});
  }
}

/* ═══════════════════════════════════
   PAGE: SENTIMENT
   ═══════════════════════════════════ */
let sentimentInited=false;
let sentimentFilter='all';

function applySentimentFilter(filter){
  sentimentFilter=filter;
  if(!D||!D.sentiment)return;
  updateSentimentCharts();
}

function updateSentimentCharts(){
  if(!D||!D.sentiment)return;
  const sd=D.sentiment.distribution;
  const total=(sd.positive||0)+(sd.neutral||0)+(sd.negative||0);

  // Pie
  let pieData=[
    {name:'正面 ✓',value:sd.positive||0,itemStyle:{color:COLORS.positive}},
    {name:'中性 ○',value:sd.neutral||0,itemStyle:{color:COLORS.neutral}},
    {name:'负面 ✗',value:sd.negative||0,itemStyle:{color:COLORS.negative}},
  ];
  if(sentimentFilter!=='all'){pieData=pieData.filter(d=>d.name.includes(sentimentFilter==='positive'?'正面':sentimentFilter==='negative'?'负面':'中性'))}

  const cPie=initChart('sentPie');
  if(cPie){
    cPie.setOption({...baseOpt(),tooltip:{trigger:'item'},
      series:[{type:'pie',radius:['40%','70%'],center:['50%','55%'],
        itemStyle:{borderRadius:6,borderColor:'rgba(13,17,23,0.8)',borderWidth:2},
        label:{color:'rgba(230,237,243,0.7)',fontSize:11,formatter:'{b}\n{c} ({d}%)'},
        data:pieData}]});
  }
}

function initSentiment(){
  if(sentimentInited||!D)return;
  sentimentInited=true;
  updateSentimentCharts();

  const as=D.sentiment.aspect_sentiment;
  const aKeys=Object.keys(as).slice(0,8);
  if(aKeys.length>0){
    const maxV=Math.max(1,...aKeys.map(k=>(as[k].positive||0)+(as[k].neutral||0)+(as[k].negative||0)));
    initChart('sentRadar').setOption({...baseOpt(),tooltip:{},
      radar:{indicator:aKeys.map(k=>({name:k,max:maxV})),axisName:{color:'rgba(230,237,243,0.7)',fontSize:10},
        splitArea:{areaStyle:{color:['rgba(110,118,129,0.03)','rgba(110,118,129,0.06)']}},splitLine:{lineStyle:{color:PAL[0]+'15'}},axisLine:{lineStyle:{color:PAL[0]+'15'}}},
      legend:{data:['正面','负面'],textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},top:0},
      series:[{type:'radar',data:[
        {name:'正面',value:aKeys.map(k=>as[k].positive||0),lineStyle:{color:COLORS.positive},itemStyle:{color:COLORS.positive},areaStyle:{color:'rgba(63,185,80,0.12)'}},
        {name:'负面',value:aKeys.map(k=>as[k].negative||0),lineStyle:{color:COLORS.negative},itemStyle:{color:COLORS.negative},areaStyle:{color:'rgba(248,81,73,0.12)'}},
      ]}]});
  }

  // Positive wordcloud
  if(D.wordcloud_positive){
    initChart('sentPosCloud').setOption({tooltip:{show:true},series:[{type:'wordCloud',shape:'circle',sizeRange:[12,44],rotationRange:[-25,25],gridSize:5,
      textStyle:{fontFamily:"'PingFang SC','Microsoft YaHei'",color:()=>['#3fb950','#3fb950','#3fb950','#3fb950','#3fb950'][Math.floor(Math.random()*5)]},
      data:D.wordcloud_positive.slice(0,50)}]});
  }

  // Negative wordcloud
  if(D.wordcloud_negative){
    initChart('sentNegCloud').setOption({tooltip:{show:true},series:[{type:'wordCloud',shape:'diamond',sizeRange:[12,40],rotationRange:[-20,20],gridSize:5,
      textStyle:{fontFamily:"'PingFang SC','Microsoft YaHei'",color:()=>['#f778ba0a0','#f85149','#f0883e','#f0883e','#f85149'][Math.floor(Math.random()*5)]},
      data:D.wordcloud_negative.slice(0,40)}]});
  }

  // Aspect bar
  const aspData=D.sentiment.aspect_frequency;
  if(aspData&&aspData.length>0){
    initChart('sentAspectBar').setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:70,right:10,top:5,bottom:20},
      xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      yAxis:{type:'category',data:aspData.map(d=>d.name).reverse(),axisLabel:{fontSize:10},axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}}},
      series:[{type:'bar',data:aspData.map(d=>d.value).reverse(),
        itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:'rgba(88,166,255,0.15)'},{offset:1,color:PAL[0]}]},borderRadius:[0,3,3,0]},
        barMaxWidth:14,label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)'}}]});
  }
}

/* ═══════════════════════════════════
   PAGE: PRODUCTS
   ═══════════════════════════════════ */
let productsInited=false;
function initProducts(){
  if(productsInited||!D)return;productsInited=true;
  const grid=document.getElementById('productGrid');
  const select=document.getElementById('productSelect');
  const summaries=D.product_summaries||{};

  D.product_ranking.forEach((p,i)=>{
    const opt=document.createElement('option');
    opt.value=p.name;opt.textContent=p.name;
    select.appendChild(opt);

    const card=document.createElement('div');card.className='product-card';
    const summary=summaries[p.name]?summaries[p.name].summary:'';
    const cleanSummary=summary.replace(/^\d+\.\s*/gm,'').replace(/\*\*/g,'').substring(0,120);
    card.innerHTML=`
      <div class="pname">${escapeHtml(p.name)}</div>
      <div class="pstats">
        <span>📊 ${p.total.toLocaleString()} 条数据</span>
        <span>⭐ ${p.avg_rating}</span>
        <span>🏅 ${p.five_star_pct}% 五星</span>
      </div>
      <div class="psummary">${escapeHtml(cleanSummary)||'摘要生成中...'}</div>
      <div class="pbar"><div class="pbar-fill" style="width:${(p.total/D.product_ranking[0].total*100)}%"></div></div>`;
    card.addEventListener('click',()=>showProductModal(p.name));
    card.style.opacity='0';card.style.transform='translateY(10px)';
    setTimeout(()=>{card.style.transition='opacity .5s ease, transform .5s ease';card.style.opacity='1';card.style.transform='translateY(0)'},i*40);
    grid.appendChild(card);
  });

  // Product monthly
  if(D.product_monthly){
    const pm=D.product_monthly;
    const cPM=initChart('prodMonthly');
    cPM.setOption({...baseOpt(),tooltip:{trigger:'axis'},
      legend:{data:Object.keys(pm.products),textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},top:0,type:'scroll'},
      xAxis:{type:'category',data:pm.months,axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}},axisLabel:{fontSize:10,rotate:30}},
      yAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      series:Object.entries(pm.products).map(([name,data],i)=>({
        name,type:'line',data,smooth:true,
        lineStyle:{width:2,color:PAL[i%PAL.length]},itemStyle:{color:PAL[i%PAL.length]},
        areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:PAL[i%PAL.length]+'20'},{offset:1,color:'transparent'}]}},
        symbol:'circle',symbolSize:4}))});
  }

  // Rating compare
  const prods=D.product_ranking.filter(p=>p.reviews>10).slice(0,15);
  initChart('prodRatingCompare').setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:80,right:10,top:10,bottom:20},
    xAxis:{type:'value',min:3,max:5,splitLine:{lineStyle:{color:PAL[0]+'10'}}},
    yAxis:{type:'category',data:prods.map(p=>p.name).reverse(),axisLabel:{fontSize:10}},
    series:[{type:'bar',data:prods.map(p=>p.avg_rating).reverse(),
      itemStyle:{color:(p)=>p.value>=4.8?COLORS.positive:p.value>=4.5?PAL[0]:COLORS.negative,borderRadius:[0,3,3,0]},
      barMaxWidth:14,label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)',formatter:'{c}'}}]});

  select.addEventListener('change',()=>{if(select.value)showProductModal(select.value)});
}

function showProductModal(name){
  const overlay=document.getElementById('modalOverlay');
  const title=document.getElementById('modalTitle');
  const body=document.getElementById('modalBody');
  const summaries=D.product_summaries||{};
  const info=summaries[name]||{};
  const prod=D.product_ranking.find(p=>p.name===name)||{};

  title.textContent=`${name} - 产品分析报告`;
  body.innerHTML=`
    <div class="row" style="margin-bottom:16px">
      <div class="kpi" style="flex:1"><div class="val">${prod.total||0}</div><div class="lbl">总数据量</div></div>
      <div class="kpi" style="flex:1"><div class="val">${prod.reviews||0}</div><div class="lbl">评论数</div></div>
      <div class="kpi" style="flex:1"><div class="val">${prod.avg_rating||0}</div><div class="lbl">平均评分</div></div>
      <div class="kpi" style="flex:1"><div class="val">${prod.five_star_pct||0}%</div><div class="lbl">五星率</div></div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">AI 产品口碑摘要</div>
      <p style="font-size:13px;line-height:1.8;color:var(--text-dim)">${escapeHtml(info.summary||'摘要生成中...').replace(/\n/g,'<br>')}</p>
    </div>
    <div class="row">
      <div class="col"><div class="card"><div class="card-title">月度趋势</div><div class="chart-box" id="modalChart1" style="height:250px"></div></div></div>
    </div>`;
  overlay.classList.add('show');

  setTimeout(()=>{
    const pm=D.product_monthly;
    if(pm&&pm.products[name]){
      const c=echarts.init(document.getElementById('modalChart1'));
      c.setOption({...baseOpt(),tooltip:{trigger:'axis'},
        xAxis:{type:'category',data:pm.months,axisLabel:{fontSize:10,rotate:30}},
        yAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
        series:[{type:'line',data:pm.products[name],smooth:true,
          lineStyle:{color:PAL[0],width:2},itemStyle:{color:PAL[0]},
          areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:PAL[0]+'30'},{offset:1,color:'transparent'}]}}}]});
    }
  },100);
}

/* ═══════════════════════════════════
   PAGE: GEOGRAPHY (俄罗斯地图)
   ═══════════════════════════════════ */
let geoInited=false;
function initGeography(){
  if(geoInited||!D)return;geoInited=true;

  const locs=D.ner.locations||[];
  if(locs.length>0){
    // 将城市数据映射为坐标格式
    const cityData = locs.map(loc => {
      const city = RUSSIA_CITIES.find(c => c.name===loc.name);
      return city ? {name:loc.name, value:[...city.value.slice(0,2), loc.value]} : null;
    }).filter(Boolean);

    if(cityData.length>0){
      const cGeo=initChart('geoChart');
      cGeo.setOption({
        tooltip:{trigger:'item',formatter:p=>`${p.name}<br/>提及次数: ${p.value[2]}`},
        visualMap:{
          min:0,max:Math.max(...cityData.map(d=>d.value[2])),
          text:['高','低'],realtime:false,calculable:true,
          inRange:{color:['rgba(22,27,34,0.1)','#58a6ff','#f778ba']},
          textStyle:{color:'rgba(145,152,161,0.4)'}
        },
        geo:{
          map:'俄罗斯',roam:true,zoom:1.2,center:[65,60],
          itemStyle:{areaColor:'rgba(22,27,34,0.15)',borderColor:'rgba(110,118,129,0.15)',borderWidth:1},
          emphasis:{itemStyle:{areaColor:'rgba(110,118,129,0.3)'}},
          label:{show:false}
        },
        series:[{
          name:'城市热度',type:'effectScatter',coordinateSystem:'geo',
          data:cityData,
          symbolSize:val=>Math.sqrt(val[2])*3,
          rippleEffect:{brushType:'stroke'},
          label:{formatter:'{b}',position:'right',show:false},
          itemStyle:{color:'#58a6ff'}
        }]
      });
    } else {
      // 降级：柱状图
      const cGeo=initChart('geoChart');
      cGeo.setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:100,right:30,top:20,bottom:20},
        xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
        yAxis:{type:'category',data:locs.slice(0,20).map(d=>d.name).reverse(),axisLabel:{fontSize:11},axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}}},
        series:[{type:'bar',data:locs.slice(0,20).map(d=>d.value).reverse(),
          itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:PAL[2]+'30'},{offset:1,color:PAL[2]}]},borderRadius:[0,5,5,0]},
          barMaxWidth:18,label:{show:true,position:'right',fontSize:10,color:'rgba(145,152,161,0.5)',formatter:'{c} 次提及'}}]});
    }
  }

  // Competitors
  const comps=D.ner.competitors||[];
  if(comps.length>0){
    initChart('geoCompetitors').setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:80,right:10,top:5,bottom:20},
      xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      yAxis:{type:'category',data:comps.slice(0,10).map(d=>d.name).reverse(),axisLabel:{fontSize:10}},
      series:[{type:'bar',data:comps.slice(0,10).map(d=>d.value).reverse(),
        itemStyle:{color:PAL[1],borderRadius:[0,3,3,0]},barMaxWidth:14,
        label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)'}}]});
  }

  // Features wordcloud
  const feats=D.ner.features||[];
  if(feats.length>0){
    initChart('geoFeatures').setOption({tooltip:{show:true},series:[{type:'wordCloud',shape:'circle',sizeRange:[12,38],rotationRange:[-20,20],gridSize:5,
      textStyle:{fontFamily:"'PingFang SC','Microsoft YaHei'",color:()=>PAL[Math.floor(Math.random()*PAL.length)]},
      data:feats.slice(0,30)}]});
  }
}

/* ═══════════════════════════════════
   PAGE: TIMELINE
   ═══════════════════════════════════ */
let timelineInited=false;
function initTimeline(){
  if(timelineInited||!D)return;timelineInited=true;

  // Heatmap
  const heatData=D.daily_heatmap||[];
  if(heatData.length>0){
    const maxH=Math.max(1,...heatData.map(d=>d[1]));
    const calRange=(D.kpi&&D.kpi.date_range_start&&D.kpi.date_range_end)
      ? [D.kpi.date_range_start,D.kpi.date_range_end]
      : (heatData.length>0?[heatData[0][0].slice(0,7),heatData[heatData.length-1][0].slice(0,7)]:['2025-03','2026-05']);
    initChart('tlHeatmap').setOption({...baseOpt(),tooltip:{formatter:p=>`${p.value[0]}<br>评论数: ${p.value[1]}`},
      visualMap:{min:0,max:maxH,calculable:true,orient:'horizontal',left:'center',bottom:0,
        inRange:{color:['rgba(22,27,34,0.1)','rgba(88,166,255,0.3)','rgba(247,120,186,0.7)',PAL[1]]},
        textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10}},
      calendar:{range:calRange,top:30,left:50,right:30,cellSize:['auto',14],
        yearLabel:{show:false},monthLabel:{color:'rgba(145,152,161,0.4)',fontSize:10},
        dayLabel:{color:'rgba(145,152,161,0.3)',fontSize:9,firstDay:1},
        splitLine:{lineStyle:{color:'rgba(145,152,161,0.06)'}},itemStyle:{borderColor:'rgba(13,17,23,0.6)',borderWidth:1}},
      series:[{type:'heatmap',coordinateSystem:'calendar',data:heatData}]});
  }

  // Trend with dataZoom
  renderTimelineTrend(initChart('tlTrend'), D.monthly_trend.months);

  // Length distribution
  initChart('tlLength').setOption({...baseOpt(),tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:D.review_length_dist.labels,axisLabel:{fontSize:10}},
    yAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
    series:[{type:'bar',data:D.review_length_dist.values,
      itemStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:PAL[2]},{offset:1,color:PAL[2]+'30'}]},borderRadius:[3,3,0,0]},barMaxWidth:30}]});

  // Time slider — 实际过滤月度趋势图
  const slider=document.getElementById('timeSlider');
  const label=document.getElementById('timeLabel');
  const months=D.monthly_trend.months;
  if(slider&&months){
    slider.max=months.length-1;slider.value=months.length-1;
    label.textContent=`${months[0]} ~ ${months[months.length-1]}`;
    slider.addEventListener('input',()=>{
      const idx=parseInt(slider.value);
      label.textContent=`${months[0]} ~ ${months[idx]}`;
      const cTL=chartInstances['tlTrend'];
      if(cTL&&!cTL.isDisposed())renderTimelineTrend(cTL,months.slice(0,idx+1));
    });
  }
}

/* 渲染时间轴趋势图（可复用，用于滑块过滤） */
function renderTimelineTrend(chart,months){
  if(!chart)return;
  const mt=D.monthly_trend;
  chart.setOption({...baseOpt(),tooltip:{trigger:'axis'},
    legend:{data:['评论量','问答量','平均评分'],textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},top:0},
    dataZoom:[{type:'slider',start:0,end:100,bottom:5,height:20,
      borderColor:'rgba(110,118,129,0.15)',fillerColor:'rgba(110,118,129,0.08)',
      handleStyle:{color:PAL[0]},textStyle:{color:'rgba(145,152,161,0.4)',fontSize:10},
      dataBackground:{lineStyle:{color:PAL[0]+'40'},areaStyle:{color:PAL[0]+'10'}}}],
    xAxis:{type:'category',data:months,axisLabel:{fontSize:10,rotate:30}},
    yAxis:[{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},{type:'value',min:4,max:5,splitLine:{show:false}}],
    series:[
      {name:'评论量',type:'bar',data:mt.reviews.slice(0,months.length),itemStyle:{color:PAL[0],borderRadius:[3,3,0,0]},barMaxWidth:18},
      {name:'问答量',type:'bar',data:mt.qa.slice(0,months.length),itemStyle:{color:PAL[1],borderRadius:[3,3,0,0]},barMaxWidth:18},
      {name:'平均评分',type:'line',yAxisIndex:1,data:mt.avg_rating.slice(0,months.length),smooth:true,lineStyle:{color:PAL[2],width:2},itemStyle:{color:PAL[2]}},
    ]});
}

/* ═══════════════════════════════════
   PAGE: QA
   ═══════════════════════════════════ */
let qaInited=false;
function initQA(){
  if(qaInited||!D)return;qaInited=true;

  // Intent
  const intData=D.intent.distribution||[];
  if(intData.length>0){
    initChart('qaIntent').setOption({...baseOpt(),tooltip:{trigger:'item'},
      series:[{type:'pie',roseType:'radius',radius:['12%','72%'],center:['50%','55%'],
        itemStyle:{borderRadius:5,borderColor:'rgba(13,17,23,0.8)',borderWidth:1},
        label:{color:'rgba(230,237,243,0.7)',fontSize:10,formatter:'{b}\n{d}%'},
        data:intData.map((d,i)=>({...d,itemStyle:{color:PAL[i%PAL.length]}})),
        animationType:'scale'}]});
  }

  // Question wordcloud
  if(D.wordcloud_questions){
    initChart('qaWordcloud').setOption({tooltip:{show:true},series:[{type:'wordCloud',shape:'circle',sizeRange:[12,42],rotationRange:[-25,25],gridSize:5,
      textStyle:{fontFamily:"'PingFang SC','Microsoft YaHei'",color:()=>PAL[Math.floor(Math.random()*PAL.length)]},
      data:D.wordcloud_questions.slice(0,50)}]});
  }

  // Scatter
  initChart('qaScatter').setOption({...baseOpt(),tooltip:{formatter:p=>`评分: ${p.value[0]}星<br>长度: ${p.value[1]}字`},
    xAxis:{type:'value',name:'评分',min:0,max:6,splitLine:{lineStyle:{color:PAL[0]+'10'}},axisLabel:{fontSize:10}},
    yAxis:{type:'value',name:'字数',splitLine:{lineStyle:{color:PAL[0]+'10'}},axisLabel:{fontSize:10}},
    dataZoom:[{type:'slider',xAxisIndex:0,bottom:5,height:18,borderColor:'rgba(110,118,129,0.15)',fillerColor:'rgba(110,118,129,0.08)'}],
    series:[{type:'scatter',data:D.rating_length_scatter,symbolSize:5,
      itemStyle:{color:'rgba(88,166,255,0.35)'}}]});

  // Top authors
  const authData=D.top_authors;
  if(authData){
    initChart('qaAuthors').setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:80,right:10,top:5,bottom:20},
      xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      yAxis:{type:'category',data:authData.names.slice(0,12).reverse(),axisLabel:{fontSize:10}},
      series:[{type:'bar',data:authData.counts.slice(0,12).reverse(),
        itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:PAL[0]+'25'},{offset:1,color:PAL[0]}]},borderRadius:[0,3,3,0]},
        barMaxWidth:14,label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)'}}]});
  }
}

/* ═══════════════════════════════════
   PAGE: DIAGNOSIS
   ═══════════════════════════════════ */
let diagnosisInited=false;
function initDiagnosis(){
  if(diagnosisInited||!D)return;diagnosisInited=true;

  // Root causes
  const rcData=D.rootcause.causes||[];
  if(rcData.length>0){
    const cRC=initChart('diagRootCause');
    const items=rcData.slice(0,15);
    cRC.setOption({...baseOpt(),tooltip:{trigger:'axis'},grid:{left:120,right:20,top:10,bottom:20},
      xAxis:{type:'value',splitLine:{lineStyle:{color:PAL[0]+'10'}}},
      yAxis:{type:'category',data:items.map(d=>d.name.length>12?d.name.substring(0,12)+'...':d.name).reverse(),
        axisLabel:{fontSize:10},axisLine:{lineStyle:{color:'rgba(145,152,161,0.2)'}}},
      series:[{type:'bar',data:items.map(d=>d.value).reverse(),
        itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:'rgba(248,81,73,0.15)'},{offset:1,color:COLORS.negative}]},borderRadius:[0,4,4,0]},
        barMaxWidth:16,label:{show:true,position:'right',fontSize:9,color:'rgba(145,152,161,0.4)'}}]});
  }

  // Severity
  const sevData=D.rootcause.severity||{};
  const sevKeys=Object.keys(sevData);
  if(sevKeys.length>0){
    const sevColors={'high':'#f778ba0a0','medium':'#d29922','low':'#3fb950'};
    initChart('diagSeverity').setOption({...baseOpt(),tooltip:{trigger:'item'},
      series:[{type:'pie',radius:['35%','65%'],center:['50%','50%'],
        itemStyle:{borderRadius:6,borderColor:'rgba(13,17,23,0.8)',borderWidth:2},
        label:{color:'rgba(230,237,243,0.7)',fontSize:12,formatter:'{b}\n{c} ({d}%)'},
        data:sevKeys.map(k=>({
          name:k==='high'?'高':k==='medium'?'中':k==='low'?'低':'未知',
          value:sevData[k],
          itemStyle:{color:sevColors[k]||PAL[0]}
        })),
        animationType:'scale'}]});
  }

  // Negative review stream
  const reviewStream=document.getElementById('diagReviews');
  const negWords=D.wordcloud_negative||[];
  const rc=D.rootcause||{};
  if(negWords.length>0){
    reviewStream.innerHTML=`
      <div style="padding:12px;text-align:center;color:var(--text-dim);font-size:12px">
        <p style="margin-bottom:12px">差评核心关键词 TOP 10${rc.negative_count?` <span style="color:var(--negative);font-weight:700">· 差评样本 ${Number(rc.negative_count).toLocaleString()} 条</span>`:''}</p>
        ${negWords.slice(0,10).map((w,i)=>`
          <div class="review-item negative" style="text-align:left;display:flex;justify-content:space-between">
            <span>#${i+1} ${escapeHtml(w.name)}</span><span style="color:var(--negative)">${w.value} 次</span>
          </div>`).join('')}
        <p style="margin-top:12px;color:var(--text-muted);font-size:10px">完整差评内容请在情感洞察页面查看</p>
      </div>`;
  }
}

/* ── Load overview on page load ── */
document.addEventListener('DOMContentLoaded',()=>initOverview());
