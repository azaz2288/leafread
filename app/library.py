import json,time,uuid
from fastapi import HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field
from .common import database

class Annotation(BaseModel):
    chapter:int=Field(ge=0)
    quote:str=Field(min_length=1,max_length=2000)
    note:str=Field('',max_length=2000)
class Note(BaseModel):
    note:str=Field(max_length=2000)

def install_library(app,root,identity):
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS annotations(id TEXT PRIMARY KEY,book_id TEXT REFERENCES books(id) ON DELETE CASCADE,chapter INTEGER,quote TEXT,note TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS progress_versions(book_id TEXT PRIMARY KEY,version INTEGER,updated REAL);
        CREATE VIRTUAL TABLE IF NOT EXISTS chapter_fts USING fts5(book_id UNINDEXED,idx UNINDEXED,text,tokenize='trigram');''')
        db.execute('DELETE FROM chapter_fts');db.execute('INSERT INTO chapter_fts SELECT book_id,idx,text FROM chapters')
        db.executescript('''CREATE TRIGGER IF NOT EXISTS chapter_index_insert AFTER INSERT ON chapters BEGIN INSERT INTO chapter_fts VALUES(new.book_id,new.idx,new.text); END;
        CREATE TRIGGER IF NOT EXISTS chapter_index_delete AFTER DELETE ON chapters BEGIN DELETE FROM chapter_fts WHERE book_id=old.book_id AND idx=old.idx; END;''')
    def owned(db,ident,request):
        row=db.execute('SELECT * FROM books WHERE id=?',(ident,)).fetchone()
        if not row or row['owner']!=identity(request)['id']:raise HTTPException(404,'书籍不存在或没有权限')
        return row
    @app.delete('/api/library/books/{ident}')
    def remove(ident:str,request:Request):
        with database(root) as db:
            owned(db,ident,request);db.execute('UPDATE books SET deleted=1 WHERE id=?',(ident,))
        return {'ok':True}
    @app.post('/api/library/books/{ident}/restore')
    def restore(ident:str,request:Request):
        with database(root) as db:owned(db,ident,request);db.execute('UPDATE books SET deleted=0 WHERE id=?',(ident,))
        return {'ok':True}
    @app.get('/api/library/trash')
    def trash(request:Request):
        with database(root) as db:return [dict(r) for r in db.execute('SELECT id,title FROM books WHERE owner=? AND deleted=1',(identity(request)['id'],))]
    @app.get('/api/library/books/{ident}/export')
    def export(ident:str,request:Request):
        with database(root) as db:
            row=owned(db,ident,request)
            text='\n\n'.join(r['title']+'\n'+r['text'] for r in db.execute('SELECT title,text FROM chapters WHERE book_id=? ORDER BY idx',(ident,)))
        return Response(text,media_type='text/plain; charset=utf-8',headers={'Content-Disposition':'attachment; filename="book.txt"'})
    @app.get('/api/library/books/{ident}/annotations')
    def annotations(ident:str,request:Request):
        with database(root) as db:
            owned(db,ident,request);return [dict(r) for r in db.execute('SELECT * FROM annotations WHERE book_id=? ORDER BY created DESC',(ident,))]
    @app.post('/api/library/books/{ident}/annotations',status_code=201)
    def add(ident:str,body:Annotation,request:Request):
        with database(root) as db:
            owned(db,ident,request);chapter=db.execute('SELECT text FROM chapters WHERE book_id=? AND idx=?',(ident,body.chapter)).fetchone()
            if not chapter or body.quote not in chapter['text']:raise HTTPException(400,'选段必须来自本章原文')
            key=uuid.uuid4().hex;db.execute('INSERT INTO annotations VALUES(?,?,?,?,?,?)',(key,ident,body.chapter,body.quote,body.note,time.time()))
        return {'id':key}
    @app.patch('/api/library/books/{ident}/annotations/{key}')
    def edit(ident:str,key:str,body:Note,request:Request):
        with database(root) as db:
            owned(db,ident,request);cursor=db.execute('UPDATE annotations SET note=? WHERE book_id=? AND id=?',(body.note,ident,key))
            if not cursor.rowcount:raise HTTPException(404,'笔记不存在')
        return {'ok':True}
    @app.delete('/api/library/books/{ident}/annotations/{key}')
    def delete(ident:str,key:str,request:Request):
        with database(root) as db:owned(db,ident,request);db.execute('DELETE FROM annotations WHERE book_id=? AND id=?',(ident,key))
        return {'ok':True}
    @app.patch('/api/library/books/{ident}/bookmarks/{key}')
    def edit_mark(ident:str,key:str,body:Note,request:Request):
        with database(root) as db:owned(db,ident,request);db.execute('UPDATE bookmarks SET note=? WHERE book_id=? AND id=?',(body.note,ident,key))
        return {'ok':True}
    @app.get('/api/library/books/{ident}/notes-export')
    def export_notes(ident:str,request:Request):
        with database(root) as db:
            row=owned(db,ident,request);text='# '+row['title']+' 阅读笔记\n\n'
            for note in db.execute('SELECT * FROM annotations WHERE book_id=? ORDER BY chapter,created',(ident,)):
                text+=f"## 第{note['chapter']+1}节\n\n> {note['quote']}\n\n{note['note']}\n\n"
        return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="reading-notes.md"'})
    @app.get('/api/library/backup')
    def backup(request:Request):
        with database(root) as db:
            books=[dict(r) for r in db.execute('SELECT * FROM books WHERE owner=?',(identity(request)['id'],))]
            for book in books:
                for table in ['chapters','bookmarks','annotations']:book[table]=[dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE book_id=?'+(' ORDER BY idx' if table=='chapters' else ' ORDER BY created'),(book['id'],))]
        return Response(json.dumps({'version':1,'books':books},ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="leafread-backup.json"'})
    @app.get('/api/library/books/{ident}/sync')
    def sync(ident:str,request:Request):
        with database(root) as db:
            row=owned(db,ident,request);version=db.execute('SELECT version FROM progress_versions WHERE book_id=?',(ident,)).fetchone()
        return {'chapter':row['chapter'],'ratio':row['ratio'],'version':version[0] if version else 0}
    @app.post('/api/library/books/{ident}/sync')
    def sync_update(ident:str,request:Request,body:dict):
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE');owned(db,ident,request)
            version=db.execute('SELECT version FROM progress_versions WHERE book_id=?',(ident,)).fetchone();current=version[0] if version else 0
            if body.get('version')!=current:raise HTTPException(409,'进度已被其他客户端更新，请刷新后合并')
            chapter=body.get('chapter');ratio=body.get('ratio')
            if not isinstance(chapter,int) or not isinstance(ratio,(int,float)) or not 0<=ratio<=1 or not db.execute('SELECT 1 FROM chapters WHERE book_id=? AND idx=?',(ident,chapter)).fetchone():raise HTTPException(400,'位置无效')
            db.execute('UPDATE books SET chapter=?,ratio=? WHERE id=?',(chapter,ratio,ident));db.execute('INSERT OR REPLACE INTO progress_versions VALUES(?,?,?)',(ident,current+1,time.time()))
        return {'version':current+1}
