#!/usr/bin/env python3
"""Minimal stdio MCP probe: initialize, tools/list, optional tools/call."""
import json, subprocess, sys, os, threading, time

cmd = sys.argv[1:] or [os.path.expanduser("~/.reason/bin/reason-network"), "mcp"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

def send(msg):
    p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()

def read(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = p.stdout.readline()
        if line.strip():
            return json.loads(line)
    return None

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"k352-probe","version":"1"}}})
init = read()
print("initialize:", json.dumps(init)[:600])
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
send({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
tl = read()
tools = [t.get("name") for t in (tl or {}).get("result", {}).get("tools", [])]
print("tools:", tools)
if os.environ.get("CALL"):
    name, arg_json = os.environ["CALL"].split("=", 1)
    send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":name,"arguments":json.loads(arg_json)}})
    print("call:", json.dumps(read(60))[:1500])
p.terminate()
