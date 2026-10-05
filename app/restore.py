import hashlib,json,time,uuid
from fastapi import HTTPException,Request,UploadFile,File
from .common import database,read_upload

def install_restore(app,root,identity):
    @app.post('/api/library/restore-backup')
    def restore(request:Request,file:UploadFile=File(...)):
        raw=read_upload(file,256*1024*1024)
        try:
            body=json.loads(raw);books=body['books']
            if body['version']!=1 or not isinstance(books,list) or len(books)>300:raise ValueError()
            checked=[];characters=0
            for book in books:
                chapters=book['chapters'];title=book['title']
                if not isinstance(title,str) or not 0<len(title)<=150 or not isinstance(chapters,list) or not 0<len(chapters)<=100000:raise ValueError()
                for index,c in enumerate(chapters):
                    if c['idx']!=index or not isinstance(c['title'],str) or len(c['title'])>150 or not isinstance(c['text'],str) or len(c['text'])>12000:raise ValueError()
                    characters+=len(c['text'])
                if characters>150_000_000:raise ValueError()
                chapter=book.get('chapter',0);ratio=book.get('ratio',0)
                if not isinstance(chapter,int) or not 0<=chapter<len(chapters) or not isinstance(ratio,(int,float)) or not 0<=ratio<=1:raise ValueError()
                marks=book.get('bookmarks',[]);notes=book.get('annotations',[])
                if len(marks)+len(notes)>10000:raise ValueError()
                for m in marks:
                    if not isinstance(m['chapter'],int) or not 0<=m['chapter']<len(chapters) or not isinstance(m['ratio'],(float,int)) or not 0<=m['ratio']<=1 or not isinstance(m['note'],str) or len(m['note'])>2000:raise ValueError()
                for n in notes:
                    if not isinstance(n['chapter'],int) or not 0<=n['chapter']<len(chapters) or not isinstance(n['quote'],str) or not n['quote'] or len(n['quote'])>2000 or n['quote'] not in chapters[n['chapter']]['text'] or not isinstance(n['note'],str) or len(n['note'])>2000:raise ValueError()
                checked.append((book,chapters,marks,notes))
        except (ValueError,KeyError,TypeError,IndexError):raise HTTPException(400,'备份格式或位置/笔记无效；未写入任何书籍') from None
        count=0;user=identity(request)['id']
        with database(root) as db:
            for book,chapters,marks,notes in checked:
                text='\n'.join(c['title']+'\n'+c['text'] for c in chapters);digest=hashlib.sha256((user+'\n'+text).encode()).hexdigest()
                if db.execute('SELECT 1 FROM books WHERE digest=?',(digest,)).fetchone():continue
                ident=uuid.uuid4().hex;db.execute('INSERT INTO books(id,title,digest,encoding,characters,created,chapter,ratio,owner) VALUES(?,?,?,?,?,?,?,?,?)',(ident,book['title'],digest,'restored',len(text),time.time(),book.get('chapter',0),book.get('ratio',0),user))
                db.executemany('INSERT INTO chapters VALUES(?,?,?,?)',[(ident,i,c['title'],c['text']) for i,c in enumerate(chapters)])
                for m in marks:db.execute('INSERT INTO bookmarks VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ident,m['chapter'],m['ratio'],m['note'],time.time()))
                for n in notes:db.execute('INSERT INTO annotations VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ident,n['chapter'],n['quote'],n['note'],time.time()))
                count+=1
        return {'imported':count,'note':'作为当前用户的新书导入，不覆盖已有记录'}
