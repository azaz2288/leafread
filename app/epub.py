"""Bounded EPUB text ingestion without extracting executable or remote assets."""
from html.parser import HTMLParser
from pathlib import PurePosixPath
import io,posixpath,zipfile
import xml.etree.ElementTree as ET
from fastapi import HTTPException

class TextParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.skip+=1
        if tag in {'p','div','br','h1','h2','h3','li'} and not self.skip:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if tag in {'p','div','h1','h2','h3','li'} and not self.skip:self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def parse_epub(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist()
            if len(infos)>20000 or sum(i.file_size for i in infos)>256*1024*1024:raise ValueError('archive limit')
            for info in infos:
                name=info.filename
                if name.startswith('/') or '..' in PurePosixPath(name).parts or '\\' in name or info.flag_bits&1:raise ValueError('unsafe path')
                if info.file_size>128*1024*1024 or info.file_size>max(1,info.compress_size)*500:raise ValueError('compression limit')
            def xml(name):
                data=archive.read(name)
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('XML entities')
                return ET.fromstring(data)
            container=xml('META-INF/container.xml')
            opf=next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
            package=xml(opf);folder=posixpath.dirname(opf)
            manifest={e.attrib['id']:e.attrib for e in package.iter() if e.tag.endswith('item')}
            title=next((e.text for e in package.iter() if e.tag.endswith('title') and e.text),'EPUB书籍')
            chapters=[]
            for ref in [e.attrib['idref'] for e in package.iter() if e.tag.endswith('itemref')]:
                item=manifest[ref];href=item['href'].split('#')[0]
                if '://' in href or '..' in PurePosixPath(href).parts or href.startswith('/'):raise ValueError('external or escaping resource')
                path=posixpath.normpath(posixpath.join(folder,href));data=archive.read(path).decode('utf-8-sig')
                parser=TextParser();parser.feed(data);text=''.join(parser.parts).strip()
                if text:
                    heading=next((line.strip() for line in text.splitlines() if line.strip()),f'第{len(chapters)+1}节')[:100]
                    for index in range(0,len(text),12000):chapters.append((heading+(f' · {index//12000+1}' if len(text)>12000 else ''),text[index:index+12000]))
            if not chapters:raise ValueError('no text')
            return title,chapters
    except Exception:
        raise HTTPException(400,'EPUB无效、路径不安全、压缩超限或没有可读正文') from None
