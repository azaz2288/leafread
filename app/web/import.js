let maxBookBytes=128*1024*1024;
const encodingControl=document.createElement('select');
encodingControl.id='import-encoding';encodingControl.setAttribute('aria-label','导入编码');
encodingControl.className='btn secondary';
const encodingOptions=[['auto','自动识别编码'],['utf-8','UTF-8'],['gb18030','GB18030 / GBK'],['big5','Big5 繁体中文'],['big5hkscs','Big5 香港增补'],['utf-16-le','UTF-16 小端'],['utf-16-be','UTF-16 大端'],['utf-32-le','UTF-32 小端'],['utf-32-be','UTF-32 大端'],['cp1252','Windows-1252'],['shift_jis','Shift-JIS 日文']];
encodingControl.innerHTML=encodingOptions.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');
document.querySelector('.file-label').before(encodingControl);
const importResult=document.createElement('p');importResult.className='small muted';
importResult.id='import-result';importResult.setAttribute('role','status');
document.querySelector('#library .toolbar').after(importResult);
async function loadImportLimits(){
  const value=await api('/config');maxBookBytes=value.max_upload_bytes;
  const footer=document.querySelector('#library footer');
  if(footer)footer.textContent=`TXT / EPUB · 自动识别UTF、GBK/GB18030、Big5等编码并转换 · 当前单本上限 ${Math.round(maxBookBytes/1024/1024)}MiB · 保留原文件`;
}
guard(loadImportLimits)();
$('#file').onchange=guard(async()=>{
  const file=$('#file').files[0];if(!file)return;
  if(file.size>maxBookBytes){$('#file').value='';throw Error(`文件${(file.size/1024/1024).toFixed(1)}MiB，超过当前${maxBookBytes/1024/1024}MiB限制；可配置LEAFREAD_MAX_UPLOAD_MIB`);}
  const body=new FormData();body.append('file',file);$('#file').disabled=true;encodingControl.disabled=true;
  importResult.textContent='正在上传并自动转换编码…';toast('正在上传，完成后解析章节并建立索引…');
  try{
    const result=await new Promise((resolve,reject)=>{
      const req=new XMLHttpRequest();req.open('POST','/api/books?encoding_hint='+encodeURIComponent(encodingControl.value));
      req.upload.onprogress=e=>{if(e.lengthComputable)toast(`上传 ${Math.round(e.loaded/e.total*100)}%；随后转换编码、解析章节和索引`);};
      req.onload=()=>{let result;try{result=JSON.parse(req.responseText);}catch{result={};}if(req.status>=200&&req.status<300)resolve(result);else reject(Error(result.detail||'导入失败'));};
      req.onerror=()=>reject(Error('连接失败，书籍未完成导入'));req.send(body);
    });
    importResult.textContent=`“${result.title}”导入完成 · 编码 ${result.detected_encoding||result.encoding} · ${result.characters.toLocaleString()}字 · ${result.chapters.length}节${result.removed_null_characters?' · 已自动移除 '+result.removed_null_characters+' 个空字符':''} · 原文件保留`;
    toast('编码已自动处理，导入完成');await library();
  }catch(error){importResult.textContent=error.message;throw error;}
  finally{$('#file').disabled=false;encodingControl.disabled=false;$('#file').value='';}
});
