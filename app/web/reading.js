// One chapter in the DOM; columns expose one screen at a time without cutting text.
let readingMode='pages', pageIndex=0, pageCount=1, pageStarts=[0], chapterText='', chapterRequest=0;
let readingPrefs={mode:'pages',line:'1.9',width:'720',toc:false}, layoutFrame=0;
try{readingPrefs={...readingPrefs,...JSON.parse(localStorage.getItem('leafread-reading')||'{}')};}catch{}
const readerViewport=document.createElement('div');readerViewport.id='page-viewport';
$('#body-text').before(readerViewport);readerViewport.append($('#body-text'));
const readerSettings=document.createElement('dialog');readerSettings.id='reader-settings';
readerSettings.setAttribute('aria-label','阅读设置');
readerSettings.innerHTML='<div class="row"><h2>阅读设置</h2><span class="spacer"></span><button class="btn secondary" id="settings-close">关闭</button></div><div class="settings-grid"><label>阅读方式<select id="read-mode" aria-label="阅读方式"><option value="pages">分页阅读</option><option value="scroll">滚动阅读</option></select></label><label id="theme-setting">阅读主题</label><label id="font-setting">字号</label><label>行距<select id="read-line" aria-label="行距"><option value="1.6">紧凑</option><option value="1.9">舒适</option><option value="2.2">宽松</option></select></label><label>正文宽度<select id="read-width" aria-label="正文宽度"><option value="560">窄</option><option value="720">适中</option><option value="900">宽</option></select></label></div><div class="row" id="reading-actions"><button class="btn secondary" id="focus-toggle">专注阅读</button><button class="btn secondary" id="fullscreen-toggle">全屏阅读</button></div><p class="small muted">左右滑动或点正文两侧翻页；键盘 ← →、PageUp / PageDown、空格翻页。Alt + ← → 切章。</p><h3>章节与工具</h3><div class="row" id="chapter-actions"></div><div class="row" id="book-actions"></div>';
document.body.append(readerSettings);
$('#theme-setting').append($('#theme'));$('#font-setting').append($('#font'));
['16','22','26','32'].forEach(value=>{const option=document.createElement('option');option.value=value;option.textContent=value+'px';$('#font').append(option);});
$('#chapter-actions').append($('#prev'),$('#next'));
$('#book-actions').append($('#bookmark'),readerTools,resolveSync,offlineButton);
const settingsButton=document.createElement('button');settingsButton.className='btn secondary';settingsButton.id='settings-open';settingsButton.textContent='设置';$('.reader-header').append(settingsButton);
settingsButton.onclick=()=>readerSettings.showModal();$('#settings-close').onclick=()=>readerSettings.close();
const tocClose=document.createElement('button');tocClose.className='btn secondary';tocClose.id='toc-close';tocClose.textContent='关闭目录';$('.reader-toc').prepend(tocClose);
const tocFilter=document.createElement('input');tocFilter.placeholder='筛选章节标题';tocFilter.setAttribute('aria-label','筛选章节标题');$('#chapters').before(tocFilter);
tocFilter.oninput=()=>$$('.chapter-link').forEach(el=>el.hidden=!el.textContent.toLowerCase().includes(tocFilter.value.toLowerCase()));
const tocBackdrop=document.createElement('button');tocBackdrop.id='toc-backdrop';tocBackdrop.setAttribute('aria-label','关闭目录');$('#reader').append(tocBackdrop);
function setToc(open){const position=book?ratio():0;$('#reader').classList.toggle('toc-open',open);$('.reader-toc').classList.toggle('open',open);$('.reader-toc').inert=!open;$('#toc-toggle').setAttribute('aria-expanded',String(open));$('#toc-toggle').textContent=open?'收起目录':'目录';readingPrefs.toc=open;rememberReading();if(open){requestAnimationFrame(()=>$('.chapter-link.active')?.scrollIntoView({block:'nearest'}));}else $('#toc-toggle').focus();if(book&&!loading)requestAnimationFrame(()=>layoutReading(position));}
$('#toc-toggle').setAttribute('aria-controls','reader-toc');$('#toc-toggle').onclick=()=>setToc(!$('#reader').classList.contains('toc-open'));
tocClose.onclick=tocBackdrop.onclick=()=>setToc(false);
const paging=document.createElement('nav');paging.id='page-controls';paging.setAttribute('aria-label','翻页');
paging.innerHTML='<button class="btn secondary" id="page-prev">← 上一页</button><span id="page-indicator" role="status" aria-live="polite"></span><button class="btn secondary" id="page-next">下一页 →</button>';
$('#reader').append(paging);paging.append($('#save-state'));
const focusExit=document.createElement('button');focusExit.id='focus-exit';focusExit.className='btn secondary';focusExit.textContent='退出专注';$('#reader').append(focusExit);
function focusReading(value){$('#reader').classList.toggle('focus-reading',value);$('#focus-toggle').textContent=value?'退出专注':'专注阅读';if(value){setToc(false);readerSettings.close();}}
$('#focus-toggle').onclick=()=>focusReading(!$('#reader').classList.contains('focus-reading'));focusExit.onclick=()=>focusReading(false);
$('#fullscreen-toggle').onclick=guard(async()=>{readerSettings.close();if(document.fullscreenElement)await document.exitFullscreen();else if($('#reader').requestFullscreen)await $('#reader').requestFullscreen();else toast('此浏览器不支持全屏，可使用专注阅读');});
function rememberReading(){try{localStorage.setItem('leafread-reading',JSON.stringify(readingPrefs));}catch{}}
function textRect(at){const node=$('#body-text').firstChild;if(!node||!chapterText.length)return null;const range=document.createRange();at=Math.max(0,Math.min(chapterText.length-1,at));range.setStart(node,at);range.setEnd(node,at+1);const rect=range.getBoundingClientRect();return rect;}
function firstOffset(predicate){let low=0,high=chapterText.length;while(low<high){const mid=Math.floor((low+high)/2);if(predicate(textRect(mid)))high=mid;else low=mid+1;}return low;}
function currentOffset(){if(readingMode==='pages')return pageStarts[pageIndex]||0;const top=$('.reader-header').getBoundingClientRect().bottom+12;return Math.min(chapterText.length-1,firstOffset(rect=>rect&&rect.bottom>=top));}
ratio=()=>Math.max(0,Math.min(1,currentOffset()/Math.max(1,chapterText.length-1)));
function updatePage(){
  const last=pageIndex===pageCount-1;
  $('#page-indicator').textContent=readingMode==='pages'?`第 ${index+1} 节 · ${pageIndex+1} / ${pageCount} 页`:`第 ${index+1} / ${book?.chapters.length||1} 节`;
  $('#page-prev').disabled=loading||(readingMode==='pages'&&pageIndex===0&&index===0)||(readingMode==='scroll'&&index===0);
  $('#page-next').disabled=loading||(readingMode==='pages'&&last&&index===book?.chapters.length-1)||(readingMode==='scroll'&&index===book?.chapters.length-1);
  $('#page-prev').textContent=readingMode==='scroll'?'← 上一章':'← 上一页';$('#page-next').textContent=readingMode==='scroll'?'下一章 →':'下一页 →';
  $('#body-text').style.transform=readingMode==='pages'?`translateX(${-pageIndex*(readerViewport.clientWidth+36)}px)`:'';
}
function layoutReading(position=ratio()){
  if(!book)return;readingMode=$('#read-mode').value;$('#reader').dataset.mode=readingMode;
  document.body.classList.toggle('paged-reading',readingMode==='pages');
  $('#reader').style.setProperty('--reading-width',$('#read-width').value+'px');
  $('#body-text').style.lineHeight=$('#read-line').value;
  const anchor=Math.round(Math.max(0,Math.min(1,position))*Math.max(0,chapterText.length-1));
  if(readingMode==='pages'){
    window.scrollTo(0,0);$('#body-text').style.transform='';
    readerViewport.style.height=Math.max(64,$('#page-controls').getBoundingClientRect().top-readerViewport.getBoundingClientRect().top-14)+'px';
    $('#body-text').style.columnWidth=readerViewport.clientWidth+'px';
    pageCount=Math.max(1,Math.round(($('#body-text').scrollWidth+36)/(readerViewport.clientWidth+36)));
    const left=$('#body-text').getBoundingClientRect().left,step=readerViewport.clientWidth+36;
    pageStarts=[0];for(let p=1;p<pageCount;p++)pageStarts.push(firstOffset(rect=>rect&&rect.left-left>=p*step-1));
    pageIndex=0;for(let p=0;p<pageStarts.length;p++)if(pageStarts[p]<=anchor)pageIndex=p;
  }else{
    readerViewport.style.height='';$('#body-text').style.transform='';$('#body-text').style.columnWidth='';pageCount=1;pageIndex=0;
    const rect=textRect(anchor);if(rect)window.scrollTo(0,Math.max(0,rect.top+scrollY-$('.reader-header').getBoundingClientRect().height-24));
  }
  updatePage();
}
async function turnPage(direction){if(!book||loading)return;const next=pageIndex+direction;if(readingMode==='scroll'){readerSettings.close();return openChapter(index+direction);}if(next>=0&&next<pageCount){pageIndex=next;updatePage();clearTimeout(saveTimer);await save();}else if(index+direction>=0&&index+direction<book.chapters.length){await openChapter(index+direction,direction<0?1:0);}}
$('#page-prev').onclick=guard(()=>turnPage(-1));$('#page-next').onclick=guard(()=>turnPage(1));
openChapter=async(next,position=0)=>{
  if(!book||loading&&chapterRequest>0||next<0||next>=book.chapters.length)return;
  clearTimeout(saveTimer);await save();loading=true;const request=++chapterRequest,target=book.id;updatePage();
  try{
    const chapter=await api('/books/'+target+'/chapters/'+next);if(request!==chapterRequest||book?.id!==target)return;
    index=next;chapterText=chapter.text;$('#chapter-number').textContent=`第 ${index+1} / ${book.chapters.length} 节`;
    $('#chapter-title').textContent=chapter.title;$('#body-text').textContent=chapterText;
    $('#prev').disabled=index===0;$('#next').disabled=index===book.chapters.length-1;
    $$('.chapter-link').forEach(el=>el.classList.toggle('active',Number(el.dataset.index)===index));
    if(matchMedia('(max-width:800px)').matches)setToc(false);
    readerSettings.close();await new Promise(resolve=>requestAnimationFrame(resolve));layoutReading(position);
    loading=false;updatePage();await persistPosition(target,{chapter:index,ratio:ratio()});
  }catch(error){loading=false;updatePage();throw error;}
};
const beforeReadingOpen=openBook;
openBook=async id=>{if(book&&book.id!==id&&!loading)await save();chapterRequest=0;chapterText='';tocFilter.value='';await beforeReadingOpen(id);setToc(!matchMedia('(max-width:800px)').matches&&readingPrefs.toc);};
const beforeReadingBack=$('#back').onclick;
$('#back').onclick=guard(async()=>{if(loading)return;focusReading(false);await beforeReadingBack();document.body.classList.remove('paged-reading');if(document.fullscreenElement)await document.exitFullscreen();});
function applyReadingSettings(){const position=book?ratio():0;settings();readingPrefs.mode=$('#read-mode').value;readingPrefs.line=$('#read-line').value;readingPrefs.width=$('#read-width').value;rememberReading();layoutReading(position);if(book&&!loading)guard(save)();}
['read-mode','read-line','read-width','theme','font'].forEach(id=>$('#'+id).onchange=applyReadingSettings);
if(['pages','scroll'].includes(readingPrefs.mode))$('#read-mode').value=readingPrefs.mode;
if(['1.6','1.9','2.2'].includes(readingPrefs.line))$('#read-line').value=readingPrefs.line;
if(['560','720','900'].includes(readingPrefs.width))$('#read-width').value=readingPrefs.width;
// Restore added font options that the old initialization did not recognize.
try{const prefs=JSON.parse(localStorage.getItem('leafread-settings')||'{}');if([...$('#font').options].some(o=>o.value===prefs.font))$('#font').value=prefs.font;}catch{}
window.addEventListener('resize',()=>{if(!book)return;const position=ratio();cancelAnimationFrame(layoutFrame);layoutFrame=requestAnimationFrame(()=>layoutReading(position));});
window.addEventListener('keydown',e=>{
  if(!book||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.target.isContentEditable)return;
  if(e.key==='Escape'){if(readerSettings.open)return; if($('#reader').classList.contains('toc-open'))setToc(false);else if($('#reader').classList.contains('focus-reading'))focusReading(false);return;}
  if(document.querySelector('dialog[open]'))return;
  if(['ArrowRight','PageDown','ArrowLeft','PageUp',' '].includes(e.key)){
    e.preventDefault();const direction=['ArrowLeft','PageUp'].includes(e.key)||e.key===' '&&e.shiftKey?-1:1;
    guard(()=>e.altKey?openChapter(index+direction):turnPage(direction))();
  }
});
let touchOrigin=null,lastSwipe=0;
readerViewport.addEventListener('touchstart',e=>{if(e.touches.length!==1)return;touchOrigin={x:e.touches[0].clientX,y:e.touches[0].clientY,time:Date.now()};},{passive:true});
readerViewport.addEventListener('touchend',e=>{if(!touchOrigin||readingMode!=='pages')return;const t=e.changedTouches[0],dx=t.clientX-touchOrigin.x,dy=t.clientY-touchOrigin.y;const duration=Date.now()-touchOrigin.time;touchOrigin=null;if(Math.abs(dx)>55&&Math.abs(dx)>Math.abs(dy)*1.5&&duration<800&&!getSelection()?.toString()){lastSwipe=Date.now();guard(()=>turnPage(dx<0?1:-1))();}},{passive:true});
readerViewport.addEventListener('click',e=>{if(Date.now()-lastSwipe<500||readingMode!=='pages'||getSelection()?.toString())return;const r=readerViewport.getBoundingClientRect(),x=(e.clientX-r.left)/r.width;if(x<.18)guard(()=>turnPage(-1))();else if(x>.82)guard(()=>turnPage(1))();});
$('#reader').classList.remove('toc-open');$('.reader-toc').classList.remove('open');$('.reader-toc').inert=true;$('#toc-toggle').setAttribute('aria-expanded','false');
