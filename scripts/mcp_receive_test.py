#!/usr/bin/env python3
"""Prove pull-receive: register a fixed session, wait, then check_inbox."""
import json, subprocess, sys, os, time

env = dict(os.environ, REASON_NETWORK_AGENT="kiro", REASON_NETWORK_SESSION="k352-kiro-probe")
p = subprocess.Popen([os.path.expanduser("~/.reason/bin/reason-network"), "mcp"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     text=True, bufsize=1, env=env)

def send(m):
    p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()

def read(timeout=30):
    t0=time.time()
    while time.time()-t0<timeout:
        line=p.stdout.readline()
        if line.strip(): return json.loads(line)
    return None

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"k352-recv","version":"1"}}})
read()
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
send({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_team","arguments":{}}})
team = read()
print("list_team address line:", [l for l in team["result"]["content"][0]["text"].splitlines() if "k352-kiro-probe" in l])
print("WAITING 25s for an external send ...", flush=True)
time.sleep(25)
send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_inbox","arguments":{}}})
inbox = read(60)
print("check_inbox:", json.dumps(inbox["result"]["content"][0]["text"])[:800])
p.terminate()
