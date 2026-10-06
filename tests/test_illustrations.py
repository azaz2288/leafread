from pathlib import Path
import base64,copy,io,json,os,tempfile,unittest,zipfile
from unittest.mock import patch
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.illustrations import normalize_image,content_digest
from app.common import database


def raster(color='navy',fmt='PNG',size=(96,64)):
    output=io.BytesIO();image=Image.new('RGB',size,color)
    if fmt=='PNG':
        metadata=PngInfo();metadata.add_text('Comment','synthetic metadata to strip')
        image.save(output,format=fmt,pnginfo=metadata)
    else:image.save(output,format=fmt)
    return output.getvalue()


def illustrated_epub(color='navy',src='images/picture.png',mime='image/png',image=None,image_only=False,extra='',duplicate=False):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        z.writestr('OPS/book.opf',f'<package><metadata><title>合成插图书</title></metadata><manifest><item id="c" href="chapter.xhtml"/><item id="i" href="images/picture.png" media-type="{mime}"/></manifest><spine><itemref idref="c"/></spine></package>')
        text='' if image_only else '<h1>第一章 星光</h1><p>只用于测试的原创正文。</p>'
        z.writestr('OPS/chapter.xhtml',f'<html><body>{text}<img src="{src}" alt="合成星光 &amp; 图"/>{extra}</body></html>')
        z.writestr('OPS/images/picture.png',raster(color) if image is None else image)
        if duplicate:z.writestr('OPS/chapter.xhtml','different duplicate')
    return out.getvalue()


class IllustrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.client=TestClient(create_app(self.root))
    def tearDown(self):self.tmp.cleanup()
    def upload(self,**kwargs):return self.client.post('/api/books',files={'file':('art.epub',illustrated_epub(**kwargs))})
    def listing(self,ident):return self.client.get(f'/api/books/{ident}/chapters/0/illustrations')
    def asset(self,ident):return self.client.get(f'/api/books/{ident}/chapters/0/illustrations/0')

    def test_real_raster_is_decoded_normalized_and_served_with_metadata_removed(self):
        response=self.upload();self.assertEqual(response.status_code,201,response.text);ident=response.json()['id']
        self.assertEqual(response.json()['illustration_count'],1)
        meta=self.listing(ident).json()[0];self.assertEqual((meta['width'],meta['height'],meta['alt']),(96,64,'合成星光 & 图'))
        asset=self.asset(ident);self.assertEqual(asset.status_code,200)
        self.assertEqual(asset.headers['content-type'],'image/png');self.assertEqual(asset.headers['cache-control'],'private, no-store')
        with Image.open(io.BytesIO(asset.content)) as image:
            self.assertEqual(image.size,(96,64));self.assertNotIn('Comment',image.info);self.assertEqual(image.convert('RGB').getpixel((0,0)),(0,0,128))

    def test_image_only_chapter_keeps_spine_and_readability(self):
        ident=self.upload(image_only=True).json()['id']
        self.assertEqual(self.client.get(f'/api/books/{ident}/chapters/0').json()['text'],'[插图章节]')
        self.assertEqual(len(self.listing(ident).json()),1)

    def test_images_affect_dedup_and_duplicate_upload_is_stable(self):
        a=self.upload().json();b=self.upload().json();c=self.upload(color='red').json()
        self.assertEqual(a['id'],b['id']);self.assertTrue(b['duplicate']);self.assertNotEqual(a['id'],c['id'])

    def test_relative_percent_encoded_manifest_resource(self):
        ident=self.upload(src='./images/%70icture.png').json()['id']
        self.assertEqual(self.asset(ident).status_code,200)

    def test_external_svg_data_and_escaping_references_never_become_assets(self):
        for src in ['https://example.invalid/x.png','//example.invalid/x.png','data:image/png;base64,a','../../escape.png','%2e%2e/%2e%2e/x.png','images\\picture.png']:
            with self.subTest(src=src):
                response=self.upload(src=src);self.assertEqual(response.status_code,201,response.text)
                self.assertEqual(response.json()['illustration_count'],0);self.assertTrue(response.json()['illustration_warnings'])
        response=self.upload(mime='image/svg+xml',image=b'<svg onload="bad()"/>')
        self.assertEqual(response.status_code,201);self.assertEqual(response.json()['illustration_count'],0)

    def test_corrupt_mismatched_animation_and_dimension_limits_reject_atomic_upload(self):
        out=io.BytesIO();Image.new('RGB',(2,2),'red').save(out,format='PNG',save_all=True,append_images=[Image.new('RGB',(2,2),'blue')],duration=100)
        cases=[{'image':b'badPNG'},{'mime':'image/jpeg'},{'image':raster(size=(4097,1))},{'image':out.getvalue()}]
        for kwargs in cases:
            with self.subTest(kwargs=list(kwargs)):
                self.assertEqual(self.upload(**kwargs).status_code,400)
                self.assertEqual(self.client.get('/api/books').json(),[])

    def test_asset_owner_deleted_and_missing_access_guards(self):
        ident=self.upload().json()['id'];other=TestClient(self.client.app)
        other.post('/api/auth/register',json={'username':'reader2','password':'-'.join(['synthetic','image','test'])})
        self.assertEqual(other.get(f'/api/books/{ident}/chapters/0/illustrations').status_code,404)
        self.assertEqual(other.get(f'/api/books/{ident}/chapters/0/illustrations/0').status_code,404)
        self.assertEqual(self.client.get(f'/api/books/{ident}/chapters/999/illustrations').status_code,404)
        self.client.delete(f'/api/library/books/{ident}');self.assertEqual(self.asset(ident).status_code,404)
        self.client.post(f'/api/library/books/{ident}/restore');self.assertEqual(self.asset(ident).status_code,200)

    def test_backup_roundtrip_includes_pixels_and_dedup_identity(self):
        ident=self.upload().json()['id'];expected=self.asset(ident).content
        backup=self.client.get('/api/library/backup').json()
        self.assertEqual(len(backup['books'][0]['illustrations']),1)
        with tempfile.TemporaryDirectory() as folder:
            other=TestClient(create_app(Path(folder)))
            result=other.post('/api/library/restore-backup',files={'file':('x.json',json.dumps(backup).encode())})
            self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['imported'],1)
            new=other.get('/api/books').json()[0]['id']
            self.assertEqual(other.get(f'/api/books/{new}/chapters/0/illustrations/0').content,expected)
            self.assertEqual(other.post('/api/library/restore-backup',files={'file':('x.json',json.dumps(backup).encode())}).json()['imported'],0)

    def test_invalid_backup_image_is_prevalidated_before_any_book_write(self):
        self.upload();backup=self.client.get('/api/library/backup').json()
        for field,value in [('data_base64','notbase64!'),('data_base64',base64.b64encode(b'badpng').decode()),('chapter',True),('ordinal',True),('width',999),('media_type','image/svg+xml')]:
            bad=copy.deepcopy(backup);bad['books'].append(copy.deepcopy(bad['books'][0]));bad['books'][1]['illustrations'][0][field]=value
            with self.subTest(field=field,value=value),tempfile.TemporaryDirectory() as folder:
                other=TestClient(create_app(Path(folder)))
                response=other.post('/api/library/restore-backup',files={'file':('x.json',json.dumps(bad).encode())})
                self.assertEqual(response.status_code,400,response.text);self.assertEqual(other.get('/api/books').json(),[])

    def test_image_count_limit_and_duplicate_archive_names(self):
        self.assertEqual(self.upload(extra='<img src="images/picture.png"/>'*200).status_code,400)
        self.assertEqual(self.upload(duplicate=True).status_code,400)

    def test_jpeg_webp_normalization_and_text_identity_compatibility(self):
        for mime,fmt in [('image/jpeg','JPEG'),('image/webp','WEBP')]:
            data,w,h=normalize_image(raster(fmt=fmt),mime);self.assertTrue(data.startswith(b'\x89PNG'));self.assertEqual((w,h),(96,64))
        import hashlib
        self.assertEqual(content_digest('local','text',[]),hashlib.sha256(b'local\ntext').hexdigest())

    def test_exact_resource_budgets_and_predecode_pixel_guard(self):
        from app.illustrations import MAX_IMAGE_BYTES
        with self.assertRaises(ValueError):normalize_image(b'x'*(MAX_IMAGE_BYTES+1),'image/png')
        with patch('app.illustrations.MAX_PIXELS',96*64):self.assertEqual(normalize_image(raster(),'image/png')[1:],(96,64))
        with patch('app.illustrations.MAX_PIXELS',96*64-1),self.assertRaises(ValueError):normalize_image(raster(),'image/png')
        size=len(normalize_image(raster(),'image/png')[0])
        with patch('app.epub.MAX_TOTAL_BYTES',size):self.assertEqual(self.upload().status_code,201)
        with patch('app.epub.MAX_TOTAL_BYTES',size-1):self.assertEqual(self.upload().status_code,400)
        with patch('app.epub.MAX_IMAGES',1):self.assertEqual(self.upload(extra='<img src="images/picture.png"/>').status_code,400)

    def test_long_spine_chapter_images_attach_to_first_split_without_text_loss(self):
        raw=illustrated_epub();text='原文'*13000
        with zipfile.ZipFile(io.BytesIO(raw)) as source:
            entries={i.filename:source.read(i) for i in source.infolist()}
        entries['OPS/chapter.xhtml']=('<html><body><p>'+text+'</p><img src="images/picture.png"/></body></html>').encode()
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:
            for name,data in entries.items():archive.writestr(name,data)
        result=self.client.post('/api/books',files={'file':('long.epub',out.getvalue())}).json()
        self.assertEqual(len(result['chapters']),3)
        observed=''.join(self.client.get(f"/api/books/{result['id']}/chapters/{i}").json()['text'] for i in range(3))
        self.assertEqual(observed,text)
        self.assertEqual(len(self.listing(result['id']).json()),1)
        self.assertEqual(self.client.get(f"/api/books/{result['id']}/chapters/1/illustrations").json(),[])

    def test_legacy_backup_without_images_is_accepted(self):
        self.client.post('/api/books',files={'file':('old.txt','第一章 旧书\n原创正文'.encode())})
        backup=self.client.get('/api/library/backup').json()
        for b in backup['books']:b.pop('illustrations')
        with tempfile.TemporaryDirectory() as folder:
            other=TestClient(create_app(Path(folder)))
            result=other.post('/api/library/restore-backup',files={'file':('old.json',json.dumps(backup).encode())})
            self.assertEqual(result.status_code,200);self.assertEqual(result.json()['imported'],1)
            self.assertEqual(other.get('/api/library/backup').json()['books'][0]['illustrations'],[])

    def test_restore_duplicate_position_and_global_count_limit_are_atomic(self):
        self.upload();self.upload(color='red');backup=self.client.get('/api/library/backup').json()
        for duplicate in (False,True):
            bad=copy.deepcopy(backup)
            if duplicate:bad['books'][0]['illustrations'].append(copy.deepcopy(bad['books'][0]['illustrations'][0]))
            with tempfile.TemporaryDirectory() as folder,patch('app.restore.MAX_IMAGES',1):
                other=TestClient(create_app(Path(folder)))
                response=other.post('/api/library/restore-backup',files={'file':('x.json',json.dumps(bad).encode())})
                self.assertEqual(response.status_code,400);self.assertEqual(other.get('/api/books').json(),[])

    def test_storage_fault_rolls_back_upload_book_chapters_and_index(self):
        with patch('app.main.save_images',side_effect=RuntimeError('synthetic write fault')):
            with self.assertRaises(RuntimeError):self.upload()
        with database(self.root) as db:
            for table in ('books','chapters','chapter_fts','illustrations'):
                self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)

    def test_storage_fault_in_later_restore_book_rolls_back_whole_backup(self):
        self.upload();self.upload(color='red');backup=self.client.get('/api/library/backup').json()
        from app.illustrations import save_images
        calls=0
        def fault(db,ident,images):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('synthetic second-book failure')
            return save_images(db,ident,images)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);other=TestClient(create_app(target))
            with patch('app.restore.save_images',side_effect=fault),self.assertRaises(RuntimeError):
                other.post('/api/library/restore-backup',files={'file':('x.json',json.dumps(backup).encode())})
            with database(target) as db:
                for table in ('books','chapters','chapter_fts','illustrations'):
                    self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)


if __name__=='__main__':unittest.main()
