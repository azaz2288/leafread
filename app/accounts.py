import hashlib,hmac,secrets,time
from fastapi import HTTPException,Request,Response
from pydantic import BaseModel,Field
from .common import database

class Credentials(BaseModel):
    username:str=Field(min_length=3,max_length=40,pattern=r"^[a-zA-Z0-9_-]+$")
    password:str=Field(min_length=10,max_length=128)

def install_accounts(app,root):
    cookie_name=app.title.lower().replace(" ","_")+"_session"
    with database(root) as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE,password TEXT,created REAL);
          CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,expires REAL);
          CREATE TABLE IF NOT EXISTS login_attempts(client TEXT PRIMARY KEY,count INTEGER,started REAL);""")
    def identity(request):
        raw=request.cookies.get(cookie_name,'')
        if raw:
            digest=hashlib.sha256(raw.encode()).hexdigest()
            with database(root) as db:
                user=db.execute('SELECT u.id,u.username FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.digest=? AND s.expires>?',(digest,time.time())).fetchone()
            if user:return dict(user)
        return {'id':'local','username':'本地访客'}
    def issue(db,response,user):
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+7*86400))
        response.set_cookie(cookie_name,token,httponly=True,samesite='strict',max_age=7*86400,secure=False)
        return {'id':user['id'],'username':user['username']}
    @app.post('/api/auth/register',status_code=201)
    def register(body:Credentials,response:Response):
        name=body.username.lower();salt=secrets.token_hex(16)
        hashed=hashlib.scrypt(body.password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        with database(root) as db:
            if db.execute('SELECT 1 FROM users WHERE username=?',(name,)).fetchone():raise HTTPException(409,'用户名已存在')
            user={'id':secrets.token_hex(16),'username':name}
            db.execute('INSERT INTO users VALUES(?,?,?,?)',(user['id'],name,salt+':'+hashed,time.time()))
            return issue(db,response,user)
    @app.post('/api/auth/login')
    def login(body:Credentials,request:Request,response:Response):
        client=request.client.host if request.client else 'local'
        with database(root) as db:
            row=db.execute('SELECT * FROM login_attempts WHERE client=?',(client,)).fetchone()
            if row and time.time()-row['started']<300 and row['count']>=10:raise HTTPException(429,'尝试过多，请5分钟后重试')
            if not row or time.time()-row['started']>=300:db.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)',(client,0,time.time()))
            db.execute('UPDATE login_attempts SET count=count+1 WHERE client=?',(client,));db.commit()
            user=db.execute('SELECT * FROM users WHERE username=?',(body.username.lower(),)).fetchone()
            salt,expected=(user['password'].split(':') if user else ('00'*16,'00'*64))
            actual=hashlib.scrypt(body.password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            if not user or not hmac.compare_digest(actual,expected):raise HTTPException(401,'用户名或密码错误')
            db.execute('DELETE FROM login_attempts WHERE client=?',(client,))
            return issue(db,response,user)
    @app.get('/api/auth/me')
    def me(request:Request):return identity(request)
    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        with database(root) as db:db.execute('DELETE FROM sessions WHERE digest=?',(hashlib.sha256(request.cookies.get(cookie_name,'').encode()).hexdigest(),))
        response.delete_cookie(cookie_name);return {'ok':True}
    return identity
