#!/usr/bin/env python3
"""REST path used by hosted assistants: list agents, send, resume. Token never printed."""
import json, sys, time, urllib.request, pathlib

creds = json.loads((pathlib.Path.home()/".config/reason/credentials.json").read_text())
TOKEN = creds["accessToken"]
ORG = creds["orgId"]
BASE = "https://api.reasonmachines.com"

def call(method, path, body=None):
    req = urllib.request.Request(BASE+path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": "Bearer "+TOKEN, "Content-Type": "application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, time.time()-t0, json.loads(r.read() or b"{}")

mode = sys.argv[1]
if mode == "who":
    st, dt, js = call("GET", f"/v3/organizations/{ORG}/agent-network/agents")
    print(f"GET agents -> HTTP {st} in {dt:.2f}s")
    for a in js.get("agents", [])[:20]:
        print(" ", a.get("address"), a.get("agent"), a.get("status"))
elif mode == "ask":
    msg = sys.argv[2]; rid = sys.argv[3] if len(sys.argv)>3 else None
    body = {"to":"kazuki0205-84/codex","message":msg,"wait_seconds":45}
    if rid: body["request_id"]=rid
    st, dt, js = call("POST", f"/v3/organizations/{ORG}/agent-network/messages", body)
    print(json.dumps({"http":st,"secs":round(dt,2),"status":js.get("status"),"request_id":js.get("request_id"),
                      "answer":(js.get("answer") or {}).get("body")}, ensure_ascii=False))
