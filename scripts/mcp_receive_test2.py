#!/usr/bin/env python3
import json, subprocess, os, time
p = subprocess.Popen([os.path.expanduser("~/.reason/bin/reason-network"), "mcp"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     text=True, bufsize=1, env=dict(os.environ, REASON_NETWORK_AGENT="kiro", REASON_NETWORK_SESSION="k352-kiro-probe"))
def send(m): p.stdin.write(json.dumps(m)+"\n"); p.stdin.flush()
def read(t=30):
    t0=time.time()
    while time.time()-t0<t:
        l=p.stdout.readline()
        if l.strip(): return json.loads(l)
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"k352","version":"1"}}})
read()
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
send({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_team","arguments":{}}})
team=read(60)
print(team["result"]["content"][0]["text"])
print("### waiting")
time.sleep(20)
send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_inbox","arguments":{}}})
print("inbox:", read(60)["result"]["content"][0]["text"])
p.terminate()
