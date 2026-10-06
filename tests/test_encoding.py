import codecs
import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.text_encoding import decode_text_details

TEXT='第一章 初遇\n你好，世界。这里是完整的中文小说，阅读文字可以保存进度。\n第二章 出发\n这是下一段旅程，故事的最后一个字符。'
TRADITIONAL=('第一章 開始\n閱讀一本書，讓文字陪伴每一段旅程。這個故事的結尾完整保留。\n第二章 結尾\n繁體中文的故事與人物，還有學習與生活。\n')*20

class EncodingTests(unittest.TestCase):
    def test_unicode_with_and_without_bom_preserves_text(self):
        for encoding in ['utf-8','utf-16','utf-16-le','utf-16-be','utf-32','utf-32-le','utf-32-be']:
            with self.subTest(encoding=encoding):
                decoded=decode_text_details(TEXT.encode(encoding))
                self.assertEqual(decoded.text,TEXT)
    def test_gbk_gb18030_and_big5(self):
        for text,encoding in [(TEXT,'gbk'),(TEXT+'\U00020000','gb18030'),(TRADITIONAL,'big5')]:
            with self.subTest(encoding=encoding):self.assertEqual(decode_text_details(text.encode(encoding)).text,text)
    def test_sparse_embedded_null_padding_is_removed_and_reported(self):
        original=('第一章 开始\n'+'小说正文。'*120000)+'\0'*512+'第二章 结尾\n最后字符。'
        decoded=decode_text_details(original.encode())
        self.assertEqual(decoded.text,original.replace('\0',''))
        self.assertEqual(decoded.removed_null_characters,512)
    def test_binary_and_broken_unicode_are_not_silently_imported(self):
        for raw in [b'\x00\x01\x00',b'\x00'*1000,b'PK\x03\x04fake',codecs.BOM_UTF8+b'text\xff',codecs.BOM_UTF16_LE+b'abc']:
            with self.subTest(raw=raw[:8]):
                with self.assertRaises(HTTPException):decode_text_details(raw)
    def test_encoding_override_and_invalid_option(self):
        self.assertEqual(decode_text_details('café déjà vu'.encode('cp1252'),'cp1252').text,'café déjà vu')
        for encoding in ['invalid','utf-8']:
            with self.assertRaises(HTTPException):decode_text_details(TEXT.encode('gbk'),encoding)
    def test_api_reports_conversion_and_stores_normalized_text(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory))) as client:
                text='第一章 测试\n'+('书籍正文。'*3000)+'\0'*12+'末尾校验。'
                response=client.post('/api/books',files={'file':('null-padding.txt',text.encode(),'text/plain')})
                self.assertEqual(response.status_code,201,response.text)
                data=response.json();self.assertEqual(data['removed_null_characters'],12)
                content=''.join(client.get(f"/api/books/{data['id']}/chapters/{c['idx']}").json()['text'] for c in data['chapters'])
                self.assertNotIn('\0',content);self.assertTrue(content.endswith('末尾校验。'))
                wrong=client.post('/api/books?encoding_hint=utf-8',files={'file':('gbk.txt',TEXT.encode('gbk'),'text/plain')})
                self.assertEqual(wrong.status_code,400)
                fixed=client.post('/api/books?encoding_hint=gb18030',files={'file':('gbk.txt',TEXT.encode('gbk'),'text/plain')})
                self.assertEqual(fixed.status_code,201)
                self.assertIn('big5',client.get('/api/config').json()['import_encodings'])

if __name__=='__main__':unittest.main()
