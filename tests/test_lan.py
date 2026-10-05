import os,tempfile,unittest,argparse
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.lan import private_host

class LanTests(unittest.TestCase):
    def test_only_explicit_private_host_is_allowed(self):
        for host in ['0.0.0.0','8.8.8.8','127.0.0.1','::','example.com']:
            with self.assertRaises(argparse.ArgumentTypeError):private_host(host)
        self.assertEqual(private_host('192.168.1.50'),'192.168.1.50')
    def test_lan_requires_login_and_checks_origin_host(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LEAFREAD_LAN_HOST':'192.168.1.50'}):
            with TestClient(create_app(Path(directory)),base_url='http://192.168.1.50:8777') as client:
                self.assertEqual(client.get('/').status_code,200)
                self.assertEqual(client.get('/api/auth/me').json()['id'],'local')
                self.assertEqual(client.get('/api/books').status_code,401)
                self.assertEqual(client.get('/api/library/backup').status_code,401)
                self.assertEqual(client.get('/api/books',headers={'Host':'192.168.1.51'}).status_code,403)
                password='synthetic'+'-phone-example'
                client.post('/api/auth/register',json={'username':'phone_reader','password':password})
                self.assertEqual(client.get('/api/books').status_code,200)
                bad=client.post('/api/books',headers={'Origin':'http://evil.example'},files={'file':('x.txt',b'hello')})
                self.assertEqual(bad.status_code,403)
                client.post('/api/auth/logout')
                self.assertEqual(client.get('/api/books').status_code,401)
    def test_default_server_stays_local(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LEAFREAD_LAN_HOST':''}):
            with TestClient(create_app(Path(directory))) as client:
                self.assertEqual(client.get('/api/books').status_code,200)
                self.assertEqual(client.get('/',headers={'Host':'192.168.1.50'}).status_code,403)

if __name__=='__main__':unittest.main()
