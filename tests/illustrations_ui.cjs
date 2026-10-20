const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync('app/web/illustrations.js','utf8');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function fixture(body){
  const nodes=new Map(),created=[],revoked=[],requests=[],notices=[],windowEvents={};
  class Element{
    constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.open=false;this.textContent='';this.classList={add(){},toggle(){}};this.style={};}
    set id(id){this._id=id;nodes.set('#'+id,this);} get id(){return this._id;}
    set textContent(value){this._text=value;this.children=[];}
    get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
    set innerHTML(_){for(const id of ['illustrations-close','illustrations-content'])if(!nodes.has('#'+id)){const node=new Element('div');node.id=id;}}
    setAttribute(){} prepend(...values){this.children.unshift(...values);} append(...values){this.children.push(...values);}
    replaceChildren(...values){this.children=values;this.textContent='';}
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    dispatch(type){for(const fn of this.listeners[type]??[])fn({type});}
    showModal(){this.open=true;} close(){if(this.open){this.open=false;this.queuedClose=true;}}
  }
  const back=new Element('button');back.id='back';
  const context={book:{id:'a'},index:0,offlineUser:'local',navigator:{onLine:true},readerTools:new Element('div'),readerSettings:{close(){}},
    document:{createElement:tag=>new Element(tag),body:new Element('body'),querySelector:id=>nodes.get(id)},
    URL:{createObjectURL:blob=>{const url='blob:synthetic-'+created.length;created.push({url,blob});return url;},revokeObjectURL:url=>revoked.push(url)},
    guard:fn=>fn,toast:(...args)=>notices.push(args),window:{addEventListener(type,fn){windowEvents[type]=fn;}},
    api:async()=>[{ordinal:0,alt:'原创甲',width:96,height:64}],
    fetchIllustration:path=>{requests.push(path);return Promise.resolve({path});},
    openChapter:async next=>{if(body)await body();context.index=next;},
  };
  back.onclick=async()=>{context.book=null;};
  vm.createContext(context);vm.runInContext(source,context);
  return {context,nodes,created,revoked,requests,notices,windowEvents,
    button:()=>nodes.get('#illustrations-open'),dialog:()=>nodes.get('#illustrations-dialog'),content:()=>nodes.get('#illustrations-content'),
    flushClose(){const dialog=nodes.get('#illustrations-dialog');if(dialog.queuedClose){dialog.queuedClose=false;dialog.dispatch('close');}},
    async load(){await context.openChapter(0);},
  };
}
test('late first image after return cannot reopen gallery or create a Blob URL',async()=>{
  const f=fixture();await f.load();const wait=deferred();f.context.fetchIllustration=()=>wait.promise;
  const pending=f.button().onclick();await f.nodes.get('#back').onclick();wait.resolve({old:true});await pending;
  assert.equal(f.dialog().open,false);assert.equal(f.content().children.length,0);assert.equal(f.created.length,0);
});
test('chapter switch during image load never issues a mixed next-chapter request',async()=>{
  const f=fixture();f.context.api=async()=>[{ordinal:0},{ordinal:1}];await f.load();const wait=deferred();const paths=[];
  f.context.fetchIllustration=path=>{paths.push(path);return wait.promise;};const pending=f.button().onclick();
  await f.context.openChapter(1);wait.resolve({});await pending;
  assert.deepEqual(paths,['/books/a/chapters/0/illustrations/0']);assert.equal(f.created.length,0);assert.equal(f.dialog().open,false);
});
test('loading gallery can be closed and delayed response cannot reopen it',async()=>{
  const f=fixture();await f.load();const wait=deferred();f.context.fetchIllustration=()=>wait.promise;
  const pending=f.button().onclick();assert.equal(f.dialog().open,true);f.nodes.get('#illustrations-close').onclick();f.flushClose();
  wait.resolve({});await pending;assert.equal(f.dialog().open,false);assert.equal(f.created.length,0);
});
test('completed close releases each URL exactly once and reopening uses fresh URLs',async()=>{
  const f=fixture();await f.load();await f.button().onclick();assert.equal(f.created.length,1);
  f.nodes.get('#illustrations-close').onclick();f.flushClose();assert.deepEqual(f.revoked,[f.created[0].url]);
  await f.button().onclick();assert.equal(f.dialog().open,true);assert.equal(f.content().children.length,1);assert.equal(f.created.length,2);
  f.context.resetIllustrations();f.flushClose();assert.deepEqual(f.revoked,f.created.map(x=>x.url));
});
test('second click supersedes earlier render without stale append or URL release',async()=>{
  const f=fixture();await f.load();const first=deferred();let calls=0;f.context.fetchIllustration=()=>++calls===1?first.promise:Promise.resolve({new:true});
  const pending=f.button().onclick();await f.button().onclick();first.resolve({old:true});await pending;
  assert.equal(f.created.length,1);assert.equal(f.created[0].blob.new,true);assert.equal(f.content().children.length,1);assert.equal(f.revoked.length,0);
});
test('queued close from prior dialog does not erase a newly opened gallery',async()=>{
  const f=fixture();await f.load();await f.button().onclick();f.nodes.get('#illustrations-close').onclick();
  await f.button().onclick();f.flushClose();assert.equal(f.dialog().open,true);assert.equal(f.content().children.length,1);assert.equal(f.revoked.length,1);
});
test('late failure after navigation is discarded while current failure is visible',async()=>{
  const f=fixture();await f.load();const wait=deferred();f.context.fetchIllustration=()=>wait.promise;
  const pending=f.button().onclick();await f.nodes.get('#back').onclick();wait.reject(new Error('synthetic failure'));await pending;
  assert.equal(f.dialog().open,false);assert.equal(f.content().children.length,0);
  f.context.book={id:'a'};await f.load();f.context.fetchIllustration=async()=>{const e=new Error('absent');e.status=404;throw e;};
  await f.button().onclick();assert.equal(f.dialog().open,true);assert.match(f.content().children[0].children[1].textContent,/不存在/);assert.equal(f.created.length,0);
});
test('metadata awaiting chapter body is invalidated by return and same-book reentry',async()=>{
  const wait=deferred();let bodies=0,calls=0;const f=fixture(()=>++bodies===1?wait.promise:Promise.resolve());
  f.context.api=async()=>[{ordinal:++calls===1?1:0}];
  const first=f.context.openChapter(0);await new Promise(resolve=>setImmediate(resolve));
  await f.nodes.get('#back').onclick();f.context.book={id:'a'};await f.context.openChapter(0);
  wait.resolve();await first;await f.button().onclick();assert.equal(calls,1);assert.match(f.requests[0],/illustrations\/1$/);
});
test('navigation after first successful image reclaims partial URLs and skips remaining requests',async()=>{
  const f=fixture();f.context.api=async()=>[{ordinal:0},{ordinal:1},{ordinal:2}];await f.load();const wait=deferred();let calls=0;
  f.context.fetchIllustration=()=>++calls===1?Promise.resolve({first:true}):wait.promise;const pending=f.button().onclick();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.created.length,1);await f.nodes.get('#back').onclick();wait.resolve({late:true});await pending;
  assert.equal(calls,2);assert.equal(f.created.length,1);assert.deepEqual(f.revoked,f.created.map(x=>x.url));assert.equal(f.dialog().open,false);
});
test('account identity changes while image loads discard old render',async()=>{
  const f=fixture();await f.load();const wait=deferred();f.context.fetchIllustration=()=>wait.promise;const pending=f.button().onclick();
  f.context.offlineUser='another';wait.resolve({old:true});await pending;assert.equal(f.created.length,0);assert.equal(f.content().children.length,0);
});

test('loading-label alt text cannot erase an earlier figure in a multi-image gallery',async()=>{
  const f=fixture();f.context.api=async()=>[{ordinal:0,alt:'正在加载插图，可随时关闭…'},{ordinal:1,alt:'第二张'}];
  await f.load();await f.button().onclick();assert.equal(f.content().children.length,2);assert.equal(f.created.length,2);
});

test('Escape cancellation releases partial URLs and discards the waiting image',async()=>{
  const f=fixture();f.context.api=async()=>[{ordinal:0},{ordinal:1}];await f.load();const wait=deferred();let calls=0;
  f.context.fetchIllustration=()=>++calls===1?Promise.resolve({}):wait.promise;
  const pending=f.button().onclick();await new Promise(resolve=>setImmediate(resolve));
  f.dialog().dispatch('cancel');f.dialog().close();f.flushClose();wait.resolve({});await pending;
  assert.equal(f.created.length,1);assert.deepEqual(f.revoked,f.created.map(x=>x.url));assert.equal(f.dialog().open,false);
});

test('out-of-order metadata and stale failure cannot replace or toast the current chapter',async()=>{
  const f=fixture(),wait=deferred();let calls=0;f.context.api=()=>++calls===1?wait.promise:Promise.resolve([{ordinal:3}]);
  const pending=f.context.openChapter(0);await new Promise(resolve=>setImmediate(resolve));await f.context.openChapter(1);
  wait.reject(new Error('old catalogue'));await pending;await f.button().onclick();
  assert.deepEqual(f.requests,['/books/a/chapters/1/illustrations/3']);assert.equal(f.notices.length,0);
});

test('pagehide releases loaded URLs and prevents pending images from being appended',async()=>{
  const f=fixture();await f.load();await f.button().onclick();f.windowEvents.pagehide();f.flushClose();
  assert.deepEqual(f.revoked,f.created.map(x=>x.url));assert.equal(f.content().children.length,0);assert.equal(f.dialog().open,false);
});
