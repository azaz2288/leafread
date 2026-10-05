from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.chapters import parse_chapters

TEXT='第一章 初遇\n你好，世界。\n第二章 出发\n这是下一段旅程。'


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.client=TestClient(create_app(self.root))
    def tearDown(self):self.tmp.cleanup()
    def upload(self,raw=None,name='小说.txt'):
        return self.client.post('/api/books',files={'file':(name,raw or TEXT.encode(),'text/plain')})
    def test_chinese_chapters_and_dedup(self):
        first=self.upload().json();second=self.upload().json()
        self.assertEqual(len(first['chapters']),2);self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate'])
    def test_gb18030_and_utf16(self):
        for encoding in ['gb18030','utf-16']:
            response=self.upload(TEXT.encode(encoding));self.assertEqual(response.status_code,201)
            self.assertEqual(len(response.json()['chapters']),2)
    def test_long_text_is_bounded_without_data_loss(self):
        text='长'*25001;parts=parse_chapters(text)
        self.assertEqual(len(parts),3);self.assertEqual(''.join(p[1] for p in parts),text)
        self.assertLessEqual(max(len(p[1]) for p in parts),12000)
    def test_chinese_heading_without_space(self):
        parts=parse_chapters('第一章初遇\n正文一\n第二章出发\n正文二')
        self.assertEqual([p[0] for p in parts],['第一章初遇','第二章出发'])
    def test_invalid_empty_and_non_text(self):
        self.assertEqual(self.upload(b'\x00\x01\x00').status_code,400)
        self.assertEqual(self.upload(b'   ').status_code,400)
        self.assertEqual(self.upload(name='book.epub').status_code,400)
    def test_progress_persists_after_restart(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.client.post('/api/books/'+ident+'/progress',json={'chapter':1,'ratio':.7}).status_code,200)
        other=TestClient(create_app(self.root));data=other.get('/api/books/'+ident).json()
        self.assertEqual((data['chapter'],data['ratio']),(1,.7))
    def test_invalid_positions(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.client.post('/api/books/'+ident+'/progress',json={'chapter':20,'ratio':.2}).status_code,400)
        self.assertEqual(self.client.post('/api/books/'+ident+'/progress',json={'chapter':1,'ratio':1.2}).status_code,422)
    def test_bookmark_add_and_delete(self):
        ident=self.upload().json()['id']
        response=self.client.post('/api/books/'+ident+'/bookmarks',json={'chapter':1,'ratio':.3,'note':'喜欢这段'})
        self.assertEqual(response.status_code,201)
        marks=self.client.get('/api/books/'+ident+'/bookmarks').json()
        self.assertEqual(marks[0]['title'],'第二章 出发')
        self.assertEqual(self.client.delete('/api/books/'+ident+'/bookmarks/'+marks[0]['id']).status_code,200)
        self.assertEqual(self.client.get('/api/books/'+ident+'/bookmarks').json(),[])
    def test_search_literal_and_chapter(self):
        ident=self.upload().json()['id'];data=self.client.get('/api/books/'+ident+'/search?q=旅程').json()
        self.assertEqual(data[0]['chapter'],1)
        self.assertEqual(self.client.get('/api/books/'+ident+'/search?q=%').json(),[])
        self.assertEqual(self.client.get('/api/books/'+ident+'/chapters/1').json()['title'],'第二章 出发')
    def test_script_content_stays_plain_text(self):
        ident=self.upload(b'<script>alert(1)</script>').json()['id']
        self.assertEqual(self.client.get('/api/books/'+ident+'/chapters/0').json()['text'],'<script>alert(1)</script>')
    def test_cross_site_blocked(self):
        self.assertEqual(self.client.post('/api/books/x/progress',headers={'Origin':'https://evil.example'},json={'chapter':0,'ratio':0}).status_code,403)


if __name__=='__main__':unittest.main()
