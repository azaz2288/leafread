from pathlib import Path
import os,tempfile,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app

class LargeImportTests(unittest.TestCase):
    def test_31_mib_txt_import_last_chapter_and_search_without_truncation(self):
        unit=('这是原创合成大书测试正文，用来检查导入没有截断。\n'*500).encode()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'large.txt'
            with source.open('wb') as stream:
                stream.write('第一章 大书\n'.encode())
                for _ in range((31*1024*1024)//len(unit)+1):stream.write(unit)
                stream.write('\n第二章 结尾\n结尾唯一校验词XYZ_END。'.encode())
            self.assertGreater(source.stat().st_size,30*1024*1024)
            client=TestClient(create_app(root/'state'))
            with source.open('rb') as stream:response=client.post('/api/books',files={'file':('large.txt',stream,'text/plain')})
            self.assertEqual(response.status_code,201,response.text[:200]);book=response.json()
            last=client.get(f"/api/books/{book['id']}/chapters/{len(book['chapters'])-1}").json()
            self.assertIn('XYZ_END',last['text'])
            hits=client.get(f"/api/books/{book['id']}/search?q=XYZ_END").json()
            self.assertEqual(hits[0]['chapter'],len(book['chapters'])-1)
            self.assertEqual(client.get('/api/config').json()['max_upload_bytes'],128*1024*1024)
    def test_configured_limit_is_enforced_and_reports_value(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'LEAFREAD_MAX_UPLOAD_MIB':'1'}):
            client=TestClient(create_app(Path(folder)));response=client.post('/api/books',files={'file':('over.txt',b'x'*(1024*1024+1))})
            self.assertEqual(response.status_code,413);self.assertIn('1MiB',response.json()['detail'])
            self.assertEqual(client.get('/api/books').json(),[])
