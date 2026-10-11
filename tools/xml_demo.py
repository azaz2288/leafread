"""Synthetic-only UTF-16 EPUB validation demo with explicit temporary state."""
from pathlib import Path
import io,json,os,socket,sys,tempfile,threading,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def epub(unsafe=False):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        text='<package><metadata><title>原创 UTF-16 安全验收</title></metadata><manifest><item id="c" href="chapter.xhtml"/></manifest><spine><itemref idref="c"/></spine></package>'
        if unsafe:text='<!DOCTYPE package [<!ENTITY authored "unsafe synthetic entity">]>'+text
        z.writestr('OPS/book.opf',text.encode('utf-16'))
        z.writestr('OPS/chapter.xhtml','<html><body><h1>第一章 安全解析</h1><p>'+('这是原创合成文字，不含私人书籍内容。'*100)+'</p></body></html>')
    return output.getvalue()

def main():
    with socket.socket() as check:check.bind(('127.0.0.1',8898))
    with tempfile.TemporaryDirectory(prefix='leafread-xml-demo-') as temporary:
        root=Path(temporary);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        from app.main import create_app
        from fastapi.testclient import TestClient
        import uvicorn
        app=create_app(root/'state')
        with TestClient(app) as client:
            response=client.post('/api/books',files={'file':('safe.epub',epub())})
            if response.status_code!=201:raise RuntimeError('synthetic safe EPUB import failed')
            refused=client.post('/api/books',files={'file':('unsafe.epub',epub(True))})
            if refused.status_code!=400:raise RuntimeError('synthetic DTD was not refused')
            print(json.dumps({'safe_status':201,'unsafe_status':400,'book_id':response.json()['id']}),flush=True)
        (root/'unsafe.epub').write_bytes(epub(True))
        print(f'Only synthetic: http://127.0.0.1:8898/ ; rejected fixture {root}/unsafe.epub ; Enter stops and cleans',flush=True)
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8898,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        try:input()
        finally:
            server.should_exit=True;thread.join(15)
            if thread.is_alive():raise RuntimeError('synthetic demo did not stop')

if __name__=='__main__':main()
