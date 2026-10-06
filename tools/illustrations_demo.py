"""Disposable synthetic EPUB demo; no existing book data is opened."""
from pathlib import Path
import io,json,os,sys,tempfile,threading,time,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix='leafread-illustrations-demo-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        from PIL import Image,ImageDraw
        from app.main import create_app
        from fastapi.testclient import TestClient
        import uvicorn
        pic=Image.new('RGB',(720,420),'#132642');draw=ImageDraw.Draw(pic)
        draw.ellipse((430,40,620,230),fill='#d8b47d');draw.polygon([(0,420),(230,120),(450,420)],fill='#27475f');draw.polygon([(200,420),(460,185),(720,420)],fill='#467c83')
        image=io.BytesIO();pic.save(image,format='PNG')
        epub=io.BytesIO()
        with zipfile.ZipFile(epub,'w') as z:
            z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
            z.writestr('OPS/book.opf','<package><metadata><title>星光旅记 · 合成插图验收</title></metadata><manifest><item id="c" href="chapter.xhtml"/><item id="i" href="moon.png" media-type="image/png"/></manifest><spine><itemref idref="c"/></spine></package>')
            z.writestr('OPS/chapter.xhtml','<html><body><h1>第一章 山与月</h1><p>'+('这是一段原创合成正文。月光照亮山间的小路，旅人停下脚步，打开一本书。'*90)+'</p><img src="moon.png" alt="月夜山谷 · 程序绘制合成插图"/></body></html>')
            z.writestr('OPS/moon.png',image.getvalue())
        (root/'demo.epub').write_bytes(epub.getvalue())
        app=create_app(root/'state')
        with TestClient(app) as client:
            start=time.monotonic();book=client.post('/api/books',files={'file':('demo.epub',epub.getvalue())}).json()
            print(json.dumps({'id':book['id'],'illustration_count':book['illustration_count'],'source_bytes':len(epub.getvalue()),'import_seconds':round(time.monotonic()-start,4)}),flush=True)
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8894,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        print(f'Synthetic demo http://127.0.0.1:8894/ ; upload fixture {root}/demo.epub ; Enter stops/cleans',flush=True)
        try:input()
        finally:
            server.should_exit=True;thread.join(timeout=15)
            if thread.is_alive():raise RuntimeError('Demo server did not stop')


if __name__=='__main__':main()
