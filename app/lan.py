"""Explicit, opt-in private-network launcher; never changes firewall rules."""
import argparse
import os
from pathlib import Path
import ipaddress

def private_host(value):
    try:address=ipaddress.ip_address(value)
    except ValueError:raise argparse.ArgumentTypeError('需要电脑的私网IPv4地址') from None
    if address.version!=4 or not any(address in ipaddress.ip_network(block) for block in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']):
        raise argparse.ArgumentTypeError('仅支持指定的192.168/10/172.16–31私网地址')
    return str(address)

def main():
    parser=argparse.ArgumentParser(description='同一Wi-Fi手机阅读；需登录现有账户，不自动开放防火墙。')
    parser.add_argument('--host',type=private_host,required=True)
    parser.add_argument('--port',type=int,default=8777)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('端口需在1024–65535')
    os.environ['LEAFREAD_LAN_HOST']=args.host
    os.environ.setdefault('APP_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data'))
    import uvicorn
    print(f'手机连接同一可信Wi-Fi，打开 http://{args.host}:{args.port}，用电脑阅读账户登录。')
    print('电脑需要保持运行；仅在可信家庭网络使用HTTP。公网或手机离线安装需HTTPS。')
    uvicorn.run('app.main:app',host=args.host,port=args.port,proxy_headers=False)

if __name__=='__main__':main()
