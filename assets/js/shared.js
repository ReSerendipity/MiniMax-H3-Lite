/* ============================================================
   MM·H3 工作台 · 共享逻辑（三模式页共用）
   页面通过 window.MMH3_PAGE 声明模式；本文件按页面配置渲染
   顶栏模式切换 / 时间线 / 参数联动 / 素材管理 / 生成提交。
   契约与 backend/h3/spec.py 及官方三份工作流一致。
   ============================================================ */
(function(){
'use strict';

/* ============ 基础工具 ============ */
function $(id){return document.getElementById(id);}
/* 单端口整合：页面与 API 同源（FastAPI 18080 直出），用相对路径 */
var API_BASE='/api';
var API_ORIGIN='';

/* 存储安全包装：localStorage 不可用（如 Canvas 预览 iframe）时降级内存 */
var memStore={};
function storeGet(k){try{var v=localStorage.getItem(k);return v===null?undefined:v;}catch(e){return memStore[k];}}
function storeSet(k,v){try{localStorage.setItem(k,v);}catch(e){}memStore[k]=v;}

/* ============ 页面配置与模式映射（与官方工作流一致） ============ */
var PAGE=window.MMH3_PAGE||{id:'t2v',file:'/',mode:'text'};
var MODE_PAGES=[
  {id:'t2v',label:'文生',sub:'T2V',file:'/'},
  {id:'i2v',label:'图生',sub:'I2V',file:'/i2v'},
  {id:'r2v',label:'多模态参考',sub:'R2V',file:'/r2v'}
];
var SHOT_MODE_PAGE={text:'/',first_frame:'/i2v',last_frame:'/i2v',first_last:'/i2v',ref:'/r2v'};
var MODE_LABEL={text:'T2V',first_frame:'I2V·首',last_frame:'I2V·末',first_last:'I2V·首尾',ref:'R2V'};

/* ============ 官方规格换算（与 backend/h3/spec.py 一致） ============ */
var H3_RATIOS={'21:9':[21,9],'16:9':[16,9],'4:3':[4,3],'1:1':[1,1],'3:4':[3,4],'9:16':[9,16]};
function framesForDuration(d){
  var b=Math.max(5,Math.round(d*24));
  return b+((5-(b%17))%17+17)%17;
}
/* 官方分辨率档位（与 backend/h3/spec.py RESOLUTION_PRESETS 一致，上限 0.98=1344×768，H3-Base 原生最高） */
var H3_RES_PRESETS=['0.4','0.5','0.6','0.7','0.8','0.9','0.98'];
var H3_RES_16_9={'0.4':[864,480],'0.5':[960,544],'0.6':[1056,608],'0.7':[1152,640],'0.8':[1216,672],'0.9':[1280,736],'0.98':[1344,768]};
var H3_RES_DEFAULT='0.98';   /* H3 原生画布（最高） */
/* 各档位短边（与 backend/h3/spec.py RESOLUTION_SHORT_SIDE 一致） */
var H3_RES_SHORT={'0.4':480,'0.5':544,'0.6':608,'0.7':640,'0.8':672,'0.9':736,'0.98':768};
function dimsForResolution(preset,aspect){
  var p=H3_RES_16_9[preset]?preset:H3_RES_DEFAULT;
  if(!aspect||aspect==='16:9')return H3_RES_16_9[p].slice();
  var sw=H3_RES_SHORT[p]||768,cap=1344;
  var r=H3_RATIOS[aspect]||[16,9],m=32,w,h;
  if(r[0]>=r[1]){w=sw*r[0]/r[1];h=sw;}else{h=sw*r[1]/r[0];w=sw;}
  var rd=function(v){v=Math.max(Math.floor(v),m);v=Math.ceil(v/m)*m;return Math.min(v,cap);};
  return [rd(w),rd(h)];
}

/* ============ 展示壳 / 主题（首访引导 + 持久化） ============ */
var SHELL_META={theater:{label:'剧场',sw:'#b3261e',desc:'红幕揭晓 · 剧场红'},pj:{label:'放映机',sw:'#15726c',desc:'青橙银幕 · 放映机'}};
var currentShell=storeGet('mmh3_shell')||'pj';
var currentTheme=storeGet('mmh3_theme')||'light';
var shellHint={theater:'剧场模式 · 生成时幕布揭晓',pj:'放映机模式 · 青橙银幕'};

function applyShell(s,persist){
  currentShell=s;
  document.documentElement.setAttribute('data-shell',s);
  var ps=document.querySelector('.preview-shell');
  if(ps)ps.setAttribute('data-mode',s);
  var sa=$('stageArea');
  if(sa)sa.setAttribute('data-shell',s);
  var h=$('stageHint');
  if(h)h.textContent=shellHint[s]||'';
  if(persist)storeSet('mmh3_shell',s);
  syncAppMenu();
}
function applyTheme(t,persist){
  currentTheme=t;
  document.documentElement.setAttribute('data-theme',t);
  if(persist)storeSet('mmh3_theme',t);
  syncAppMenu();
}

/* 首访引导弹层：无持久化值时出现一次 */
function renderShellModal(){
  var host=$('shellModal');
  if(!host)return;
  if(storeGet('mmh3_shell'))return; /* 已有持久化选择则不再出现 */
  var box=document.createElement('div');
  box.className='sm-box';
  box.innerHTML=
    '<div class="sm-title">选择展示壳</div>'+
    '<div class="sm-sub">展示壳决定工作台的观看氛围与强调色，选择后固定使用，可在顶栏「外观」菜单随时更换。</div>'+
    '<div class="sm-cards">'+
      ['theater','pj'].map(function(s){
        var m=SHELL_META[s];
        return '<button type="button" class="sm-card '+s+'" data-shell="'+s+'">'+
          '<span class="sm-visual"></span>'+
          '<span class="sm-meta"><span class="sm-name"><span class="sm-sw" style="background:'+m.sw+'"></span>'+m.label+'</span>'+
          '<span class="sm-desc">'+m.desc+'</span></span></button>';
      }).join('')+
    '</div>'+
    '<button type="button" class="sm-skip" id="smSkip">跳过 · 使用默认（放映机）</button>';
  host.appendChild(box);
  host.classList.add('open');
  host.addEventListener('click',function(e){
    var card=e.target&&e.target.closest?e.target.closest('.sm-card'):null;
    if(card){applyShell(card.dataset.shell,true);host.classList.remove('open');return;}
    var skip=e.target&&e.target.closest?e.target.closest('#smSkip'):null;
    if(skip){applyShell('pj',false);host.classList.remove('open');}
  });
}

/* ============ 顶栏：模式切换 + 外观菜单 ============ */
function renderModeTabs(){
  var host=$('modeTabs');
  if(!host)return;
  host.innerHTML='';
  MODE_PAGES.forEach(function(m){
    var a=document.createElement('a');
    a.className='mtab'+(m.id===PAGE.id?' on':'');
    a.href=m.file;
    a.setAttribute('role','tab');
    a.setAttribute('aria-selected',m.id===PAGE.id?'true':'false');
    a.innerHTML='<span>'+m.label+'</span><span class="mt-tag">'+m.sub+'</span>';
    host.appendChild(a);
  });
}
function syncAppMenu(){
  document.querySelectorAll('.app-opt[data-app="shell"]').forEach(function(o){
    o.classList.toggle('on',o.dataset.value===currentShell);
  });
  document.querySelectorAll('.app-opt[data-app="theme"]').forEach(function(o){
    o.classList.toggle('on',o.dataset.value===currentTheme);
  });
}

/* ============ 全局状态 ============ */
var currentProjectId=null;
var SHOT_REFS={};       /* shot_id -> [{id,kind,mime,name}] */
var i2vMap={};          /* shot_id -> {first:assetId|null, last:assetId|null} */
var pathMap={};         /* assetId -> asset.path（会话内缩略图用） */
var segs=[];
var pollTimer=null,ctxTimer=null;

var promptInput=$('promptInput'),charCount=$('charCount');
var stageScene=$('stageScene'),previewShell=$('previewShell');
var genStatus=$('genStatus'),playbar=$('playbar'),pbScrub=document.querySelector('.pb-scrub i');
var refBlock=document.querySelector('.ref-block'),refNote=refBlock?refBlock.querySelector('.bridge-note'):null;
var queueItem=$('queueItem');

/* ============ 项目下拉 ============ */
var projSwitch=$('projSwitch'),projDropdown=$('projDropdown'),projList=$('projList');
var projNameEl=$('projName'),projMetaEl=$('projMeta');

function loadProjects(prefProject,prefShot){
  fetch(API_BASE+'/projects').then(function(r){return r.json();}).then(function(list){
    if(!currentProjectId&&list.length){
      var pid=prefProject&&list.some(function(p){return p.id===prefProject;})?prefProject:list[0].id;
      switchProject(pid,list.filter(function(p){return p.id===pid;})[0].name,prefShot);
    }
    projList.innerHTML='';
    list.forEach(function(p){
      var item=document.createElement('div');
      item.className='proj-item'+(p.id===currentProjectId?' active':'');
      item.innerHTML='<span class="pi-name">'+p.name+'</span><span class="pi-meta">'+(p.shot_count||0)+' shots</span><button class="pi-ren" title="重命名">✎</button><button class="pi-del" title="删除">✕</button>';
      item.addEventListener('click',function(e){
        if(e.target.classList.contains('pi-del')){
          e.stopPropagation();
          if(confirm('删除项目「'+p.name+'」？镜头与历史将一并删除。')){
            fetch(API_BASE+'/projects/'+p.id,{method:'DELETE'}).then(function(){loadProjects();});
          }
          return;
        }
        if(e.target.classList.contains('pi-ren')){
          e.stopPropagation();
          var newName=prompt('重命名项目',p.name);
          if(newName&&newName.trim()){
            fetch(API_BASE+'/projects/'+p.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newName.trim()})}).then(function(){loadProjects();});
          }
          return;
        }
        switchProject(p.id,p.name);
      });
      projList.appendChild(item);
    });
  }).catch(function(){projList.innerHTML='<div class="proj-item"><span class="pi-name">后端未启动</span></div>';});
}
function switchProject(pid,name,shotId){
  currentProjectId=pid;
  projNameEl.textContent=name;
  projSwitch.classList.remove('open');
  projSwitch.setAttribute('aria-expanded','false');
  loadProjectShots(pid,shotId);
  loadHistory(pid);
}
if(projSwitch){
  projSwitch.addEventListener('click',function(e){
    e.stopPropagation();
    projSwitch.classList.toggle('open');
    projSwitch.setAttribute('aria-expanded',projSwitch.classList.contains('open')?'true':'false');
  });
  projSwitch.addEventListener('keydown',function(e){
    if(e.key==='Enter'||e.key===' '){e.preventDefault();projSwitch.click();}
  });
}
/* 一键清空全部（POST /api/projects/clear） */
var projClear=$('projClear');
if(projClear){
  projClear.addEventListener('click',function(e){
    e.stopPropagation();
    if(!confirm('一键清空全部？将删除所有项目、镜头、生成任务与资产，并清空 uploads/ 与 assets/ 目录下的文件。此操作不可撤销。'))return;
    projClear.disabled=true;
    projClear.textContent='清空中…';
    fetch(API_BASE+'/projects/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keep_uploads:false})})
      .then(function(r){return r.json();})
      .then(function(res){
        if(res.detail){window.alert('清空失败: '+res.detail);return;}
        currentProjectId=null;
        projNameEl.textContent='未命名项目_01';
        if(projMetaEl)projMetaEl.textContent='0 SHOTS';
        var tl=$('tlSegments');
        if(tl){
          var ctl=tl.querySelector('.tl-ctl');
          var ph=tl.querySelector('.playhead');
          var addBtn=tl.querySelector('.seg.add');
          tl.innerHTML='';
          if(ctl)tl.appendChild(ctl);
          if(ph)tl.appendChild(ph);
          if(addBtn)tl.appendChild(addBtn);
        }
        segs=[];
        updateTotals();
        loadProjects();
        window.alert('已清空：'+JSON.stringify(res.cleared)+'，删除文件 '+JSON.stringify(res.removed_files));
      })
      .catch(function(){window.alert('清空失败: 后端连接失败');})
      .finally(function(){
        projClear.disabled=false;
        projClear.textContent='⌫ 一键清空全部';
        projSwitch.classList.remove('open');
      });
  });
}

/* ============ 时间线 / 镜头 ============ */
function activeShotId(){var s=document.querySelector('.seg.active');return s&&s.dataset.id?s.dataset.id:null;}
function findShot(sid){var hit=null;segs.forEach(function(s){if(s.dataset.id===sid)hit=s;});return hit;}

function sizeSegs(){segs.forEach(function(s){s.style.width=(72+6*parseInt(s.dataset.dur,10))+'px';});}
function updateTotals(){
  var total=0;segs.forEach(function(s){total+=parseInt(s.dataset.dur,10);});
  var tsub=document.querySelector('.tsub');
  if(tsub)tsub.textContent='TIMELINE · 总时长 '+total+'s · '+segs.length+' 镜头';
  var sb=$('totalDurSb');
  if(sb)sb.textContent='总时长 '+total+'s';
}
function bindSeg(s){
  s.addEventListener('click',function(){selectShot(s);});
  s.addEventListener('keydown',function(e){
    if(e.key==='Enter'||e.key===' '){e.preventDefault();selectShot(s);}
  });
}

function selectShot(seg){
  if(!seg)return;
  var mode=seg.dataset.mode||'text';
  var page=SHOT_MODE_PAGE[mode]||'/';
  /* 该镜头属于其他模式页 → 跨页跳转并选中 */
  if(page!==PAGE.file){
    location.href=page+'?project='+(currentProjectId||'')+'&shot='+seg.dataset.id;
    return;
  }
  segs.forEach(function(s){s.classList.remove('active');s.setAttribute('aria-selected','false');});
  seg.classList.add('active');
  seg.setAttribute('aria-selected','true');
  var name=seg.dataset.name,dur=seg.dataset.dur,shot=+seg.dataset.shot+1;
  var s=('0'+shot).slice(-2),d=('0'+dur).slice(-2);
  var shotNo=$('shotNo');if(shotNo)shotNo.textContent=s;
  var shotScene=$('shotScene');if(shotScene)shotScene.className='shot-scene s'+(shot-1);
  var shotName=$('shotName');if(shotName)shotName.textContent=name;
  var slateShot=$('slateShot');if(slateShot)slateShot.textContent='SHOT '+s;
  var tvSrc=$('tvSrc');if(tvSrc)tvSrc.textContent='SRC · SHOT '+s;
  var slateTc=$('slateTc');if(slateTc)slateTc.textContent='00:00:'+('0'+(dur-1)).slice(-2)+'.00';
  var pbShot=$('pbShot');if(pbShot)pbShot.innerHTML=name+'<small>SHOT '+s+' · 0:'+d+'</small>';
  var pbTime=$('pbTime');if(pbTime)pbTime.textContent='00:00.0 / 00:'+d;
  promptInput.value=seg.dataset.prompt;
  updateCount();
  readbackParams(seg);
  if(PAGE.id==='i2v')renderFrameSlots();
  if(PAGE.id==='r2v')renderRefs(seg.dataset.id);
}

function readbackParams(seg){
  var params={};
  try{params=JSON.parse(seg.dataset.params||'{}');}catch(e){}
  document.querySelectorAll('.p-row').forEach(function(r){
    var k=r.querySelector('.k')?r.querySelector('.k').textContent.trim():'';
    if(k==='种子')return;  /* 种子行含输入框+随机按钮，跳过 chip 回填循环 */
    var opts=r.querySelectorAll('.seg:not(.disabled)');
    if(!opts.length)return;
    opts.forEach(function(x){x.classList.remove('on');});
    var v=null;
    if(k==='帧模式')v=seg.dataset.mode||'first_frame';
    else if(k==='画面比例')v=params.aspect;
    else if(k==='分辨率'){
      v=params.resolution;
      /* 旧值 768P/2K → 官方原生档 0.98（H3-Base 原生最高） */
      if(v==='768P'||v==='2K')v=H3_RES_DEFAULT;
      if(!v)v=H3_RES_DEFAULT;
    }
    else if(k==='时长'){var durInput=r.querySelector('#durationInput');if(durInput&&params.duration!=null)durInput.value=params.duration;return;}
    else if(k==='生成尺寸')v=(params.size_mode==='follow_first'?'follow_first':'0.98M');
    var matched=false;
    if(v){opts.forEach(function(x){if(x.dataset.value===v){x.classList.add('on');matched=true;}});}
    if(!matched)opts[0].classList.add('on');
  });
  /* 种子回填 */
  var si=$('seedInput');
  if(si)si.value=(params.seed!=null)?String(params.seed):'';
  /* Steps 回填 (主视图) */
  var ms=$('mainSteps');
  if(ms&&params.steps!=null)ms.value=params.steps;
  /* 高级参数回填 */
  var as=$('advSampler');
  if(as)as.value=params.sampler||'';
  var asch=$('advScheduler');
  if(asch)asch.value=params.scheduler_override||'';
  var ast=$('advSteps');
  if(ast)ast.value=(params.steps!=null)?String(params.steps):'';
  var ad=$('advDenoise');
  if(ad)ad.value=(params.denoise!=null)?String(params.denoise):'';
  /* r2v：ref_image_size 回填 */
  if(PAGE.id==='r2v'){
    var rs=document.querySelectorAll('.ref-size .seg');
    if(rs.length){
      [].slice.call(rs).forEach(function(x){x.classList.remove('on');});
      var rsv=params.ref_image_size||'match';
      var rsm=false;
      [].slice.call(rs).forEach(function(x){if(x.dataset.value===rsv){x.classList.add('on');rsm=true;}});
      if(!rsm)rs[0].classList.add('on');
    }
  }
  /* 分辨率档 × 画面比例 → 输出像素（官方 ResolutionSelector 语义） */
  var resPx=$('resPx');
  if(resPx){
    var rp=params.resolution||H3_RES_DEFAULT;
    if(rp==='768P'||rp==='2K')rp=H3_RES_DEFAULT;
    var d=dimsForResolution(rp,params.aspect||'16:9');
    resPx.innerHTML=(params.aspect||'16:9')+' → <b>'+d[0]+'×'+d[1]+'</b> <em>'+rp+'MP</em>';
  }
}

function loadProjectShots(pid,selectId){
  fetch(API_BASE+'/projects/'+pid+'/shots').then(function(r){return r.json();}).then(function(shots){
    var tl=$('tlSegments');
    var ctl=tl.querySelector('.tl-ctl');
    var ph=tl.querySelector('.playhead');
    var addBtn=tl.querySelector('.seg.add');
    tl.innerHTML='';
    tl.appendChild(ctl);
    tl.appendChild(ph);
    tl.appendChild(addBtn); /* innerHTML='' 会分离旧子节点，需重新挂载后再 insertBefore */
    SHOT_REFS={};i2vMap={};
    shots.forEach(function(s,i){
      var node=document.createElement('div');
      node.className='seg';
      node.dataset.shot=i;
      node.dataset.id=s.id;
      node.dataset.name=s.name;
      node.dataset.dur=s.duration;
      node.dataset.prompt=s.prompt;
      node.dataset.mode=s.mode||'text';
      node.dataset.params=JSON.stringify(s.params||{});
      node.setAttribute('data-component','timeline-segment');
      node.setAttribute('role','button');
      node.setAttribute('tabindex','0');
      node.setAttribute('aria-selected','false');
      var no=('0'+(i+1)).slice(-2);
      var d=('0'+s.duration).slice(-2);
      node.innerHTML='<div class="sf"><span class="no">'+no+'</span><span class="dur">0:'+d+'</span></div><div class="nm"><b>'+s.name+'</b><span class="seg-mode">'+(MODE_LABEL[s.mode]||'T2V')+'</span></div>';
      tl.insertBefore(node,addBtn);
      bindSeg(node);
      SHOT_REFS[s.id]=(s.refs||[]).map(function(r){return {id:r.id,kind:r.kind,mime:r.mime,name:r.name,paired_video:r.paired_video};});
    });
    segs=[].slice.call(document.querySelectorAll('.seg[data-shot]'));
    sizeSegs();
    updateTotals();
    if(projMetaEl)projMetaEl.textContent=shots.length+' SHOTS · '+shots.reduce(function(a,s){return a+s.duration;},0)+'S';
    if(segs.length>0){
      var hit=null;
      if(selectId){segs.forEach(function(s){if(s.dataset.id===selectId)hit=s;});}
      selectShot(hit||segs[0]);
    }else{
      promptInput.value='';
      updateCount();
      if(PAGE.id==='i2v')renderFrameSlots();
      if(PAGE.id==='r2v')renderRefs(null);
    }
  }).catch(function(){
    if(projMetaEl)projMetaEl.textContent='0 SHOTS';
  });
}

/* ============ i2v：帧模式子项 + 首/末帧槽位 ============ */
function i2vSlotsFor(sid){
  var shot=findShot(sid);
  var p={};
  try{p=JSON.parse(shot.dataset.params||'{}');}catch(e){}
  var map=p.i2v||{};
  var imgs=(SHOT_REFS[sid]||[]).filter(function(r){return r.kind==='image';});
  var mode=shot?shot.dataset.mode:'first_frame';
  var out={first:map.first||null,last:map.last||null};
  if(!out.first&&!out.last){
    if(mode==='last_frame'){out.last=imgs[0]?imgs[0].id:null;}
    else{
      out.first=imgs[0]?imgs[0].id:null;
      if(mode==='first_last'&&imgs[1])out.last=imgs[1].id;
    }
  }
  return out;
}
function renderFrameSlots(){
  var sid=activeShotId();
  var slotEls=document.querySelectorAll('.fs-slot');
  if(!slotEls.length)return;
  var i2v=i2vSlotsFor(sid||'');
  var refs=SHOT_REFS[sid]||[];
  var frameMode=(function(){var row=null;document.querySelectorAll('.p-row').forEach(function(r){var k=r.querySelector('.k');if(k&&k.textContent.trim()==='帧模式')row=r;});var seg=row?row.querySelector('.seg.on'):null;return seg?(seg.dataset.value||'first_frame'):'first_frame';})();
  ['first','last'].forEach(function(slot){
    var el=$('fs-'+slot);
    if(!el)return;
    var wantFirst=(frameMode==='first_frame'||frameMode==='first_last');
    var wantLast=(frameMode==='last_frame'||frameMode==='first_last');
    el.classList.toggle('disabled',slot==='first'?!wantFirst:!wantLast);
    var id=i2v[slot];
    var ref=null;refs.forEach(function(r){if(r.id===id)ref=r;});
    var thumb=el.querySelector('.fs-thumb');
    if(thumb){
      var path=id?pathMap[id]:null;
      thumb.innerHTML=path
        ?'<img src="'+API_ORIGIN+'/'+path+'" alt="'+slot+'帧预览">'
        :'<span class="fs-placeholder">'+(ref?('<b>'+slotName(slot)+'</b><span>'+escapeHtml(ref.name)+'</span>'):('<b>'+slotName(slot)+' 未上传</b><span>点击下方按钮上传</span>'))+'</span>';
    }
  });
}
function slotName(s){return s==='first'?'首帧':'末帧';}
function escapeHtml(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}

function uploadFrame(slot){
  var inp=$('fsInput');
  var sid=activeShotId();
  if(!inp)return;
  if(!currentProjectId||!sid){window.alert('请先选择项目与镜头');return;}
  inp.dataset.slot=slot;
  inp.click();
}
function uploadRefs(){
  var inp=$('refInput');
  if(!inp)return;
  if(!currentProjectId||!activeShotId()){window.alert('请先选择项目与镜头');return;}
  inp.click();
}
function uploadPairedAudio(videoAssetId){
  var inp=$('pairAudioInput');
  if(!inp)return;
  if(!currentProjectId||!activeShotId()){window.alert('请先选择项目与镜头');return;}
  inp.dataset.pairedWith=videoAssetId;
  inp.click();
}
function doUpload(files,shotId,onDone,pairedWith){
  var pending=files.length;
  var failed=0;
  files.forEach(function(file){
    var fd=new FormData();
    fd.append('file',file);
    fd.append('shot_id',shotId);
    if(pairedWith)fd.append('paired_with',pairedWith);
    fetch(API_BASE+'/upload',{method:'POST',body:fd})
      .then(function(r){return r.json();})
      .then(function(a){
        if(a.detail||!a.id){failed++;window.alert('上传失败: '+(a.detail||'未知错误'));}
        else{
          if(a.path)pathMap[a.id]=a.path;
          if(SHOT_REFS[shotId]){
            SHOT_REFS[shotId].push({id:a.id,kind:a.kind,mime:a.mime,name:(a.meta&&a.meta.original_name)||a.id,paired_video:pairedWith||null});
          }
        }
        if(--pending===0)onDone(failed===0);
      })
      .catch(function(){failed++;if(--pending===0)onDone(failed===0);});
  });
}

/* ============ r2v：参考素材管理器（官方标签体系） ============ */
function renderRefs(sid){
  var box=$('refList');
  var refs=SHOT_REFS[sid]||[];
  if(!box)return;
  var imgN=0,vidN=0,audN=0;
  refs.forEach(function(r){if(r.kind==='image')imgN++;else if(r.kind==='video')vidN++;else if(r.kind==='audio')audN++;});
  var e1=$('refImgN');if(e1)e1.textContent=imgN;
  var e2=$('refVidN');if(e2)e2.textContent=vidN;
  var e3=$('refAudN');if(e3)e3.textContent=audN;
  box.style.display=refs.length?'flex':'none';
  box.innerHTML='';
  var imgi=0,vidi=0,audi=0;
  refs.forEach(function(r){
    var tag=r.kind==='image'?'Picture '+(++imgi):(r.kind==='video'?'Video '+(++vidi):'Audio '+(++audi));
    var pairedLabel=r.paired_video?'（音轨）':'';
    var d=document.createElement('div');
    d.className='rm-item';
    d.innerHTML='<span class="rm-tag">'+tag+'</span><span class="rm-name">'+escapeHtml(r.name)+pairedLabel+'</span>';
    /* 视频项追加「配同步音轨」按钮 */
    if(r.kind==='video'){
      var pairBtn=document.createElement('button');
      pairBtn.className='rm-pair';
      pairBtn.type='button';
      pairBtn.textContent='＋配同步音轨';
      pairBtn.title='为该视频上传同步音轨';
      pairBtn.addEventListener('click',function(e){e.stopPropagation();uploadPairedAudio(r.id);});
      d.appendChild(pairBtn);
    }
    box.appendChild(d);
  });
  renderTagChips();
}
function renderTagChips(){
  var box=$('tagChips');
  if(!box)return;
  box.innerHTML='';
  var sid=activeShotId();
  if(!sid)return;
  var refs=SHOT_REFS[sid]||[];
  var imgi=0,vidi=0,audi=0;
  refs.forEach(function(r){
    var tag=r.kind==='image'?'Picture '+(++imgi):(r.kind==='video'?'Video '+(++vidi):'Audio '+(++audi));
    var b=document.createElement('button');
    b.type='button';b.className='tg-chip';
    b.textContent='<'+tag+'>';
    b.addEventListener('click',function(){insertTag('<'+tag+'>');});
    box.appendChild(b);
  });
}
function insertTag(tag){
  var p=promptInput;
  var s=p.selectionStart||p.value.length,e=p.selectionEnd||p.value.length;
  p.value=p.value.slice(0,s)+tag+p.value.slice(e);
  p.focus();p.selectionStart=p.selectionEnd=s+tag.length;
  updateCount();
}

/* ============ 提示词 / 生成 ============ */
function updateCount(){
  var n=promptInput.value.replace(/\s/g,'').length;
  charCount.textContent=n+' 字符 · ≈'+Math.max(1,Math.round(n*1.4))+' token · 上限 7000';
  charCount.classList.toggle('over',n>7000);
}
function runContextIR(){
  var base=promptInput.value.trim()||'黄昏的海岸线，海浪缓缓拍打礁石，落日余晖洒在海面上，电影级调色，镜头缓慢推近';
  promptInput.value='[Context-IR 优化] '+base+'；画面氛围：黄昏色调；运镜：缓慢推近；成片参考：电影级写实质感';
  updateCount();
  var negBtn=document.querySelector('.neg');
  if(negBtn){
    negBtn.textContent='优化完成 ✓';
    negBtn.style.borderColor='var(--seed-primary)';
    clearTimeout(ctxTimer);
    ctxTimer=setTimeout(function(){negBtn.textContent='＋ 指令优化（轻量）';negBtn.style.borderColor='';},2000);
  }
}
function playDemo(){
  if(playbar.classList.contains('playing'))return;
  var seg=document.querySelector('.seg.active');
  var dur=seg&&seg.dataset.dur?parseInt(seg.dataset.dur,10):8;
  pbScrub.style.transition='width '+dur+'s linear';
  playbar.classList.add('playing');
  pbScrub.addEventListener('transitionend',function h(){
    pbScrub.removeEventListener('transitionend',h);
    playbar.classList.remove('playing');
    pbScrub.style.transition='';
  });
}
function setGenState(txt,done){
  genStatus.textContent=txt;
  genStatus.classList.toggle('done',!!done);
  stageScene.classList.add('genning');
}
function premiere(label){
  if(previewShell.dataset.mode!=='theater')return;
  var rc=$('revealCard');
  if(!rc)return;
  rc.querySelector('.rc-main').textContent='SHOT '+label+' · 首映';
  previewShell.classList.add('opened');
  rc.classList.remove('card-anim');
  void rc.offsetWidth;
  rc.classList.add('card-anim');
}
var revealCard=$('revealCard');
if(revealCard){
  revealCard.addEventListener('animationend',function(){revealCard.classList.remove('card-anim');});
}
var curtainClose=$('curtainClose');
if(curtainClose){
  curtainClose.addEventListener('click',function(){previewShell.classList.remove('opened');});
}

function getActiveMode(){
  if(PAGE.id==='t2v')return 'text';
  if(PAGE.id==='r2v')return 'ref';
  var row=null;
  document.querySelectorAll('.p-row').forEach(function(r){var k=r.querySelector('.k');if(k&&k.textContent.trim()==='帧模式')row=r;});
  var seg=row?row.querySelector('.seg.on'):null;
  return seg?(seg.dataset.value||'first_frame'):'first_frame';
}
function getActiveParams(){
  var p={};
  document.querySelectorAll('.p-row').forEach(function(r){
    var k=r.querySelector('.k')?r.querySelector('.k').textContent.trim():'';
    if(!k)return;
    /* 时长：input 类型，无需 .seg.on */
    if(k==='时长'){
      var durInput=r.querySelector('#durationInput');
      if(durInput){var durVal=parseInt(durInput.value,10);if(!isNaN(durVal)&&durVal>=4&&durVal<=15)p.duration=durVal;}
      return;
    }
    var on=r.querySelector('.seg.on');
    if(!on)return;
    var v=on.dataset.value||on.textContent.trim();
    if(k==='画面比例')p.aspect=v;
    else if(k==='分辨率')p.resolution=v||H3_RES_DEFAULT;
    else if(k==='生成尺寸')p.size_mode=(v==='follow_first'?'follow_first':'0.98M');
  });
  if(PAGE.id==='r2v'){
    var rs=document.querySelector('.ref-size .seg.on');
    if(rs)p.ref_image_size=rs.dataset.value||rs.textContent.trim();
  }
  // Steps (主视图)
  var mainSteps=$('mainSteps');if(mainSteps&&mainSteps.value.trim()!==''){var stepsVal=parseInt(mainSteps.value.trim(),10);if(!isNaN(stepsVal))p.steps=stepsVal;}
  /* 种子 */
  var si=$('seedInput');
  if(si&&si.value.trim()!==''){
    var seed=parseInt(si.value.trim(),10);
    if(!isNaN(seed))p.seed=seed;
  }
  /* 高级参数（留空=全局） */
  var as=$('advSampler');
  if(as&&as.value)p.sampler=as.value;
  var asch=$('advScheduler');
  if(asch&&asch.value)p.scheduler_override=asch.value;
  
  var ad=$('advDenoise');
  if(ad&&ad.value.trim()!==''){
    var den=parseFloat(ad.value.trim());
    if(!isNaN(den))p.denoise=den;
  }
  return p;
}
function submitGeneration(){
  var seg=document.querySelector('.seg.active');
  if(!seg||!seg.dataset.id){window.alert('请先在项目中选择镜头');return;}
  var sid=seg.dataset.id;
  var mode=getActiveMode();
  var params=getActiveParams();
  var refIds=[];
  if(PAGE.id==='i2v'){
    var i2v=i2vSlotsFor(sid);
    if(mode==='first_frame'&&!i2v.first){window.alert('首帧模式需先上传首帧图像');return;}
    if(mode==='last_frame'&&!i2v.last){window.alert('末帧模式需先上传末帧图像');return;}
    if(mode==='first_last'&&(!i2v.first||!i2v.last)){window.alert('首尾帧模式需上传首帧与末帧各一张图像');return;}
    refIds=[i2v.first,i2v.last].filter(Boolean);
  }else if(PAGE.id==='r2v'){
    var refs=SHOT_REFS[sid]||[];
    refIds=refs.map(function(r){return r.id;});
    if(!refIds.length){window.alert('多模态参考模式需要至少 1 个参考素材');return;}
    if(refs.every(function(r){return r.kind==='audio';})){window.alert('音频须搭配图像或视频输入');return;}
  }
  queueItem.textContent='QUEUE 1 · 1';
  queueItem.style.fontWeight='700';
  setGenState('提交中…',false);
  premiere(('0'+(+seg.dataset.shot+1)).slice(-2));
  var upd={prompt:promptInput.value,mode:mode,duration:params.duration||8,aspect:params.aspect||'16:9',params:params};
  fetch(API_BASE+'/shots/'+sid,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(upd)})
    .then(function(r){return r.json();})
    .catch(function(){return null;})
    .then(function(){
      return fetch(API_BASE+'/generations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shot_id:sid,mode:mode,prompt:promptInput.value,params:params,ref_ids:refIds})});
    })
    .then(function(r){return r.json();})
    .then(function(task){
      if(task.detail||!task.id){
        setGenState('提交失败: '+(task.detail||'未知错误'),true);
        queueItem.textContent='QUEUE 0 · 0';queueItem.style.fontWeight='';
        return;
      }
      setGenState('生成中 · 推理执行中',false);
      pollTask(task.id);
    })
    .catch(function(){
      setGenState('提交失败: 后端连接失败',true);
      queueItem.textContent='QUEUE 0 · 0';queueItem.style.fontWeight='';
    });
}
function pollTask(taskId){
  clearTimeout(pollTimer);
  pollTimer=setTimeout(function(){
    fetch(API_BASE+'/generations/'+taskId)
      .then(function(r){return r.json();})
      .then(function(task){
        if(task.status==='processing'){
          setGenState('生成中 · '+(task.progress||0)+'%',false);
          pollTask(taskId);
        }else if(task.status==='completed'){
          queueItem.textContent='QUEUE 0 · 0';
          queueItem.style.fontWeight='';
          setGenState('生成完成 ✓',true);
          if(task.result_path){
            var v=document.createElement('video');
            v.src=API_ORIGIN+'/'+task.result_path;
            v.style.cssText='position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0';
            v.loop=true;v.muted=true;v.autoplay=true;
            var old=stageScene.querySelector('video');
            if(old)old.remove();
            stageScene.appendChild(v);
          }
          setTimeout(function(){stageScene.classList.remove('genning');},1400);
        }else if(task.status==='failed'){
          queueItem.textContent='QUEUE 0 · 0';
          queueItem.style.fontWeight='';
          setGenState('生成失败: '+(task.error||'未知错误'),true);
          setTimeout(function(){stageScene.classList.remove('genning');},2000);
        }else{
          pollTask(taskId);
        }
      })
      .catch(function(){setGenState('查询任务失败: 后端连接失败',true);});
  },1000);
}

/* ============ 历史库 / 引擎 / 连接 ============ */
function loadHistory(pid){
  var body=$('historyBody');
  var count=$('historyCount');
  if(!body)return;
  fetch(API_BASE+'/projects/'+pid+'/history').then(function(r){return r.json();}).then(function(items){
    if(count)count.textContent=items.length+' 条';
    body.innerHTML='';
    if(!items.length){body.innerHTML='<div class="history-empty">暂无历史记录</div>';return;}
    items.forEach(function(it){
      var d=document.createElement('div');
      d.className='history-item';
      var thumb=it.result_path?'<img src="'+API_ORIGIN+'/'+it.result_path+'" alt="">':'';
      d.innerHTML='<div class="history-thumb">'+thumb+'</div><div class="history-info"><div class="hi-name">'+escapeHtml(it.name||it.shot_name||'镜头')+'</div><div class="hi-meta">'+(it.mode||'')+' · '+(it.duration||'')+'s · '+escapeHtml(it.created_at||'')+'</div><div class="hi-reuse">复用参数重新生成</div></div>';
      body.appendChild(d);
    });
  }).catch(function(){});
}
var historyBtn=$('historyBtn'),historyPanel=$('historyPanel');
if(historyBtn&&historyPanel){
  historyBtn.addEventListener('click',function(){historyPanel.classList.toggle('open');});
  var hc=$('historyClose');
  if(hc)hc.addEventListener('click',function(){historyPanel.classList.remove('open');});
}
var engineSwitch=$('engineSwitch'),engineMenu=$('engineMenu');
function toggleEngineMenu(force){
  var open=force!==undefined?force:!engineMenu.classList.contains('open');
  engineMenu.classList.toggle('open',open);
  engineSwitch.setAttribute('aria-expanded',String(open));
}
function loadEngines(){
  fetch(API_BASE+'/engines').then(function(r){return r.json();}).then(function(d){
    var engs=d.engines||[];
    var act=null;engs.forEach(function(e){if(e.active)act=e;});
    var et=$('engineText');
    if(et&&act)et.textContent='ENGINE: '+act.display_name;
    var dot=$('engineDot');
    if(dot&&act)dot.classList.toggle('external',!!act.external);
    var box=$('engineList');if(!box)return;
    box.innerHTML='';
    engs.forEach(function(e){
      var it=document.createElement('button');
      it.type='button';
      it.className='engine-item'+(e.active?' on':'')+(e.implemented?'':' off');
      it.setAttribute('role','menuitemradio');
      it.setAttribute('aria-checked',String(e.active));
      it.disabled=!e.implemented;
      it.innerHTML='<span>'+e.display_name+'</span>'+
        '<span class="ei-tag">'+(e.external?'外部服务':'本地进程内')+'</span>'+
        (e.implemented?'':'<span class="ei-badge">未实现</span>');
      if(e.implemented&&!e.active&&!d.locked){
        it.addEventListener('click',function(){
          fetch(API_BASE+'/engine/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({backend:e.name})})
            .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
            .then(function(){toggleEngineMenu(false);loadEngines();checkHealth();})
            .catch(function(){window.alert('引擎切换失败');toggleEngineMenu(false);});
        });
      }
      box.appendChild(it);
    });
    var note=$('engineNote');
    if(note)note.textContent=d.locked?'推理引擎由环境变量 MMH3_INFERENCE_BACKEND 锁定，暂不可切换。':'默认「本地 · diffusers」脱离 ComfyUI 即可运行；外部引擎需自行启动对应服务。';
  }).catch(function(){});
}
function checkHealth(){
  fetch(API_ORIGIN+'/api/health').then(function(r){return r.json();}).then(function(h){
    var c=$('connText');
    if(c)c.textContent='CONN: LOCAL · '+(h.model||'OK');
  }).catch(function(){
    var c=$('connText');
    if(c)c.textContent='CONN: 离线';
  });
}

/* ============ 事件绑定（事件委托为主） ============ */
document.addEventListener('click',function(e){
  var t=e.target&&e.target.closest?e.target.closest('.p-row .seg, .ref-size .seg, .ref-add, .neg, .pb-play, .fs-upload, .app-btn, .app-opt, #addSeg, .eng-switch, .sm-card, #smSkip, .history-btn, .tl-collapse, .icon-btn.mobile-only, .coll-btn, .edge-handle, #paramCollapseHeader'):null;
  if(!t)return;
  /* 折叠 / 抽屉 / 时间线收起（沿用既有交互） */
  if(t.classList.contains('tl-collapse')){
    var tl=$('timeline');
    tl.classList.toggle('collapsed');
    t.setAttribute('aria-expanded',tl.classList.contains('collapsed')?'false':'true');
    return;
  }
  if(t.classList.contains('mobile-only')){
    var lab=t.getAttribute('aria-label')||'';
    (lab.indexOf('参数')>-1?$('sideR'):$('sideL')).classList.add('open');
    var sc=$('scrim');if(sc)sc.classList.add('show');
    return;
  }
  if(t.classList.contains('coll-btn')||t.classList.contains('edge-handle')){
    var side=t.closest('.side-l, .side-r');
    if(!side)return;
    var isMobile=window.matchMedia('(max-width:1024px)').matches;
    if(isMobile){
      side.classList.toggle('open');
      var sc2=$('scrim');
      if(sc2)sc2.classList.toggle('show',side.classList.contains('open'));
      t.setAttribute('aria-expanded',side.classList.contains('open')?'true':'false');
    }else{
      side.classList.toggle('collapsed');
      var w=$('workzone');
      var workCls=side.classList.contains('side-l')?'coll-l':'coll-r';
      w.classList.toggle(workCls,side.classList.contains('collapsed'));
      t.setAttribute('aria-expanded',!side.classList.contains('collapsed')?'true':'false');
    }
    return;
  }
  /* 高级参数折叠面板 */
  if(t.id==='paramCollapseHeader'){
    var pcH=$('paramCollapseHeader');
    var pcB=$('paramCollapseBody');
    if(pcH&&pcB){
      var pcCollapsed=pcH.classList.toggle('collapsed');
      pcB.style.maxHeight=pcCollapsed?'0':'800px';
      pcB.style.opacity=pcCollapsed?'0':'1';
    }
    return;
  }
  /* 生成 */
  if(t.id==='addSeg'){
    addShot();return;
  }
  if(t.classList.contains('pb-play')){playDemo();return;}
  if(t.classList.contains('neg')){runContextIR();return;}
  /* 参考上传入口 */
  if(t.classList.contains('ref-add')){uploadRefs();return;}
  if(t.classList.contains('fs-upload')){uploadFrame(t.dataset.slot);return;}
  /* 外观菜单 */
  if(t.classList.contains('app-btn')){
    var m=$('appMenu');
    if(m){m.classList.toggle('open');}
    return;
  }
  if(t.classList.contains('app-opt')){
    if(t.dataset.app==='shell')applyShell(t.dataset.value,true);
    if(t.dataset.app==='theme')applyTheme(t.dataset.value,true);
    var m2=$('appMenu');
    if(m2)m2.classList.remove('open');
    return;
  }
  /* 引擎菜单 */
  if(t.classList.contains('eng-switch')){
    e.stopPropagation();
    toggleEngineMenu();
    return;
  }
  if(t.classList.contains('history-btn')){
    if(historyPanel)historyPanel.classList.toggle('open');
    return;
  }
  /* 参数 chip 单选 + 联动 */
  var group=t.parentNode;
  [].slice.call(group.children).forEach(function(c){c.classList.remove('on');});
  t.classList.add('on');
  var row=t.parentNode.parentNode;
  var k=row.querySelector?row.querySelector('.k'):null;
  if(k&&k.textContent==='画面比例'){
    var ratio=t.dataset.value||t.textContent.trim();
    previewShell.style.setProperty('--shell-ar',ratio);
    var dim=document.querySelector('.stage-mark .dim');
    if(dim)dim.textContent=ratio;
    var resPx=$('resPx');
    if(resPx){
      var pres=H3_RES_DEFAULT;
      document.querySelectorAll('.p-row').forEach(function(rr){var kk=rr.querySelector('.k');if(kk&&kk.textContent.trim()==='分辨率'){var so=rr.querySelector('.seg.on');if(so&&so.dataset.value)pres=so.dataset.value;}});
      var d=dimsForResolution(pres,ratio);
      resPx.innerHTML=ratio+' → <b>'+d[0]+'×'+d[1]+'</b> <em>'+pres+'MP</em>';
    }
  }
  if(k&&k.textContent==='分辨率'&&resPx){
    var aspEl=null;
    document.querySelectorAll('.p-row').forEach(function(rr){var kk=rr.querySelector('.k');if(kk&&kk.textContent.trim()==='画面比例')aspEl=rr.querySelector('.seg.on');});
    var asp=aspEl?aspEl.dataset.value:'16:9';
    var d=dimsForResolution(t.dataset.value,asp);
    resPx.innerHTML=asp+' → <b>'+d[0]+'×'+d[1]+'</b> <em>'+t.dataset.value+'MP</em>';
  }
  if(k&&k.textContent==='帧模式'&&PAGE.id==='i2v'){
    renderFrameSlots();
    var fm=t.dataset.value||'first_frame';
    var note=$('i2vNote');
    if(note){
      note.textContent=fm==='first_frame'?'首帧模式：上传 1 张图作为首帧，模型生成后续画面。':
        (fm==='last_frame'?'末帧模式：上传 1 张图作为末帧，模型由前向生成到该帧。':
        '首尾帧模式：上传 2 张图（首帧 + 末帧），模型生成两者之间的运动。');
    }
  }
  /* r2v：参考保真度说明随状态 */
  if(PAGE.id==='r2v'&&refNote){
    var m3=getActiveMode();
    refNote.textContent=(m3==='ref')?'已启用多模态参考：图 ≤9 · 视频 ≤3 · 音频 ≤3（混合 ≤12）；提示词按连接顺序用 <Picture 1>/<Video 1>/<Audio 1> 引用。':
      '首/末帧模式需上传对应图像；音频须搭配图像或视频输入。运镜由提示词驱动。';
  }
});
/* 点击外部关闭外观菜单 / 引擎菜单 / 项目下拉 / 抽屉 */
document.addEventListener('click',function(e){
  var m=$('appMenu');if(m&&m.classList.contains('open')&&!e.target.closest('.app-wrap'))m.classList.remove('open');
  var em=engineMenu;if(em&&em.classList.contains('open')&&!e.target.closest('.eng-switch'))toggleEngineMenu(false);
  if(projSwitch&&projSwitch.classList.contains('open')&&!e.target.closest('#projSwitch')){projSwitch.classList.remove('open');projSwitch.setAttribute('aria-expanded','false');}
  var sc=$('scrim');
  if(sc&&sc.classList.contains('show')&&e.target===sc){$('sideL').classList.remove('open');$('sideR').classList.remove('open');sc.classList.remove('show');}
});
/* 输入框事件 */
if(promptInput)promptInput.addEventListener('input',updateCount);
document.querySelectorAll('.preset').forEach(function(p){
  p.addEventListener('click',function(){promptInput.value=p.textContent.trim();updateCount();});
});
/* i2v / r2v 文件输入 */
var fsInput=$('fsInput');
if(fsInput){
  fsInput.addEventListener('change',function(){
    var files=Array.prototype.slice.call(fsInput.files||[]);
    var sid=activeShotId(),slot=fsInput.dataset.slot;
    fsInput.value='';
    if(!files.length||!sid)return;
    doUpload(files,sid,function(){
      /* 更新槽位映射并持久化到镜头 params */
      var map=i2vSlotsFor(sid);
      var seg=findShot(sid);
      var p={};try{p=JSON.parse(seg.dataset.params||'{}');}catch(e){}
      var latest=(SHOT_REFS[sid]||[]).filter(function(r){return r.kind==='image';});
      var lastImg=latest.length?latest[latest.length-1].id:null;
      if(slot==='first')map.first=lastImg;else map.last=lastImg;
      i2vMap[sid]=map;
      p.i2v=map;
      fetch(API_BASE+'/shots/'+sid,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({params:p})})
        .then(function(){return loadProjectShots(currentProjectId,sid);})
        .catch(function(){});
    });
  });
}
var refInput=$('refInput');
if(refInput){
  refInput.addEventListener('change',function(){
    var files=Array.prototype.slice.call(refInput.files||[]);
    var sid=activeShotId();
    refInput.value='';
    if(!files.length||!sid)return;
    doUpload(files,sid,function(){loadProjectShots(currentProjectId,sid);});
  });
}
/* r2v 配对音轨上传 */
var pairAudioInput=$('pairAudioInput');
if(pairAudioInput){
  pairAudioInput.addEventListener('change',function(){
    var files=Array.prototype.slice.call(pairAudioInput.files||[]);
    var sid=activeShotId(),pairedWith=pairAudioInput.dataset.pairedWith;
    pairAudioInput.value='';
    pairAudioInput.dataset.pairedWith='';
    if(!files.length||!sid||!pairedWith)return;
    doUpload(files,sid,function(){loadProjectShots(currentProjectId,sid);},pairedWith);
  });
}
/* 生成按钮 */
var genBtn=$('genBtn');
if(genBtn)genBtn.addEventListener('click',submitGeneration);

function addShot(){
  if(!currentProjectId){window.alert('请先新建或选择项目');return;}
  var body={name:'新镜头 '+(segs.length+1),prompt:promptInput.value||'',mode:getActiveMode(),duration:8,aspect:'16:9',params:{}};
  fetch(API_BASE+'/projects/'+currentProjectId+'/shots',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json();})
    .then(function(s){
      if(s.detail||!s.id){window.alert('创建镜头失败: '+(s.detail||'未知错误'));return;}
      loadProjectShots(currentProjectId,s.id);
    })
    .catch(function(){window.alert('创建镜头失败: 后端连接失败');});
}

/* ============ 初始化 ============ */
function init(){
  applyShell(currentShell,false);
  applyTheme(currentTheme,false);
  renderModeTabs();
  syncAppMenu();
  renderShellModal();
  /* 时长帧数徽标（17k+5 网格 @24fps） */
  document.querySelectorAll('.p-row .seg[data-value]').forEach(function(s){
    if(/^\d+s$/.test(s.dataset.value)){
      var em=document.createElement('em');
      em.textContent='·'+framesForDuration(parseInt(s.dataset.value,10))+'帧';
      s.appendChild(em);
    }
  });
  /* 种子随机按钮 */
  var sr=$('seedRand');
  if(sr)sr.addEventListener('click',function(){
    var si=$('seedInput');
    if(si)si.value=String(Math.floor(Math.random()*4294967296));
  });
  var qp=new URLSearchParams(location.search);
  var prefProject=qp.get('project'),prefShot=qp.get('shot');
  if(PAGE.id==='i2v')renderFrameSlots();
  checkHealth();
  loadEngines();
  setInterval(checkHealth,15000);
  loadProjects(prefProject,prefShot);
}
init();
})();

/* ===== 滑块联动（附加初始化）===== */
(function(){
  setTimeout(function(){
    var durSlider=document.getElementById('durationSlider'),durInput=document.getElementById('durationInput');
    if(durSlider&&durInput){
      durSlider.addEventListener('input',function(){durInput.value=durSlider.value;});
      durInput.addEventListener('change',function(){var v=parseInt(durInput.value,10);if(!isNaN(v)&&v>=4&&v<=15)durSlider.value=v;});
    }
    var stepsSlider=document.getElementById('stepsSlider'),stepsInput=document.getElementById('mainSteps');
    if(stepsSlider&&stepsInput){
      stepsSlider.addEventListener('input',function(){stepsInput.value=stepsSlider.value;});
      stepsInput.addEventListener('change',function(){var v=parseInt(stepsInput.value,10);if(!isNaN(v)&&v>=1&&v<=50)stepsSlider.value=v;});
    }
  },100);
  /* 清除 URL 参数避免误触发跨页跳转 */
  if(location.search){var newUrl=location.pathname+location.hash;window.history.replaceState({} ,'',newUrl);}
})();

/* ===== 折叠组件交互 ===== */
(function(){
  document.querySelectorAll('.fold-header').forEach(function(header){
    header.addEventListener('click', function(){
      var folded = this.dataset.folded === 'true';
      this.dataset.folded = !folded;
    });
  });
})();

/* ===== 折叠组件：同步显示当前选中值 + 展示壳宽高比联动 ===== */
(function(){
  /* 画面比例 → 展示壳宽高比（手机/平板/电视/电影屏等） */
  var SHELL_AR = {'21:9':'21/9','16:9':'16/9','4:3':'4/3','1:1':'1/1','3:4':'3/4','9:16':'9/16'};
  function applyShellAspect(aspect){
    var ps = document.querySelector('.preview-shell');
    if(!ps)return;
    var ar = SHELL_AR[aspect] || '16/9';
    ps.style.setProperty('--shell-ar', ar);
    /* 设备类型：竖屏手机 / 平板 / 其它（电视·放映机） */
    var device = 'tv';
    if(aspect === '9:16') device = 'phone';
    else if(aspect === '3:4' || aspect === '4:3' || aspect === '1:1') device = 'tablet';
    ps.classList.remove('device-phone','device-tablet','device-tv');
    ps.classList.add('device-' + device);
  }
  function syncAspectDisplay(){
    var currentEl = document.getElementById('aspectCurrent');
    var active = document.querySelector('#aspectFold .fold-body .seg.on');
    if(!active)return;
    if(currentEl){
      currentEl.textContent = active.dataset.value;
      currentEl.title = '当前选择：' + active.dataset.value;
    }
    applyShellAspect(active.dataset.value);
  }
  
  // 初始化时执行（延时确保 DOM 就绪）
  setTimeout(syncAspectDisplay, 100);
  
  // 监听点击事件
  var aspectBody = document.querySelector('#aspectFold .fold-body');
  if(aspectBody){
    aspectBody.addEventListener('click', function(e){
      if(e.target.classList.contains('seg')){
        this.querySelectorAll('.seg').forEach(function(s){s.classList.remove('on');});
        e.target.classList.add('on');
        syncAspectDisplay();
      }
    });
  }
})();

/* ===== LoRA 管理 ===== */
(function(){
  var loraSlots = [];
  var maxLoras = 6;
  
  function updateLoraCount(){
    var countEl = document.getElementById('loraCount');
    var activeCount = loraSlots.filter(function(s){return s&&s.name}).length;
    if(countEl)countEl.textContent = activeCount + '/' + maxLoras;
  }
  
  function renderLoraSlots(){
    var slots = document.querySelectorAll('.lora-slot');
    slots.forEach(function(slot){
      var idx = parseInt(slot.dataset.index, 10);
      var nameEl = slot.querySelector('.lora-slot-name');
      var btn = slot.querySelector('.lora-slot-btn');
      var rmBtn = slot.querySelector('.lora-remove') || createRemoveButton(slot);
      
      if(loraSlots[idx]&&loraSlots[idx].name){
        nameEl.textContent = loraSlots[idx].name;
        slot.classList.add('active');
        btn.style.display = 'none';
        rmBtn.style.display = 'block';
      }else{
        nameEl.textContent = '未选择';
        slot.classList.remove('active');
        btn.style.display = 'block';
        rmBtn.style.display = 'none';
      }
    });
    updateLoraCount();
  }
  
  function createRemoveButton(slot){
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lora-remove';
    btn.textContent = '✕ 移除';
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      var idx = parseInt(slot.dataset.index, 10);
      loraSlots[idx] = null;
      renderLoraSlots();
    });
    slot.appendChild(btn);
    return btn;
  }
  
  // 初始化
  setTimeout(function(){
    loraSlots = new Array(maxLoras).fill(null);
    renderLoraSlots();
    
    // 绑定点击事件
    document.querySelectorAll('.lora-slot-btn').forEach(function(btn){
      btn.addEventListener('click', function(){
        var idx = parseInt(this.dataset.slot, 10);
        var input = document.getElementById('loraInput');
        if(input){
          input.onchange = function(e){
            var files = e.target.files;
            if(files.length>0){
              var file = files[0];
              loraSlots[idx] = {name: file.name, file: file};
              renderLoraSlots();
            }
            input.value = '';
          };
          input.click();
        }
      });
    });
  }, 200);
})();


/* ===== 舞台显示控制（外观菜单：左上标签 / 右下角水印，含自定义水印文字）===== */
(function(){
  var tagsOpt = document.querySelector('.app-opt[data-app="stagetags"]');
  var hintOpt = document.querySelector('.app-opt[data-app="stagehint"]');
  var wmInput = document.getElementById('stageWatermarkInput');
  var hintEl = document.getElementById('stageHint');

  function setOn(opt, on){
    if(!opt) return;
    opt.classList.toggle('on', !!on);
    var desc = opt.querySelector('.ao-desc');
    if(desc) desc.textContent = on ? 'ON' : 'OFF';
  }
  function getOn(opt){
    return opt ? opt.classList.contains('on') : false;
  }
  function applyTags(){
    document.body.classList.toggle('ctrl-hide-tags', !getOn(tagsOpt));
  }
  function applyHint(){
    document.body.classList.toggle('ctrl-hide-text', !getOn(hintOpt));
  }
  function applyWatermark(){
    if(!hintEl) return;
    var custom = wmInput && wmInput.value.trim();
    if(custom){
      hintEl.textContent = custom;
      hintEl.title = '自定义水印';
    }else if(hintEl._default){
      hintEl.textContent = hintEl._default;
      hintEl.title = '';
    }
  }

  /* init：默认 标签=ON，水印=OFF；记录水印默认文案 */
  setOn(tagsOpt, true);
  setOn(hintOpt, false);
  if(hintEl && !hintEl._default) hintEl._default = hintEl.textContent;

  if(tagsOpt) tagsOpt.addEventListener('click', function(){ setOn(tagsOpt, !getOn(tagsOpt)); applyTags(); });
  if(hintOpt) hintOpt.addEventListener('click', function(){ setOn(hintOpt, !getOn(hintOpt)); applyHint(); });
  if(wmInput) wmInput.addEventListener('input', applyWatermark);

  setTimeout(function(){ applyTags(); applyHint(); applyWatermark(); }, 80);
})();
