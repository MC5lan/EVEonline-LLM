"""HTTP 服务：给外部（前端、脚本、其它系统）用的接口。

三个端点：
  POST /chat    多轮对话（带 session_id 延续上下文）
  POST /search  只检索，不生成（调试与外部拼装用）
  GET  /        极简聊天页，浏览器直接打开就能用

启动：
  python -m serve.api --port 8000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

app = FastAPI(title="EVE 助手", version="1.0")
_d: "Dialogue | None" = None


def dialogue():
    global _d
    if _d is None:
        from rag.dialogue import Dialogue
        _d = Dialogue()
    return _d


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


class SearchIn(BaseModel):
    query: str
    topk: int = 3


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(inp: ChatIn) -> dict:
    r = dialogue().ask(inp.message, inp.session_id)
    return {"session_id": r["session_id"], "answer": r["answer"],
            "rewritten": r["rewritten"], "blocked": r["blocked"],
            "entity": r["entity"], "sources": r["sources"]}


@app.post("/search")
def search(inp: SearchIn) -> dict:
    hits = dialogue().retriever.search(inp.query, k=inp.topk)
    return {"hits": [{"source": h.get("source"), "score": round(h.get("score", 0), 3),
                      "text": h["text"][:300]} for h in hits]}


PAGE = """<!doctype html>
<meta charset="utf-8"><title>EVE 助手</title>
<style>
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:720px;
      margin:40px auto;padding:0 16px;background:#0f1115;color:#e6e6e6}
 #log{height:60vh;overflow-y:auto;border:1px solid #2a2f3a;border-radius:8px;
      padding:12px;background:#151922}
 .u{color:#7cc4ff;margin:10px 0 2px} .a{color:#d8d8d8;white-space:pre-wrap;margin:0 0 12px}
 .m{color:#8a8f98;font-size:12px;margin:2px 0 8px}
 #bar{display:flex;gap:8px;margin-top:12px}
 input{flex:1;padding:10px;border-radius:8px;border:1px solid #2a2f3a;background:#151922;color:#e6e6e6}
 button{padding:10px 18px;border-radius:8px;border:0;background:#2f6fed;color:#fff;cursor:pointer}
</style>
<div id="log"></div>
<div id="bar"><input id="q" placeholder="问点什么…（例：毒蜥级的护盾容量是多少）" autofocus>
<button onclick="send()">发送</button></div>
<script>
let sid=null;
function add(cls,txt){const d=document.createElement('div');d.className=cls;d.textContent=txt;
  document.getElementById('log').appendChild(d);
  document.getElementById('log').scrollTop=1e9;}
async function send(){
  const q=document.getElementById('q'); const v=q.value.trim(); if(!v)return;
  q.value=''; add('u','你：'+v);
  const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:v,session_id:sid})});
  const j=await r.json(); sid=j.session_id;
  if(j.rewritten) add('m','（改写：'+j.rewritten+'）');
  if(j.blocked) add('m','⚠️ '+j.blocked);
  add('a','助手：'+j.answer);
  if(j.sources&&j.sources.length) add('m','来源：'+j.sources.join(' / '));
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
</script>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    import uvicorn
    print(f"[serve] 打开 http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
