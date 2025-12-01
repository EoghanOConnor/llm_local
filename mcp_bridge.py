
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, Set

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse
import uvicorn

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

class StdioProcess:
    def __init__(self, command: str, args: list[str], env: dict[str, str]):
        self.command = command
        self.args = args
        self.env = env
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.queues: Set[asyncio.Queue] = set()
        self.read_task: Optional[asyncio.Task] = None

    async def start(self):
        print(f"Starting process: {self.command} {self.args}")
        self.proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=sys.stderr,
            env={**os.environ, **self.env}
        )
        self.read_task = asyncio.create_task(self._bg_read_loop())

    async def write(self, message: dict):
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Process not running")
        
        data = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + data)
        await self.proc.stdin.drain()

    async def _bg_read_loop(self):
        """Single background reader that broadcasts to all connected queues."""
        if not self.proc or not self.proc.stdout:
            return
        
        while True:
            try:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode("ascii", errors="replace").strip()
                if not line_str:
                    continue
                
                msg = None
                if line_str.lower().startswith("content-length:"):
                    length = int(line_str.split(":", 1)[1].strip())
                    # Read empty line
                    await self.proc.stdout.readline()
                    # Read body
                    body = await self.proc.stdout.readexactly(length)
                    msg = json.loads(body)
                elif line_str.startswith("{"):
                    msg = json.loads(line)
                
                if msg:
                    # Broadcast to all active queues
                    for q in list(self.queues):
                        await q.put(msg)
            except Exception as e:
                print(f"Error in read loop: {e}", file=sys.stderr)
                await asyncio.sleep(0.1)

    async def subscribe(self):
        q = asyncio.Queue()
        self.queues.add(q)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            self.queues.remove(q)

process_wrapper = None

async def sse_endpoint(request):
    print(f"SSE endpoint called")
    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Query Params: {dict(request.query_params)}")
    print(f"Body: {await request.body()}")
    async def event_generator():
        # Send initial connection message to establish stream immediately
        # Use simple string replacement to avoid URL object issues
        base_url = str(request.url).split("/sse")[0]
        messages_url = f"{base_url}/messages"
        
        yield {
            "event": "endpoint",
            "data": messages_url
        }
        
        if not process_wrapper:
            return
        async for message in process_wrapper.subscribe():
            print(f"<- {json.dumps(message)[:100]}...", file=sys.stderr)
            yield {
                "event": "message",
                "data": json.dumps(message)
            }

    return EventSourceResponse(
        event_generator(), 
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

async def messages_endpoint(request):
    if request.method == "GET":
        print(f"GET request to /messages")
        return JSONResponse({"status": "ok", "message": "Send POST requests to this endpoint"})
        
    body = await request.json()
    print(f"SSE endpoint called")
    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Query Params: {dict(request.query_params)}")
    print(f"-> {json.dumps(body)[:100]}...", file=sys.stderr)
    if process_wrapper:
        await process_wrapper.write(body)
    return JSONResponse({"status": "accepted"})

def load_config():
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    servers = config.get("mcpServers", {})
    if "atlassian" in servers:
        return servers["atlassian"]
    if servers:
        return list(servers.values())[0]
    print("No servers found in config")
    sys.exit(1)

async def lifespan(app):
    global process_wrapper
    server_config = load_config()
    process_wrapper = StdioProcess(
        server_config["command"], 
        server_config["args"], 
        server_config.get("env", {})
    )
    await process_wrapper.start()
    yield
    if process_wrapper.proc:
        try:
            process_wrapper.proc.terminate()
        except:
            pass
    if process_wrapper.read_task:
        process_wrapper.read_task.cancel()

routes = [
    Route("/sse", endpoint=sse_endpoint),
    Route("/messages", endpoint=messages_endpoint, methods=["GET", "POST"]),
]

app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    uvicorn.run("mcp_bridge:app", host="0.0.0.0", port=8090, reload=False)
