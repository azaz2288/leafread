"""Disposable original multi-chapter/image EPUB, isolated from existing libraries."""
from pathlib import Path
import argparse
import io
import json
import os
import sys
import tempfile
import threading
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8904)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    with tempfile.TemporaryDirectory(prefix='leafread-gallery-demo-') as tmp:
        root = Path(tmp)
        os.environ['APP_DATA_DIR'] = str(root / 'bootstrap')
        from PIL import Image, ImageDraw
        from app.main import create_app
        from fastapi.testclient import TestClient
        import uvicorn

        epub = io.BytesIO()
        with zipfile.ZipFile(epub, 'w') as archive:
            archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
            archive.writestr('OPS/book.opf', '<package><metadata><title>星光旅记 · 画廊生命周期合成验收</title></metadata><manifest>' + ''.join(
                f'<item id="c{i}" href="c{i}.xhtml"/>' for i in range(2)) + ''.join(
                f'<item id="i{i}" href="i{i}.png" media-type="image/png"/>' for i in range(3)) +
                '</manifest><spine><itemref idref="c0"/><itemref idref="c1"/></spine></package>')
            for i, color in enumerate(['#467c83', '#98754b', '#626b94']):
                picture = Image.new('RGB', (480, 280), '#132642')
                draw = ImageDraw.Draw(picture)
                draw.ellipse((310, 25, 435, 150), fill='#d8b47d')
                draw.polygon([(0, 280), (140 + i * 25, 65), (380, 280)], fill=color)
                image = io.BytesIO()
                picture.save(image, format='PNG')
                archive.writestr(f'OPS/i{i}.png', image.getvalue())
            for i, images in enumerate([[0, 1], [2]]):
                archive.writestr(f'OPS/c{i}.xhtml', f'<html><body><h1>第{i+1}章 原创星光</h1><p>' +
                    ('原创合成故事：月光照亮山谷，旅人沿着河边走向下一座山。' * 75) + '</p>' + ''.join(
                        f'<img src="i{j}.png" alt="原创合成山谷 {j+1}"/>' for j in images) + '</body></html>')
        app = create_app(root / 'state')
        with TestClient(app) as client:
            response = client.post('/api/books', files={'file': ('gallery.epub', epub.getvalue())})
            response.raise_for_status()
            book = response.json()
            print(json.dumps({'id': book['id'], 'illustrations': book['illustration_count'],
                              'synthetic': True, 'port': args.port}), flush=True)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='warning'))
        thread = threading.Thread(target=server.run)
        thread.start()
        print(f'Original synthetic demo http://127.0.0.1:{args.port}/ ; Enter stops/cleans', flush=True)
        try:
            input()
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError('Demo server did not stop')


if __name__ == '__main__':
    main()
