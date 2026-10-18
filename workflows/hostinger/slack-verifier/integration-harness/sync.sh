export PATH=/workspace/n8ntest/node_modules/.bin:$PATH N8N_USER_FOLDER=/workspace/n8ntest/home N8N_ENCRYPTION_KEY=fake-test-key-not-secret
cd /workspace/n8ntest
pkill -f "n8n start"; pkill -f "python3 mock.py"; pkill -f "postgrest /workspace"; sleep 2
(nohup python3 mock.py > mock.log 2>&1 &)
/workspace/pgvenv/bin/python /workspace/neyen-app/workflows/hostinger/slack-verifier/integration-harness/pg_setup.py
(nohup /workspace/postgrest /workspace/n8ntest/postgrest.conf > pgrst.log 2>&1 &)
python3 - <<'P'
import json
jwt=open('/workspace/n8ntest/test.jwt').read()
c=json.load(open('/workspace/n8ntest/creds.json'))
for x in c:
    if x['type']=='supabaseApi': x['data']={"host":"http://127.0.0.1:3000","serviceRole":jwt}
json.dump(c,open('/workspace/n8ntest/creds.json','w'))
P
n8n import:credentials --input=creds.json >/dev/null 2>&1
python3 - <<'P'
import json
E=lambda n:'/workspace/neyen-app/workflows/hostinger/essential/'+n
M='http://127.0.0.1:9100'; N='http://127.0.0.1:5680'
cmap={'Internal Webhook Header':'c1','Header Auth account':'c2','Supabase account':'c3','Slack account':'c4'}
def load(f,wid,subs,path=None):
    s=open(E(f)).read()
    for a,b in subs:
        assert a in s,a
        s=s.replace(a,b)
    d=json.loads(s);d['id']=wid
    for n in d['nodes']:
        for v in (n.get('credentials') or {}).values(): v['id']=cmap.get(v['name'],v['id'])
        if path and n['type']=='n8n-nodes-base.webhook': n['parameters']['path']=path
    return d
SB='https://gsmtzdramqzcqdywboro.supabase.co/rest/v1/'
W2='https://n8n.thespiralwithin.ai/webhook/wf02-crosslink'; W3='https://n8n.thespiralwithin.ai/webhook/wf03-crosslink-notify'
common=[('https://api.anthropic.com/v1/messages',M+'/anthropic'),(SB+'metadata?on_conflict=file_name',M+'/supabase-insert'),('https://slack.com/api/chat.postMessage',M+'/slack')]
FB=("const CONFIGURED_CHANNEL = '';","const CONFIGURED_CHANNEL = 'CTESTFALLBACK';")
wfs=[
 load('NEYEN-ingest.json','wf01test',common+[(W2,M+'/notify')]),
 load('NEYEN-ingest.json','wf01chain',common+[(W2,N+'/webhook/wf02-crosslink')],'wf01-ingest-chain'),
 load('NEYEN-ingest.json','wf01chainnofb',common+[(W2,N+'/webhook/wf02-crosslink-nofb')],'wf01-ingest-chain-nofb'),
 load('NEYEN-crosslink.json','wf02test',[(SB+'rpc/crosslink_entry',M+'/supabase-rpc'),(W3,N+'/webhook/wf03-crosslink-notify')]),
 load('NEYEN-crosslink.json','wf02nofb',[(SB+'rpc/crosslink_entry',M+'/supabase-rpc'),(W3,N+'/webhook/wf03-notify-nofb')],'wf02-crosslink-nofb'),
 load('NEYEN-crosslink-notify.json','wf03test',[(SB+'metadata?select=id,file_name,tags,summary&id=in.(',M+'/supabase-related?id=in.('),('https://slack.com/api/chat.postMessage',M+'/slack'),(SB+'notification_reservations','http://127.0.0.1:3000/notification_reservations'),FB]),
 load('NEYEN-crosslink-notify.json','wf03nofb',[(SB+'metadata?select=id,file_name,tags,summary&id=in.(',M+'/supabase-related?id=in.('),('https://slack.com/api/chat.postMessage',M+'/slack'),(SB+'notification_reservations','http://127.0.0.1:3000/notification_reservations')],'wf03-notify-nofb'),
]
json.dump(wfs,open('all-test.json','w'))
P
n8n import:workflow --input=all-test.json 2>&1 | grep -E "Success|Cannot|rror" | head -3
for i in wf01test wf01chain wf01chainnofb wf02test wf02nofb wf03test wf03nofb; do n8n publish:workflow --id=$i >/dev/null 2>&1; done
N8N_PORT=5680 N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false nohup n8n start > n8n.log 2>&1 &
# segunda replica de n8n (carpeta y SQLite propias, mismo contenido)
export N8N_USER_FOLDER=/workspace/n8ntest/home_r2; rm -rf $N8N_USER_FOLDER
n8n import:credentials --input=creds.json >/dev/null 2>&1; n8n import:workflow --input=all-test.json >/dev/null 2>&1
for i in wf01test wf01chain wf01chainnofb wf02test wf02nofb wf03test wf03nofb; do n8n publish:workflow --id=$i >/dev/null 2>&1; done
N8N_PORT=5681 N8N_RUNNERS_BROKER_PORT=5689 N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false nohup n8n start > n8n_r2.log 2>&1 &
sleep 30; tail -2 n8n.log
