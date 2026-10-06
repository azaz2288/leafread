"""Bounded EPUB text ingestion without extracting executable or remote assets."""
from html.parser import HTMLParser
from pathlib import PurePosixPath
import io,posixpath,zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit,unquote
from .illustrations import normalize_image,MAX_IMAGES,MAX_IMAGE_BYTES,MAX_TOTAL_BYTES,MIME_FORMATS
from fastapi import HTTPException

class TextParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0;self.images=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.skip+=1
        if tag=='img' and not self.skip:
            values=dict(attrs);self.images.append((values.get('src',''),(values.get('alt') or '')[:300]))
        if tag in {'p','div','br','h1','h2','h3','li'} and not self.skip:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if tag in {'p','div','h1','h2','h3','li'} and not self.skip:self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def resource_path(base,href):
    url=urlsplit(href)
    if url.scheme or url.netloc or url.query:raise ValueError('external resource')
    path=unquote(url.path,errors='strict')
    if not path or '\\' in path or '\x00' in path or path.startswith('/') or ':' in path:raise ValueError('unsafe resource')
    result=posixpath.normpath(posixpath.join(base,path))
    if result=='..' or result.startswith('../'):raise ValueError('escaping resource')
    return result


def parse_epub_details(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist()
            if len(infos)>20000 or sum(i.file_size for i in infos)>256*1024*1024:raise ValueError('archive limit')
            for info in infos:
                name=info.filename
                if name.startswith('/') or '..' in PurePosixPath(name).parts or '\\' in name or info.flag_bits&1:raise ValueError('unsafe path')
                if info.file_size>128*1024*1024 or info.file_size>max(1,info.compress_size)*500:raise ValueError('compression limit')
            if len({i.filename for i in infos})!=len(infos):raise ValueError('duplicate archive names')
            def xml(name):
                data=archive.read(name)
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('XML entities')
                return ET.fromstring(data)
            container=xml('META-INF/container.xml')
            opf=next(e.attrib['full-path'] for e in container.iter() if e.tag.endswith('rootfile'))
            package=xml(opf);folder=posixpath.dirname(opf)
            manifest={e.attrib['id']:e.attrib for e in package.iter() if e.tag.endswith('item')}
            title=next((e.text for e in package.iter() if e.tag.endswith('title') and e.text),'EPUB书籍')
            resources={resource_path(folder,item['href']):item.get('media-type','') for item in manifest.values()}
            chapters=[];images=[];warnings=[];total=0
            for ref in [e.attrib['idref'] for e in package.iter() if e.tag.endswith('itemref')]:
                item=manifest[ref];href=item['href'].split('#')[0]
                if '://' in href or '..' in PurePosixPath(href).parts or href.startswith('/'):raise ValueError('external or escaping resource')
                path=posixpath.normpath(posixpath.join(folder,href));data=archive.read(path).decode('utf-8-sig')
                parser=TextParser();parser.feed(data);text=''.join(parser.parts).strip()
                chapter_images=[]
                for src,alt in parser.images:
                    try:image_path=resource_path(posixpath.dirname(path),src)
                    except ValueError:
                        warnings.append('已忽略外部或不安全插图');continue
                    media_type=resources.get(image_path)
                    if media_type not in MIME_FORMATS:
                        warnings.append('已忽略非manifest栅格插图（含SVG）');continue
                    if archive.getinfo(image_path).file_size>MAX_IMAGE_BYTES:raise ValueError('image input limit')
                    data,w,h=normalize_image(archive.read(image_path),media_type)
                    total+=len(data)
                    if total>MAX_TOTAL_BYTES or len(images)+len(chapter_images)>=MAX_IMAGES:raise ValueError('image total')
                    chapter_images.append({'chapter':len(chapters),'ordinal':len(chapter_images),'alt':alt,'data':data,'width':w,'height':h})
                if not text and chapter_images:text='[插图章节]'
                if text:
                    heading=next((line.strip() for line in text.splitlines() if line.strip()),f'第{len(chapters)+1}节')[:100]
                    for index in range(0,len(text),12000):chapters.append((heading+(f' · {index//12000+1}' if len(text)>12000 else ''),text[index:index+12000]))
                    images.extend(chapter_images)
            if not chapters:raise ValueError('no text')
            return title,chapters,images,list(dict.fromkeys(warnings))
    except Exception:
        raise HTTPException(400,'EPUB无效、路径不安全、压缩超限或没有可读正文') from None


def parse_epub(raw):
    title,chapters,_,_=parse_epub_details(raw)
    return title,chapters
