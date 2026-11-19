"""Loopback web interface for the seven user-confirmed Pyomo SG scripts."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid
from twin_baseline import BaselineTwin as Twin, PROFILES

WEB = Path(__file__).resolve().parent / 'web'


class TwinServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self,address):
        super().__init__(address,Handler)
        self.twins={}
        self.sessions_lock=threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(WEB),**kwargs)

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        super().end_headers()

    def reply(self,status,data):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path=='/api/health': return self.reply(200,dict(status='ok',model='original SG / Pyomo / Ipopt'))
        if self.path=='/api/profiles': return self.reply(200,PROFILES)
        if self.path.startswith('/api/'): return self.reply(404,dict(error='Unknown endpoint'))
        super().do_GET()

    def do_POST(self):
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):
            return self.reply(403,dict(error='Cross-origin request denied'))
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.reply(415,dict(error='application/json required'))
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384: raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('Request must be an object')
            if self.path=='/api/session':
                # Expensive full-horizon initialization is outside the session lock.
                with self.server.sessions_lock:
                    now=time.monotonic()
                    for key in list(self.server.twins):
                        if now-self.server.twins[key].last_access>7200: del self.server.twins[key]
                    if len(self.server.twins)>=8: return self.reply(429,dict(error='Too many sessions'))
                twin=Twin(data.get('profile','SG_qs'),data.get('ratio',.01),data.get('variant','optimised'))
                token=uuid.uuid4().hex
                with self.server.sessions_lock: self.server.twins[token]=twin
                return self.reply(200,dict(session=token,snapshot=twin.snapshot()))
            with self.server.sessions_lock: twin=self.server.twins.get(data.get('session'))
            if twin is None: return self.reply(404,dict(error='会话已过期，请刷新网页'))
            with twin.lock:
                twin.last_access=time.monotonic()
                if self.path=='/api/step': return self.reply(200,dict(snapshot=twin.step(data)))
                if self.path=='/api/action':
                    return self.reply(200,dict(snapshot=twin.action(data.get('action'),data.get('ratio'),data.get('temperatures')),
                        history=list(twin.history)))
                if self.path=='/api/reset':
                    fresh=Twin(data.get('profile',twin.profile),data.get('ratio',twin.ratio),data.get('variant',twin.variant))
                    with self.server.sessions_lock: self.server.twins[data['session']]=fresh
                    return self.reply(200,dict(snapshot=fresh.snapshot()))
                if self.path=='/api/history': return self.reply(200,dict(history=list(twin.history)))
                return self.reply(404,dict(error='Unknown endpoint'))
        except (ValueError,TypeError,KeyError,ArithmeticError,RuntimeError) as error:
            self.reply(422,dict(error=str(error),state_preserved=True))
        except Exception:
            import traceback
            traceback.print_exc()
            self.reply(500,dict(error='服务器计算异常，请查看终端日志'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    server=TwinServer(('127.0.0.1',args.port))
    print(f'Open http://127.0.0.1:{args.port} — original seven SG baselines / Ipopt',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__': main()
