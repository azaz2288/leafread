"""Bounded, decoded raster illustrations. No archive HTML or active SVG is served."""
import base64
import hashlib
import io
import json
import warnings
from PIL import Image, ImageOps
from fastapi import HTTPException, Request
from fastapi.responses import Response
from .common import database

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_IMAGES = 200
MAX_PIXELS = 8_000_000
MIME_FORMATS = {'image/png':'PNG','image/jpeg':'JPEG','image/webp':'WEBP'}


def _normalize_image(raw, media_type):
    if media_type not in MIME_FORMATS or not raw or len(raw)>MAX_IMAGE_BYTES:
        raise ValueError('unsupported or oversized image')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format!=MIME_FORMATS[media_type] or probe.width*probe.height>MAX_PIXELS or max(probe.size)>4096:
                raise ValueError('image format or dimensions')
            if getattr(probe,'n_frames',1)!=1:raise ValueError('animated image unsupported')
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image=ImageOps.exif_transpose(source).convert('RGBA')
            # New pixel-only image strips EXIF, profiles and textual metadata.
            clean=Image.frombytes('RGBA',image.size,image.tobytes())
            output=io.BytesIO();clean.save(output,format='PNG')
            data=output.getvalue()
            if len(data)>MAX_IMAGE_BYTES:raise ValueError('normalized image limit')
            return data,clean.width,clean.height


def normalize_image(raw,media_type):
    try:return _normalize_image(raw,media_type)
    except (OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('invalid or unsafe raster image') from exc


def content_digest(user, text, images):
    # Keep the historical text-only identity exactly compatible.
    payload=user+'\n'+text
    if images:
        identity=[(i['chapter'],i['ordinal'],i['alt'],hashlib.sha256(i['data']).hexdigest()) for i in images]
        payload+='\nEPUB-ILLUSTRATIONS-v1\n'+json.dumps(identity,ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def checked_backup_images(values, chapters):
    if not isinstance(values,list) or len(values)>MAX_IMAGES:raise ValueError('image count')
    checked=[];total=0;positions=set()
    for value in values:
        chapter=value['chapter'];ordinal=value['ordinal'];alt=value['alt']
        if type(chapter)!=int or not 0<=chapter<len(chapters) or type(ordinal)!=int or not 0<=ordinal<MAX_IMAGES:
            raise ValueError('image position')
        if not isinstance(alt,str) or len(alt)>300 or (chapter,ordinal) in positions:raise ValueError('image metadata')
        encoded=value['data_base64']
        if not isinstance(encoded,str) or len(encoded)>((MAX_IMAGE_BYTES+2)//3)*4:raise ValueError('image size')
        raw=base64.b64decode(encoded,validate=True)
        data,w,h=normalize_image(raw,value['media_type'])
        if type(value['width'])!=int or type(value['height'])!=int or (w,h)!=(value['width'],value['height']):raise ValueError('image dimensions')
        total+=len(data)
        if total>MAX_TOTAL_BYTES:raise ValueError('image total')
        positions.add((chapter,ordinal));checked.append({'chapter':chapter,'ordinal':ordinal,'alt':alt,'data':data,'width':w,'height':h})
    return sorted(checked,key=lambda v:(v['chapter'],v['ordinal']))


def save_images(db, ident, images):
    db.executemany('INSERT INTO illustrations VALUES(?,?,?,?,?,?,?,?)',
        [(ident,i['chapter'],i['ordinal'],i['alt'],'image/png',i['width'],i['height'],i['data']) for i in images])


def backup_images(db, ident):
    result=[]
    for row in db.execute('SELECT * FROM illustrations WHERE book_id=? ORDER BY chapter,ordinal',(ident,)):
        value=dict(row);value['data_base64']=base64.b64encode(value.pop('data')).decode('ascii');value.pop('book_id')
        result.append(value)
    return result


def install_illustrations(app,root,identity):
    with database(root) as db:
        db.execute('CREATE TABLE IF NOT EXISTS illustrations(book_id TEXT REFERENCES books(id) ON DELETE CASCADE,chapter INTEGER,ordinal INTEGER,alt TEXT,media_type TEXT,width INTEGER,height INTEGER,data BLOB,PRIMARY KEY(book_id,chapter,ordinal))')

    def owned(db,ident,request):
        if not db.execute('SELECT 1 FROM books WHERE id=? AND owner=? AND deleted=0',(ident,identity(request)['id'])).fetchone():
            raise HTTPException(404,'书籍不存在或没有权限')

    @app.get('/api/books/{ident}/chapters/{chapter}/illustrations')
    def listing(ident:str,chapter:int,request:Request):
        with database(root) as db:
            owned(db,ident,request)
            if not db.execute('SELECT 1 FROM chapters WHERE book_id=? AND idx=?',(ident,chapter)).fetchone():raise HTTPException(404,'章节不存在')
            return [dict(r) for r in db.execute('SELECT ordinal,alt,media_type,width,height FROM illustrations WHERE book_id=? AND chapter=? ORDER BY ordinal',(ident,chapter))]

    @app.get('/api/books/{ident}/chapters/{chapter}/illustrations/{ordinal}')
    def image(ident:str,chapter:int,ordinal:int,request:Request):
        with database(root) as db:
            owned(db,ident,request)
            row=db.execute('SELECT data FROM illustrations WHERE book_id=? AND chapter=? AND ordinal=?',(ident,chapter,ordinal)).fetchone()
        if not row:raise HTTPException(404,'插图不存在')
        return Response(row['data'],media_type='image/png',headers={'Cache-Control':'private, no-store','Content-Disposition':'inline; filename="illustration.png"'})
