from pathlib import Path
import hashlib
import time
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from .common import prepare,mount_ui,database,data_root,read_upload,decode_text
from .chapters import parse_chapters


class Position(BaseModel):
    chapter: int=Field(ge=0)
    ratio: float=Field(ge=0,le=1,allow_inf_nan=False)


class Bookmark(Position):
    note: str=Field('',max_length=200)


def create_app(root=None):
    root=Path(root or data_root('leafread'))
    app=prepare(FastAPI(title='LeafRead',version='0.1.0'),root)
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS books(id TEXT PRIMARY KEY,title TEXT,digest TEXT UNIQUE,encoding TEXT,characters INTEGER,created REAL,chapter INTEGER DEFAULT 0,ratio REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS chapters(book_id TEXT REFERENCES books(id) ON DELETE CASCADE,idx INTEGER,title TEXT,text TEXT,PRIMARY KEY(book_id,idx));
        CREATE TABLE IF NOT EXISTS bookmarks(id TEXT PRIMARY KEY,book_id TEXT REFERENCES books(id) ON DELETE CASCADE,chapter INTEGER,ratio REAL,note TEXT,created REAL);''')

    def book(db,ident):
        row=db.execute('SELECT * FROM books WHERE id=?',(ident,)).fetchone()
        if not row: raise HTTPException(404,'书籍不存在')
        value=dict(row)
        value['chapters']=[dict(r) for r in db.execute('SELECT idx,title,length(text) AS characters FROM chapters WHERE book_id=? ORDER BY idx',(ident,))]
        return value

    @app.get('/api/books')
    def books(q:str=Query('',max_length=100)):
        with database(root) as db:
            return [dict(r) for r in db.execute('SELECT b.*, (SELECT count(*) FROM chapters c WHERE c.book_id=b.id) AS chapter_count FROM books b WHERE instr(lower(title),lower(?))>0 ORDER BY created DESC',(q,))]

    @app.post('/api/books',status_code=201)
    def upload(file:UploadFile=File(...)):
        if Path(file.filename or '').suffix.lower()!='.txt':raise HTTPException(400,'请导入TXT文件')
        raw=read_upload(file,10*1024*1024);text,encoding=decode_text(raw)
        text=text.strip()
        if not text:raise HTTPException(400,'书籍正文为空')
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
        chapters=parse_chapters(text)
        if not chapters:raise HTTPException(400,'没有可阅读的正文')
        with database(root) as db:
            row=db.execute('SELECT id FROM books WHERE digest=?',(digest,)).fetchone()
            if row:return {**book(db,row['id']),'duplicate':True}
            ident=uuid.uuid4().hex
            title=Path(file.filename.replace('\\','/')).stem[:150]
            db.execute('INSERT INTO books(id,title,digest,encoding,characters,created) VALUES(?,?,?,?,?,?)',(ident,title,digest,encoding,len(text),time.time()))
            db.executemany('INSERT INTO chapters VALUES(?,?,?,?)',[(ident,i,t,b) for i,(t,b) in enumerate(chapters)])
            return {**book(db,ident),'duplicate':False}

    @app.get('/api/books/{ident}')
    def detail(ident:str):
        with database(root) as db:return book(db,ident)

    @app.get('/api/books/{ident}/chapters/{index}')
    def chapter(ident:str,index:int):
        with database(root) as db:
            row=db.execute('SELECT * FROM chapters WHERE book_id=? AND idx=?',(ident,index)).fetchone()
            if not row:raise HTTPException(404,'章节不存在')
            return dict(row)

    def check_position(db,ident,body):
        if not db.execute('SELECT 1 FROM chapters WHERE book_id=? AND idx=?',(ident,body.chapter)).fetchone():
            raise HTTPException(400,'阅读位置不在书籍章节范围内')

    @app.post('/api/books/{ident}/progress')
    def progress(ident:str,body:Position):
        with database(root) as db:
            check_position(db,ident,body)
            db.execute('UPDATE books SET chapter=?,ratio=? WHERE id=?',(body.chapter,body.ratio,ident))
        return {'ok':True}

    @app.get('/api/books/{ident}/bookmarks')
    def bookmarks(ident:str):
        with database(root) as db:
            book(db,ident)
            return [dict(r) for r in db.execute('SELECT m.*,c.title FROM bookmarks m JOIN chapters c ON c.book_id=m.book_id AND c.idx=m.chapter WHERE m.book_id=? ORDER BY m.created DESC',(ident,))]

    @app.post('/api/books/{ident}/bookmarks',status_code=201)
    def add_bookmark(ident:str,body:Bookmark):
        with database(root) as db:
            check_position(db,ident,body);key=uuid.uuid4().hex
            db.execute('INSERT INTO bookmarks VALUES(?,?,?,?,?,?)',(key,ident,body.chapter,body.ratio,body.note.strip(),time.time()))
        return {'id':key}

    @app.delete('/api/books/{ident}/bookmarks/{key}')
    def remove_bookmark(ident:str,key:str):
        with database(root) as db:
            cursor=db.execute('DELETE FROM bookmarks WHERE id=? AND book_id=?',(key,ident))
            if cursor.rowcount==0:raise HTTPException(404,'书签不存在')
        return {'ok':True}

    @app.get('/api/books/{ident}/search')
    def search(ident:str,q:str=Query(...,min_length=1,max_length=100)):
        with database(root) as db:
            book(db,ident)
            rows=db.execute('SELECT idx,title,text FROM chapters WHERE book_id=? AND instr(lower(text),lower(?))>0 LIMIT 50',(ident,q))
            results=[]
            for row in rows:
                pos=row['text'].lower().find(q.lower())
                results.append({'chapter':row['idx'],'title':row['title'],'excerpt':row['text'][max(0,pos-40):pos+len(q)+100],'ratio':pos/max(1,len(row['text']))})
            return results

    mount_ui(app);return app


app=create_app()
