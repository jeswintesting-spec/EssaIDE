import asyncio
import json
import os

class LSPClient:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.process = None
        self.req_id = 0
        self.futures = {}
        self.is_ready = False
        self.on_diagnostics = None

    async def start(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                "pylsp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )
            asyncio.create_task(self._read_loop())
            
            # Send initialize
            await self.send_request("initialize", {
                "processId": os.getpid(),
                "rootUri": f"file://{self.workspace_path}",
                "capabilities": {}
            })
            self.send_notification("initialized", {})
            self.is_ready = True
        except Exception as e:
            print(f"Failed to start LSP: {e}")

    async def _read_loop(self):
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line: break
                line = line.decode('utf-8')
                if not line.startswith("Content-Length:"): continue
                length = int(line.split(":")[1].strip())
                
                # Read past headers
                while True:
                    c = await self.process.stdout.readline()
                    if c == b'\r\n': break
                
                content = await self.process.stdout.readexactly(length)
                msg = json.loads(content)
                
                if "id" in msg and msg["id"] in self.futures:
                    if "error" in msg:
                        self.futures[msg["id"]].set_exception(Exception(msg["error"]))
                    else:
                        self.futures[msg["id"]].set_result(msg.get("result"))
                elif "method" in msg and msg["method"] == "textDocument/publishDiagnostics":
                    if self.on_diagnostics:
                        self.on_diagnostics(msg["params"]["uri"], msg["params"]["diagnostics"])
            except Exception:
                pass

    def send_notification(self, method, params):
        if not self.process: return
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        body = json.dumps(msg).encode('utf-8')
        header = f"Content-Length: {len(body)}\r\n\r\n".encode('utf-8')
        self.process.stdin.write(header + body)

    async def send_request(self, method, params):
        if not self.process: return None
        self.req_id += 1
        msg = {"jsonrpc": "2.0", "id": self.req_id, "method": method, "params": params}
        body = json.dumps(msg).encode('utf-8')
        header = f"Content-Length: {len(body)}\r\n\r\n".encode('utf-8')
        
        fut = asyncio.get_running_loop().create_future()
        self.futures[self.req_id] = fut
        
        self.process.stdin.write(header + body)
        try:
            # Add timeout to avoid hanging the UI
            return await asyncio.wait_for(fut, timeout=2.0)
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    def did_open(self, uri: str, text: str):
        self.send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": "python",
                "version": 1,
                "text": text
            }
        })

    def did_change(self, uri: str, text: str):
        self.send_notification("textDocument/didChange", {
            "textDocument": {
                "uri": uri,
                "version": 2,
            },
            "contentChanges": [{"text": text}]
        })

    async def get_completions(self, uri: str, line: int, char: int):
        res = await self.send_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": char}
        })
        return res

    async def get_hover(self, uri: str, line: int, char: int):
        res = await self.send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": char}
        })
        return res

    async def get_definition(self, uri: str, line: int, char: int):
        res = await self.send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": char}
        })
        return res
