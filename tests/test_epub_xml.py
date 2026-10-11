"""Synthetic EPUB metadata XML entities/encodings and bounded parsing."""
import io
import tempfile
from pathlib import Path
import unittest
import zipfile
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.epub import parse_epub_details
from app.common import database


CONTAINER='<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>'
PACKAGE='<package><metadata><title>原创合成书</title></metadata><manifest><item id="c" href="chapter.xhtml"/></manifest><spine><itemref idref="c"/></spine></package>'

def archive(container=CONTAINER,package=PACKAGE):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('META-INF/container.xml',container)
        z.writestr('OPS/book.opf',package)
        z.writestr('OPS/chapter.xhtml','<html><body><p>原创安全正文，没有私人内容。</p></body></html>')
    return output.getvalue()

class EpubXmlTests(unittest.TestCase):
    def test_utf16_entities_in_container_or_package_rejected_without_writes(self):
        for location in ('container','package'):
            for encoding in ('utf-8','utf-16-le','utf-16-be'):
                    with self.subTest(location=location,encoding=encoding),tempfile.TemporaryDirectory() as temporary:
                        root=Path(temporary);client=TestClient(create_app(root))
                        text=CONTAINER if location=='container' else PACKAGE
                        doctype='container' if location=='container' else 'package'
                        xml='<?xml version="1.0" encoding="'+('UTF-16' if encoding.startswith('utf-16') else 'UTF-8')+'"?>'
                        xml+='<!DOCTYPE '+doctype+' [<!ENTITY authored "ENTITY_MUST_NOT_EXPAND">]>'
                        xml+=text.replace('原创合成书','&authored;') if location=='package' else text
                        encoded=xml.encode(encoding)
                        if encoding=='utf-16-le':encoded=b'\xff\xfe'+encoded
                        if encoding=='utf-16-be':encoded=b'\xfe\xff'+encoded
                        raw=archive(**{location:encoded})
                        response=client.post('/api/books',files={'file':('synthetic.epub',raw)})
                        self.assertEqual(response.status_code,400,response.text)
                        self.assertNotIn('ENTITY_MUST_NOT_EXPAND',response.text)
                        with database(root) as db:
                            for table in ('books','chapters','images','chapter_fts'):
                                if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():
                                    self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)

    def test_doctype_without_entities_and_external_entity_also_refused(self):
        for declaration in ('<!DOCTYPE package>',
                '<!DOCTYPE package SYSTEM "https://invalid.example/never-fetch.dtd">',
                '<!DOCTYPE package [<!ENTITY remote SYSTEM "file:///synthetic-never-read">]>'):
            with self.subTest(declaration=declaration):
                with self.assertRaises(HTTPException) as raised:
                    parse_epub_details(archive(package=(declaration+PACKAGE).encode('utf-16')))
                self.assertEqual(raised.exception.status_code,400)

    def test_safe_utf8_and_utf16_metadata_keep_original_title_and_text(self):
        for encoding in ('utf-8','utf-16','utf-16-be'):
            with self.subTest(encoding=encoding):
                declaration='<?xml version="1.0" encoding="'+('UTF-16' if encoding.startswith('utf-16') else 'UTF-8')+'"?>'
                container=(declaration+CONTAINER).encode(encoding);package=(declaration+PACKAGE).encode(encoding)
                if encoding=='utf-16-be':container=b'\xfe\xff'+container;package=b'\xfe\xff'+package
                title,chapters,images,warnings=parse_epub_details(archive(container,package))
                self.assertEqual(title,'原创合成书');self.assertIn('原创安全正文',chapters[0][1])
                self.assertEqual((images,warnings),([],[]))

    def test_metadata_byte_limit_rejects_before_reading_large_member(self):
        with self.assertRaises(HTTPException) as raised:
            parse_epub_details(archive(package=PACKAGE+' '*(2*1024*1024)))
        self.assertEqual(raised.exception.status_code,400)

    def test_metadata_element_and_depth_budgets(self):
        for xml in (PACKAGE.replace('<metadata>','<metadata>'+'<extra/>'*10001),
                    PACKAGE.replace('<metadata>','<metadata>'+'<extra>'*65).replace('</metadata>','</extra>'*65+'</metadata>')):
            with self.subTest(size=len(xml)),self.assertRaises(HTTPException):parse_epub_details(archive(package=xml))

    def test_metadata_exact_byte_node_and_depth_limits_are_accepted(self):
        from app.epub import MAX_XML_BYTES,MAX_XML_ELEMENTS,MAX_XML_DEPTH
        for package in (PACKAGE+' '*(MAX_XML_BYTES-len(PACKAGE.encode('utf-8'))),
                PACKAGE.replace('<metadata>','<metadata>'+'<extra/>'*(MAX_XML_ELEMENTS-7)),
                PACKAGE.replace('<metadata>','<metadata>'+'<extra>'*(MAX_XML_DEPTH-3)).replace('</metadata>','</extra>'*(MAX_XML_DEPTH-3)+'</metadata>')):
            with self.subTest(length=len(package)):
                self.assertEqual(parse_epub_details(archive(package=package))[0],'原创合成书')

    def test_normalized_registered_rootfile_is_allowed(self):
        self.assertEqual(parse_epub_details(archive(container=CONTAINER.replace('OPS/book.opf','OPS/%62ook.opf')))[0],'原创合成书')

    def test_rootfile_path_does_not_select_external_or_unregistered_member(self):
        for path in ('https://invalid.example/book.opf','../OPS/book.opf','/OPS/book.opf','OPS\\book.opf'):
            with self.subTest(path=path),self.assertRaises(HTTPException):
                parse_epub_details(archive(container=CONTAINER.replace('OPS/book.opf',path)))

if __name__=='__main__':unittest.main()
