// Keep raster galleries separate from text pagination/character progress.
const illustrationButton=document.createElement('button');
illustrationButton.id='illustrations-open';illustrationButton.className='btn secondary hidden';
illustrationButton.textContent='本章插图';readerTools.prepend(illustrationButton);
const illustrationDialog=document.createElement('dialog');
illustrationDialog.id='illustrations-dialog';illustrationDialog.setAttribute('aria-label','本章插图');
illustrationDialog.innerHTML='<div class="row"><h2>本章插图</h2><span class="spacer"></span><button class="btn secondary" id="illustrations-close">关闭插图</button></div><p class="small muted">栅格插图集中显示，不改变正文分页；插图暂需联网。长章节拆分时插图位于原章节第一节。</p><div id="illustrations-content"></div>';
document.body.append(illustrationDialog);
let chapterIllustrations=[],illustrationVersion=0;
function resetIllustrations(){
  illustrationVersion++;chapterIllustrations=[];
  illustrationButton.classList.add('hidden');
  if(illustrationDialog.open)illustrationDialog.close();
  document.querySelector('#illustrations-content').replaceChildren();
}
document.querySelector('#illustrations-close').onclick=()=>illustrationDialog.close();
illustrationDialog.addEventListener('close',()=>document.querySelector('#illustrations-content').replaceChildren());
illustrationButton.onclick=guard(async()=>{
  if(!book||!chapterIllustrations.length)return;
  if(!navigator.onLine)return toast('正文可离线阅读，插图暂需联网',true);
  readerSettings.close();
  const content=document.querySelector('#illustrations-content');content.replaceChildren();
  for(const value of chapterIllustrations){
    if(!Number.isInteger(value.ordinal)||value.ordinal<0)continue;
    const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');
    image.src=`/api/books/${encodeURIComponent(book.id)}/chapters/${index}/illustrations/${value.ordinal}`;
    image.alt=value.alt||'本章插图';image.loading='lazy';image.width=value.width;image.height=value.height;
    image.style.cssText='display:block;max-width:100%;height:auto;margin:auto';
    caption.textContent=value.alt||`插图 ${value.ordinal+1} · ${value.width}×${value.height}`;
    image.onerror=()=>{caption.textContent='插图加载失败，请联网后重试';};
    figure.append(image,caption);content.append(figure);
  }
  illustrationDialog.showModal();
});
const chapterBeforeIllustrations=openChapter;
openChapter=async(...args)=>{
  resetIllustrations();await chapterBeforeIllustrations(...args);
  if(!book)return;
  const target=book.id,chapter=index,version=illustrationVersion;
  try{
    const values=await api(`/books/${target}/chapters/${chapter}/illustrations`);
    if(version!==illustrationVersion||book?.id!==target||index!==chapter)return;
    chapterIllustrations=values;
    illustrationButton.textContent=`本章插图（${values.length}）`;
    illustrationButton.classList.toggle('hidden',!values.length);
  }catch(error){
    if(navigator.onLine)toast('插图目录加载失败，正文仍可阅读',true);
  }
};
const backBeforeIllustrations=document.querySelector('#back').onclick;
document.querySelector('#back').onclick=guard(async()=>{resetIllustrations();await backBeforeIllustrations();});
