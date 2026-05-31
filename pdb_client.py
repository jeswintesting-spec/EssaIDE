import asyncio
import re

class PdbWrapper:
    def __init__(self, script_path, cwd):
        self.script_path = script_path
        self.cwd = cwd
        self.process = None
        self.on_line_changed = None
        self.on_output = None
        self.on_finished = None
        
    async def start(self):
        import sys
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pdb", self.script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.cwd
        )
        asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        # Match lines like: > /home/user/file.py(10)<module>()
        pattern = re.compile(r'^>\\s+(.*?)\\((\\d+)\\)')
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line: break
                line_str = line.decode('utf-8', errors='replace')
                
                if self.on_output:
                    self.on_output(line_str)
                    
                m = pattern.search(line_str)
                if m and self.on_line_changed:
                    filepath = m.group(1)
                    lineno = int(m.group(2))
                    if filepath and not filepath.startswith("<"):
                        self.on_line_changed(filepath, lineno)
            except Exception:
                break

        if self.on_finished:
            self.on_finished()

    def send_command(self, cmd: str):
        if self.process and self.process.stdin:
            self.process.stdin.write(f"{cmd}\\n".encode('utf-8'))
            
    def terminate(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception: pass
