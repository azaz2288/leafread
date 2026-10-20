// Keep raster galleries separate from text pagination/character progress.
const illustrationButton=document.createElement('button');
illustrationButton.id='illustrations-open';illustrationButton.className='btn secondary hidden';
illustrationButton.textContent='本章插图';readerTools.prepend(illustrationButton);
const illustrationDialog=document.createElement('dialog');
illustrationDialog.id='illustrations-dialog';illustrationDialog.setAttribute('aria-label','本章插图');
illustrationDialog.innerHTML='<div class="row"><h2>本章插图</h2><span class="spacer"></span><button class="btn secondary" id="illustrations-close">关闭插图</button></div><p class="small muted">栅格插图集中显示，不改变正文分页；保存整本离线副本后可离线查看。长章节拆分时插图位于原章节第一节。</p><div id="illustrations-content"></div>';
document.body.append(illustrationDialog);
let chapterIllustrations=[],illustrationVersion=0,illustrationRender=0;
let illustrationUrls=[];
const illustrationContent=document.querySelector('#illustrations-content');
function clearIllustrationRender(){
  illustrationRender++;
  illustrationUrls.splice(0).forEach(url=>URL.revokeObjectURL(url));
  illustrationContent.replaceChildren();
  illustrationContent.setAttribute('aria-busy','false');
}
function closeIllustrations(){
  clearIllustrationRender();
  if(illustrationDialog.open)illustrationDialog.close();
}
function resetIllustrations(){
  illustrationVersion++;chapterIllustrations=[];
  illustrationButton.classList.add('hidden');
  closeIllustrations();
}
document.querySelector('#illustrations-close').onclick=closeIllustrations;
illustrationDialog.addEventListener('cancel',clearIllustrationRender);
// Native close events are queued: an old one must not clear a reopened dialog.
illustrationDialog.addEventListener('close',()=>{if(!illustrationDialog.open)clearIllustrationRender();});
illustrationButton.onclick=guard(async()=>{
  if(!book||!chapterIllustrations.length)return;
  clearIllustrationRender();
  const render=illustrationRender,version=illustrationVersion,target=book.id,chapter=index,user=offlineUser;
  const values=chapterIllustrations.slice();
  function current(){
    if(render!==illustrationRender)return false;
    if(version!==illustrationVersion||book?.id!==target||index!==chapter||offlineUser!==user){closeIllustrations();return false;}
    return illustrationDialog.open;
  }
  readerSettings.close();
  const content=illustrationContent;
  content.textContent='正在加载插图，可随时关闭…';content.setAttribute('aria-busy','true');
  if(!illustrationDialog.open)illustrationDialog.showModal();
  let firstFigure=true;
  for(const value of values){
    if(!current())return;
    if(!Number.isInteger(value.ordinal)||value.ordinal<0)continue;
    const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');
    image.alt=value.alt||'本章插图';image.loading='lazy';image.width=value.width;image.height=value.height;
    image.style.cssText='display:block;max-width:100%;height:auto;margin:auto';
    caption.textContent=value.alt||`插图 ${value.ordinal+1} · ${value.width}×${value.height}`;
    const path=`/books/${encodeURIComponent(target)}/chapters/${chapter}/illustrations/${value.ordinal}`;
    try{
      const blob=await fetchIllustration(path);if(!current())return;
      const url=URL.createObjectURL(blob);illustrationUrls.push(url);image.src=url;
    }catch(error){
      if(!current())return;
      caption.textContent=error.status===404?'插图不存在':'插图加载失败，请先保存离线副本或联网重试';
    }
    if(firstFigure){content.replaceChildren();firstFigure=false;}
    figure.append(image,caption);content.append(figure);
  }
  if(current())content.setAttribute('aria-busy','false');
});
const chapterBeforeIllustrations=openChapter;
openChapter=async(...args)=>{
  resetIllustrations();const version=illustrationVersion,user=offlineUser,target=book?.id;
  await chapterBeforeIllustrations(...args);
  if(version!==illustrationVersion||!book||book.id!==target||offlineUser!==user)return;
  const chapter=index;
  try{
    const values=await api(`/books/${target}/chapters/${chapter}/illustrations`);
    if(version!==illustrationVersion||book?.id!==target||index!==chapter||offlineUser!==user)return;
    chapterIllustrations=values;
    illustrationButton.textContent=`本章插图（${values.length}）`;
    illustrationButton.classList.toggle('hidden',!values.length);
  }catch(error){
    if(version===illustrationVersion&&book?.id===target&&index===chapter&&offlineUser===user&&navigator.onLine)toast('插图目录加载失败，正文仍可阅读',true);
  }
};
const backBeforeIllustrations=document.querySelector('#back').onclick;
document.querySelector('#back').onclick=guard(async()=>{resetIllustrations();await backBeforeIllustrations();});
window.addEventListener('pagehide',resetIllustrations);
