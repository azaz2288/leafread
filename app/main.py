from pathlib import Path
from .accounts import install_accounts
import hashlib
import os
from .epub import parse_epub_details
from .illustrations import install_illustrations,save_images,content_digest
from .library import install_library
from .restore import install_restore
import time
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from pydantic import BaseModel, Field
from .common import prepare,mount_ui,database,data_root,read_upload
from .text_encoding import decode_text_details,IMPORT_ENCODINGS
from .chapters import parse_chapters


class Position(BaseModel):
    chapter: int=Field(ge=0)
    ratio: float=Field(ge=0,le=1,allow_inf_nan=False)


class Bookmark(Position):
    note: str=Field('',max_length=200)


def create_app(root=None):
    root=Path(root or data_root('leafread'))
    app=prepare(FastAPI(title='LeafRead',version='0.2.1'),root)
    identity=install_accounts(app,root)
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS books(id TEXT PRIMARY KEY,title TEXT,digest TEXT UNIQUE,encoding TEXT,characters INTEGER,created REAL,chapter INTEGER DEFAULT 0,ratio REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS chapters(book_id TEXT REFERENCES books(id) ON DELETE CASCADE,idx INTEGER,title TEXT,text TEXT,PRIMARY KEY(book_id,idx));
        CREATE TABLE IF NOT EXISTS bookmarks(id TEXT PRIMARY KEY,book_id TEXT REFERENCES books(id) ON DELETE CASCADE,chapter INTEGER,ratio REAL,note TEXT,created REAL);''')

    with database(root) as db:
        for column,ddl in [('owner',"TEXT DEFAULT 'local'"),('deleted','INTEGER DEFAULT 0')]:
            if column not in {r[1] for r in db.execute('PRAGMA table_info(books)')}:db.execute(f'ALTER TABLE books ADD COLUMN {column} {ddl}')
    install_illustrations(app,root,identity)
    install_library(app,root,identity)
    install_restore(app,root,identity)
    max_upload=int(os.getenv('LEAFREAD_MAX_UPLOAD_MIB','128'))*1024*1024
    if max_upload<1024*1024 or max_upload>1024**3:raise ValueError('LEAFREAD_MAX_UPLOAD_MIB must be between 1 and 1024')
    @app.get('/api/config')
    def config():return {'max_upload_bytes':max_upload,'formats':['.txt','.epub'],'import_encodings':IMPORT_ENCODINGS}
    def book(db,ident,user='local'):
        row=db.execute('SELECT * FROM books WHERE id=?',(ident,)).fetchone()
        if not row or row['owner']!=user or row['deleted']: raise HTTPException(404,'书籍不存在或没有权限')
        value=dict(row)
        value['chapters']=[dict(r) for r in db.execute('SELECT idx,title,length(text) AS characters FROM chapters WHERE book_id=? ORDER BY idx',(ident,))]
        return value

    @app.get('/api/books')
    def books(request:Request,q:str=Query('',max_length=100)):
        with database(root) as db:
            return [dict(r) for r in db.execute('SELECT b.*, (SELECT count(*) FROM chapters c WHERE c.book_id=b.id) AS chapter_count FROM books b WHERE instr(lower(title),lower(?))>0 AND owner=? AND deleted=0 ORDER BY created DESC',(q,identity(request)['id']))]

    @app.post('/api/books',status_code=201)
    def upload(request:Request,file:UploadFile=File(...),encoding_hint:str=Query('auto',max_length=30)):
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in {'.txt','.epub'}:raise HTTPException(400,'请导入TXT或EPUB文件')
        raw=read_upload(file,max_upload)
        removed_nulls=0;images=[];image_warnings=[]
        if suffix=='.epub':
            epub_title,chapters,images,image_warnings=parse_epub_details(raw);text='\n'.join(t+'\n'+b for t,b in chapters);encoding='EPUB UTF-8'
        else:
            decoded=decode_text_details(raw,encoding_hint)
            text,encoding=decoded.text,decoded.encoding;removed_nulls=decoded.removed_null_characters
            chapters=parse_chapters(text)
        text=text.strip()
        if not text:raise HTTPException(400,'书籍正文为空')
        digest=content_digest(identity(request)['id'],text,images)
        if not chapters:raise HTTPException(400,'没有可阅读的正文')
        with database(root) as db:
            row=db.execute('SELECT id FROM books WHERE digest=?',(digest,)).fetchone()
            if row:
                db.execute('UPDATE books SET deleted=0 WHERE id=?',(row['id'],));return {**book(db,row['id'],identity(request)['id']),'duplicate':True,'removed_null_characters':removed_nulls,'detected_encoding':encoding,'illustration_count':len(images),'illustration_warnings':image_warnings}
            ident=uuid.uuid4().hex
            title=epub_title[:150] if suffix=='.epub' else Path(file.filename.replace('\\','/')).stem[:150]
            db.execute('INSERT INTO books(id,title,digest,encoding,characters,created,owner) VALUES(?,?,?,?,?,?,?)',(ident,title,digest,encoding,len(text),time.time(),identity(request)['id']))
            db.executemany('INSERT INTO chapters VALUES(?,?,?,?)',[(ident,i,t,b) for i,(t,b) in enumerate(chapters)])
            save_images(db,ident,images)
            return {**book(db,ident,identity(request)['id']),'duplicate':False,'removed_null_characters':removed_nulls,'detected_encoding':encoding,'illustration_count':len(images),'illustration_warnings':image_warnings}

    @app.get('/api/books/{ident}')
    def detail(ident:str,request:Request):
        with database(root) as db:return book(db,ident,identity(request)['id'])

    @app.get('/api/books/{ident}/chapters/{index}')
    def chapter(ident:str,index:int,request:Request):
        with database(root) as db:
            book(db,ident,identity(request)['id'])
            row=db.execute('SELECT * FROM chapters WHERE book_id=? AND idx=?',(ident,index)).fetchone()
            if not row:raise HTTPException(404,'章节不存在')
            return dict(row)

    def check_position(db,ident,body,user):
        book(db,ident,user)
        if not db.execute('SELECT 1 FROM chapters WHERE book_id=? AND idx=?',(ident,body.chapter)).fetchone():
            raise HTTPException(400,'阅读位置不在书籍章节范围内')

    @app.post('/api/books/{ident}/progress')
    def progress(ident:str,body:Position,request:Request):
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE')
            check_position(db,ident,body,identity(request)['id'])
            db.execute('UPDATE books SET chapter=?,ratio=? WHERE id=?',(body.chapter,body.ratio,ident))
            db.execute('INSERT INTO progress_versions VALUES(?,1,?) ON CONFLICT(book_id) DO UPDATE SET version=version+1,updated=excluded.updated',(ident,time.time()))
        return {'ok':True}

    @app.get('/api/books/{ident}/bookmarks')
    def bookmarks(ident:str,request:Request):
        with database(root) as db:
            book(db,ident,identity(request)['id'])
            return [dict(r) for r in db.execute('SELECT m.*,c.title FROM bookmarks m JOIN chapters c ON c.book_id=m.book_id AND c.idx=m.chapter WHERE m.book_id=? ORDER BY m.created DESC',(ident,))]

    @app.post('/api/books/{ident}/bookmarks',status_code=201)
    def add_bookmark(ident:str,body:Bookmark,request:Request):
        with database(root) as db:
            check_position(db,ident,body,identity(request)['id']);key=uuid.uuid4().hex
            db.execute('INSERT INTO bookmarks VALUES(?,?,?,?,?,?)',(key,ident,body.chapter,body.ratio,body.note.strip(),time.time()))
        return {'id':key}

    @app.delete('/api/books/{ident}/bookmarks/{key}')
    def remove_bookmark(ident:str,key:str,request:Request):
        with database(root) as db:
            book(db,ident,identity(request)['id'])
            cursor=db.execute('DELETE FROM bookmarks WHERE id=? AND book_id=?',(key,ident))
            if cursor.rowcount==0:raise HTTPException(404,'书签不存在')
        return {'ok':True}

    @app.get('/api/books/{ident}/search')
    def search(ident:str,request:Request,q:str=Query(...,min_length=1,max_length=100)):
        with database(root) as db:
            book(db,ident,identity(request)['id'])
            if len(q)>=3:
                rows=db.execute('SELECT c.idx,c.title,c.text FROM chapter_fts f JOIN chapters c ON c.book_id=f.book_id AND c.idx=f.idx WHERE chapter_fts MATCH ? AND f.book_id=? LIMIT 50',(chr(34)+q.replace(chr(34),chr(34)*2)+chr(34),ident))
            else:rows=db.execute('SELECT idx,title,text FROM chapters WHERE book_id=? AND instr(lower(text),lower(?))>0 LIMIT 50',(ident,q))
            results=[]
            for row in rows:
                pos=row['text'].lower().find(q.lower())
                results.append({'chapter':row['idx'],'title':row['title'],'excerpt':row['text'][max(0,pos-40):pos+len(q)+100],'ratio':pos/max(1,len(row['text']))})
            return results

    mount_ui(app);return app


app=create_app()
