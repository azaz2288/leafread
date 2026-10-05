def synthetic_password(suffix):
    return '-'.join(['synthetic','pass',suffix])

from pathlib import Path
import io,tempfile,unittest,zipfile,json
from fastapi.testclient import TestClient
from app.main import create_app

def epub(unsafe=False):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        z.writestr('OPS/book.opf','<package><metadata><title>示例EPUB</title></metadata><manifest><item id="c" href="chapter.xhtml"/></manifest><spine><itemref idref="c"/></spine></package>')
        z.writestr('OPS/chapter.xhtml','<html><body><h1>第一章</h1><p>正文与批注测试。</p><script>malicious()</script></body></html>')
        if unsafe:z.writestr('../escape','bad')
    return output.getvalue()

class LibraryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.client=TestClient(create_app(Path(self.tmp.name)))
    def tearDown(self):self.tmp.cleanup()
    def book(self):return self.client.post('/api/books',files={'file':('sample.epub',epub())}).json()['id']
    def test_epub_safe_text_and_archive_escape(self):
        ident=self.book();chapter=self.client.get('/api/books/'+ident+'/chapters/0').json()
        self.assertIn('正文',chapter['text']);self.assertNotIn('malicious',chapter['text'])
        self.assertEqual(self.client.post('/api/books',files={'file':('bad.epub',epub(True))}).status_code,400)
    def test_notes_export_and_source_validation(self):
        ident=self.book();response=self.client.post('/api/library/books/'+ident+'/annotations',json={'chapter':0,'quote':'正文','note':'想法'})
        self.assertEqual(response.status_code,201)
        self.assertIn('想法',self.client.get('/api/library/books/'+ident+'/notes-export').text)
        self.assertEqual(self.client.post('/api/library/books/'+ident+'/annotations',json={'chapter':0,'quote':'不存在'}).status_code,400)
    def test_soft_delete_restore_and_export(self):
        ident=self.book();self.assertIn('正文',self.client.get('/api/library/books/'+ident+'/export').text)
        self.client.delete('/api/library/books/'+ident);self.assertEqual(self.client.get('/api/books').json(),[])
        self.assertEqual(len(self.client.get('/api/library/trash').json()),1)
        self.client.post('/api/library/books/'+ident+'/restore');self.assertEqual(len(self.client.get('/api/books').json()),1)
    def test_optimistic_sync_conflict(self):
        ident=self.book();body={'version':0,'chapter':0,'ratio':.5}
        self.assertEqual(self.client.post('/api/library/books/'+ident+'/sync',json=body).status_code,200)
        self.assertEqual(self.client.post('/api/library/books/'+ident+'/sync',json=body).status_code,409)
    def test_account_read_isolation(self):
        ident=self.book();other=TestClient(self.client.app)
        other.post('/api/auth/register',json={'username':'reader','password':synthetic_password('123')})
        self.assertEqual(other.get('/api/books/'+ident).status_code,404)
        self.assertEqual(other.get('/api/library/books/'+ident+'/export').status_code,404)
    def test_backup_restore_roundtrip_and_atomic_invalid_rejection(self):
        ident=self.book()
        self.client.post('/api/books/'+ident+'/progress',json={'chapter':0,'ratio':.6})
        self.client.post('/api/books/'+ident+'/bookmarks',json={'chapter':0,'ratio':.4,'note':'标记'})
        self.client.post('/api/library/books/'+ident+'/annotations',json={'chapter':0,'quote':'正文','note':'笔记'})
        backup=self.client.get('/api/library/backup').json()
        with tempfile.TemporaryDirectory() as folder:
            other=TestClient(create_app(Path(folder)))
            result=other.post('/api/library/restore-backup',files={'file':('backup.json',json.dumps(backup).encode())})
            self.assertEqual(result.json()['imported'],1)
            new=other.get('/api/books').json()[0]
            self.assertEqual(new['ratio'],.6)
            self.assertEqual(other.get('/api/books/'+new['id']+'/bookmarks').json()[0]['note'],'标记')
            self.assertEqual(other.get('/api/library/books/'+new['id']+'/annotations').json()[0]['note'],'笔记')
            self.assertEqual(other.post('/api/library/restore-backup',files={'file':('backup.json',json.dumps(backup).encode())}).json()['imported'],0)
        backup['books'].append({**backup['books'][0],'chapter':999})
        with tempfile.TemporaryDirectory() as folder:
            other=TestClient(create_app(Path(folder)))
            self.assertEqual(other.post('/api/library/restore-backup',files={'file':('backup.json',json.dumps(backup).encode())}).status_code,400)
            self.assertEqual(other.get('/api/books').json(),[])
    def test_legacy_progress_invalidates_sync_version(self):
        ident=self.book();self.client.post('/api/books/'+ident+'/progress',json={'chapter':0,'ratio':.8})
        self.assertEqual(self.client.post('/api/library/books/'+ident+'/sync',json={'version':0,'chapter':0,'ratio':.1}).status_code,409)

if __name__=='__main__':unittest.main()
