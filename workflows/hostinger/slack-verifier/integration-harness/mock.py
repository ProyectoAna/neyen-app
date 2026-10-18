import json,threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
calls=[]; mode={"supabase":"ok","anthropic":"ok","notify":"ok","rpc":"five","slack":"ok"}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def _send(self,code,obj):
        b=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith('/supabase-related'):
            calls.append({'path':self.path,'body':None});return self._send(200,[{'id':'r%d'%i,'file_name':'old_%d'%i,'tags':['t'],'summary':'previo'} for i in range(5)])
        if self.path=='/calls':return self._send(200,calls)
        self._send(404,{})
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0));raw=self.rfile.read(n).decode()
        try:body=json.loads(raw) if raw else None
        except Exception:body=raw
        if self.path=='/control':
            if body.get('reset'):calls.clear()
            mode.update(body.get('mode',{}));return self._send(200,mode)
        calls.append({"path":self.path,"body":body,"hdr_keys":sorted(k.lower() for k in self.headers.keys())})
        if self.path=='/anthropic':
            if mode['anthropic']=='garbage':return self._send(200,{"content":[{"type":"text","text":"not json"}]})
            return self._send(200,{"content":[{"type":"text","text":json.dumps({"tags":["a","b","c"],"entities":["X"],"summary":"Resumen.","narrative_role":"system","date_estimated":"2026","timeline_group":"2024-2026"})}]})
        if self.path.startswith('/supabase-insert'):
            if mode['supabase']=='err200':return self._send(200,{"code":"23502","message":"null value violates not-null constraint"})
            if mode['supabase']=='500':return self._send(500,{"message":"boom"})
            cols={'file_name','type','summary','tags','entities','emotional_tone','source','themes','concepts','keywords','mime_type','cluster','related_ids','date_estimated','timeline_group','narrative_role'}
            if not isinstance(body,dict) or set(body)-cols or not body.get('file_name') or not body.get('source'):return self._send(400,{"code":"PGRST204","message":"unknown column or null"})
            self.send_response(201);self.send_header('Content-Length','0');self.end_headers();return
        if self.path=='/notify':
            if mode['notify']=='err200':return self._send(200,{"status":"error","error":"rpc failed"})
            return self._send(200,{"status":"ok"})
        if self.path=='/supabase-rpc':
            fn=body.get('p_file_name') if isinstance(body,dict) else None
            if mode['rpc']=='err200':return self._send(200,{"code":"P0001","message":"rpc failed"})
            if mode['rpc']=='notfound':return self._send(200,{"status":"error","message":"Entry not found"})
            n=5 if mode['rpc']=='five' else 2
            return self._send(200,{"status":"ok","entry_id":"id-"+str(fn),"file_name":fn,"related_ids":["r%d"%i for i in range(n)],"related_count":n,"tags":["a"],"entities":["X"],"summary":"S"})
        if self.path.startswith('/supabase-related'):
            return self._send(200,[{"id":"r%d"%i,"file_name":"old_%d"%i,"tags":["t"],"summary":"previo"} for i in range(5)])
        if self.path=='/slack':
            if mode['slack']=='err200':return self._send(200,{"ok":False,"error":"channel_not_found"})
            return self._send(200,{"ok":True,"ts":"1"})
        self._send(200,{"ok":True})
ThreadingHTTPServer(('127.0.0.1',9100),H).serve_forever()
