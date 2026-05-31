import sys
import asyncio
import requests
import argparse
import ast
import code
import io
from pathlib import Path

# Add EssaCache to path so we can import the client
sys.path.append(str(Path(__file__).parent.parent / "EssaCache"))
try:
    from essacache.client import EssaCacheClient
except ImportError:
    EssaCacheClient = None

from textual import on, events
from textual.message import Message
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    DirectoryTree,
    TextArea,
    RichLog,
    Label,
    Input,
    TabbedContent,
    TabPane,
    Static,
    Button,
    Tree,
    Switch,
    DataTable,
    ContentSwitcher,
    Select,
    OptionList,
)


class MenuLabel(Label):
    """A clickable label for the menu bar."""

    class Clicked(Message):
        def __init__(self, label_id: str) -> None:
            self.label_id = label_id
            super().__init__()

    async def on_click(self, event: events.Click) -> None:
        event.stop()
        if self.id:
            self.post_message(self.Clicked(self.id))


class VerticalResizer(Static):
    """A vertical drag handle to resize left/right panels."""

    def __init__(self, target_id: str, offset: int = 0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_id = target_id
        self.drag_offset = offset
        self._dragging = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self._dragging = True
            self.capture_mouse()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._dragging = False
        self.release_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            try:
                target = self.app.query_one(f"#{self.target_id}")
                target.styles.width = max(10, event.screen_x - self.drag_offset)
            except Exception:
                pass


class HorizontalResizer(Static):
    """A horizontal drag handle to resize top/bottom panels."""

    def __init__(self, target_id: str, offset: int = 0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_id = target_id
        self.drag_offset = offset
        self._dragging = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self._dragging = True
            self.capture_mouse()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._dragging = False
        self.release_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            try:
                target = self.app.query_one(f"#{self.target_id}")
                new_height = (
                    self.app.console.size.height - event.screen_y - self.drag_offset
                )
                target.styles.height = max(5, new_height)
            except Exception:
                pass


class StatusBar(Horizontal):
    """A VS Code-style Status Bar for the IDE."""

    def compose(self) -> ComposeResult:
        yield Label(" 📄 Plain Text ", id="status-file", classes="status-item")
        yield Label("Ln 1, Col 1", id="status-cursor", classes="status-item")
        yield Label("UTF-8", id="status-encoding", classes="status-item")
        yield Label("✅ Linter: Ready", id="status-linter", classes="status-item")


class SQLQueryPane(Vertical):
    """A full-featured SQLite query engine widget."""

    CSS = """
    SQLQueryPane {
        layout: vertical;
        height: 1fr;
    }
    #sql-toolbar {
        height: 1;
        background: #1a1b26;
        layout: horizontal;
    }
    #sql-status {
        width: 1fr;
        content-align: left middle;
        padding: 0 1;
        color: #a9b1d6;
    }
    .sql-action-btn {
        height: 1;
        min-width: 12;
        border: none;
        background: #3d59a1;
        color: white;
    }
    .sql-action-btn:hover { background: #7aa2f7; }
    #sql-body {
        height: 1fr;
        layout: horizontal;
    }
    #sql-tables-panel {
        width: 22;
        border-right: solid #3d59a1;
        layout: vertical;
        background: #16161e;
    }
    #sql-tables-title {
        height: 1;
        background: #24283b;
        color: #bb9af7;
        padding: 0 1;
        text-style: bold;
    }
    #sql-tables-tree {
        height: 1fr;
        background: #16161e;
    }
    #sql-editor-panel {
        width: 1fr;
        layout: vertical;
    }
    #sql-editor {
        height: 8;
        border-bottom: solid #3d59a1;
    }
    #sql-results {
        height: 1fr;
        background: #1a1b26;
    }
    """

    def __init__(self, db_path: str, widget_id: str):
        super().__init__(id=widget_id)
        self.db_path = db_path
        self._db_tables = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="sql-toolbar"):
            yield Label("⚡ Ready", id="sql-status")
            b1 = Button("▶ Run (F5)", id="sql-run", classes="sql-action-btn")
            yield b1
            b2 = Button("📋 Export CSV", id="sql-export", classes="sql-action-btn")
            yield b2
        with Horizontal(id="sql-body"):
            with Vertical(id="sql-tables-panel"):
                yield Label("Tables", id="sql-tables-title")
                yield Tree("📁 Database", id="sql-tables-tree")
            with Vertical(id="sql-editor-panel"):
                yield TextArea(
                    "SELECT * FROM sqlite_master WHERE type='table';",
                    id="sql-editor",
                    language="sql",
                    show_line_numbers=True,
                    theme=getattr(self.app, "settings", {}).get(
                        "editor_theme", "monokai"
                    ),
                )
                yield DataTable(id="sql-results")

    def on_mount(self) -> None:
        self._load_schema()

    def _load_schema(self) -> None:
        import sqlite3

        tree = self.query_one("#sql-tables-tree", Tree)
        tree.root.remove_children()
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = [r[0] for r in cur.fetchall()]
            self._db_tables = tables
            for tname in tables:
                cur.execute(f"PRAGMA table_info({tname})")
                cols = cur.fetchall()
                t_node = tree.root.add(f"🗃 {tname}", expand=False)
                for col in cols:
                    icon = "🔑" if col[5] else "▪"
                    t_node.add_leaf(f"{icon} {col[1]} ({col[2]})", data=tname)
            conn.close()
            tree.root.expand()
            status = self.query_one("#sql-status", Label)
            status.update(f"⚡ {len(tables)} table(s) found")
        except Exception as e:
            self.query_one("#sql-status", Label).update(f"[red]Schema Error: {e}[/red]")

    @on(Tree.NodeSelected, "#sql-tables-tree")
    def on_table_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data:
            editor = self.query_one("#sql-editor", TextArea)
            editor.load_text(f"SELECT * FROM {event.node.data} LIMIT 100;")

    @on(Button.Pressed, "#sql-run")
    def run_query(self) -> None:
        import sqlite3, time

        sql = self.query_one("#sql-editor", TextArea).text.strip()
        if not sql:
            return
        status = self.query_one("#sql-status", Label)
        results = self.query_one("#sql-results", DataTable)
        results.clear(columns=True)
        status.update("⏳ Executing...")
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            t0 = time.perf_counter()
            cur.execute(sql)
            elapsed = (time.perf_counter() - t0) * 1000
            if cur.description:
                cols = [d[0] for d in cur.description]
                results.add_columns(*cols)
                rows = cur.fetchmany(500)
                for row in rows:
                    results.add_row(*[str(c) if c is not None else "NULL" for c in row])
                status.update(f"✅ {len(rows)} row(s) · {elapsed:.1f}ms")
            else:
                conn.commit()
                status.update(
                    f"✅ Query OK · {cur.rowcount} row(s) affected · {elapsed:.1f}ms"
                )
                self._load_schema()
            self._last_rows = cur.fetchall() if cur.description else []
            self._last_cols = [d[0] for d in cur.description] if cur.description else []
            conn.close()
        except Exception as e:
            status.update(f"[red]❌ {e}[/red]")

    @on(Button.Pressed, "#sql-export")
    def export_csv(self) -> None:
        import csv, io

        results = self.query_one("#sql-results", DataTable)
        if not results.columns:
            return
        out_path = Path(self.db_path).with_suffix(".csv")
        try:
            col_keys = list(results.columns.keys())
            col_labels = [str(results.columns[k].label) for k in col_keys]
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(col_labels)
                for row_key in results.rows.keys():
                    writer.writerow(
                        [str(results.get_cell(row_key, col)) for col in col_keys]
                    )
            self.query_one("#sql-status", Label).update(
                f"✅ Exported → {out_path.name}"
            )
        except Exception as e:
            self.query_one("#sql-status", Label).update(
                f"[red]Export failed: {e}[/red]"
            )


class CommandPaletteModal(ModalScreen):
    """Fuzzy command palette (Ctrl+Shift+P)."""

    CSS = """
    CommandPaletteModal { align: center top; background: $surface 60%; }
    #cp-dialog {
        width: 70;
        max-height: 30;
        background: #1a1b26;
        border: solid #7aa2f7;
        margin-top: 3;
    }
    #cp-input { border: none; background: #24283b; }
    #cp-list { height: 1fr; background: #1a1b26; }
    .cp-item {
        padding: 0 2;
        height: 1;
        color: #a9b1d6;
    }
    .cp-item:hover { background: #3d59a1; color: white; }
    """
    COMMANDS = [
        ("📁  Open Folder", "open_folder"),
        ("📄  New File", "new_file"),
        ("💾  Save File", "save"),
        ("🔍  Search in Files", "search"),
        ("↔️  Toggle Split View", "toggle_split"),
        ("💻  Toggle Bottom Panel", "toggle_panel"),
        ("🗂️  Toggle Sidebar", "toggle_sidebar"),
        ("🎨  Toggle Dark Mode", "toggle_dark"),
        ("▶️  Run Code", "run_code"),
        ("🐞  Debug File", "run_debugger"),
        ("⏱️  Profile Run", "profile_run"),
        ("🌐  Toggle Live Server", "start_live_server"),
        ("🧩  LSP: Autocomplete", "autocomplete"),
        ("🧩  LSP: Go To Definition", "go_definition"),
        ("🧩  LSP: Hover Docs", "hover_docs"),
        ("✨  Format Code (F8)", "format_code"),
        ("📝  Preview Markdown", "preview_markdown"),
        ("🗑️  Delete File", "delete_file"),
        ("❌  Close Tab", "close_tab"),
        ("🪟  New Window", "new_window"),
        ("↑  Go Up Directory", "go_up_dir"),
        ("🔴  Toggle Breakpoint", "toggle_breakpoint"),
        ("⭐  Quit EssaIDE", "quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="cp-dialog"):
            yield Input(
                placeholder="\u2315 Type a command or filename...", id="cp-input"
            )
            with VerticalScroll(id="cp-list"):
                for label, action in self.COMMANDS:
                    lbl = Label(label, classes="cp-item")
                    lbl.action = action
                    yield lbl

    def on_mount(self) -> None:
        self.query_one("#cp-input").focus()

    @on(Input.Changed, "#cp-input")
    def filter_commands(self, event: Input.Changed) -> None:
        q = event.value.lower()
        for item in self.query(".cp-item"):
            item.display = q in str(item.renderable).lower()

    @on(Input.Submitted, "#cp-input")
    def run_first_visible(self) -> None:
        for item in self.query(".cp-item"):
            if item.display:
                self._execute(item.action)
                return

    @on(events.Click)
    def on_label_clicked(self, event: events.Click) -> None:
        lbl = event.widget
        if isinstance(lbl, Label) and hasattr(lbl, "action"):
            self._execute(lbl.action)

    def _execute(self, action: str) -> None:
        self.dismiss()
        self.app.call_after_refresh(lambda: self.app.run_action(action))


class UnsavedChangesModal(ModalScreen):
    """Confirmation dialog when quitting with unsaved files."""

    CSS = """
    UnsavedChangesModal { align: center middle; background: $surface 70%; }
    #unsaved-dialog {
        width: 60; height: auto;
        background: #1a1b26;
        border: solid #f7768e;
        padding: 2 3;
    }
    #unsaved-title { color: #f7768e; text-style: bold; margin-bottom: 1; }
    #unsaved-buttons { height: 3; align: center middle; layout: horizontal; }
    """

    def __init__(self, count: int):
        super().__init__()
        self.count = count

    def compose(self) -> ComposeResult:
        with Vertical(id="unsaved-dialog"):
            yield Label(
                f"\u26a0\ufe0f  {self.count} unsaved file(s)", id="unsaved-title"
            )
            yield Label("You have unsaved changes. What would you like to do?")
            with Horizontal(id="unsaved-buttons"):
                yield Button(
                    "\ud83d� Save All & Quit", id="btn-save-quit", variant="success"
                )
                yield Button("\u274c Quit Anyway", id="btn-force-quit", variant="error")
                yield Button("\u21a9  Cancel", id="btn-cancel-quit", variant="primary")

    @on(Button.Pressed, "#btn-save-quit")
    def save_quit(self):
        self.dismiss("save")

    @on(Button.Pressed, "#btn-force-quit")
    def force_quit(self):
        self.dismiss("force")

    @on(Button.Pressed, "#btn-cancel-quit")
    def cancel(self):
        self.dismiss(None)


class GlobalReplaceModal(ModalScreen):
    """Modal for Global Workspace-Wide Mass Refactoring."""

    CSS = """
    GlobalReplaceModal {
        align: center middle;
    }
    #replace-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: #1a1b26;
        border: solid #7aa2f7;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="replace-dialog"):
            yield Label("[bold cyan]Workspace-Wide Mass Refactoring[/bold cyan]\n")
            yield Input(placeholder="Target word to find...", id="target-input")
            yield Input(placeholder="Replacement word...", id="replace-input")
            with Horizontal():
                yield Button("Cancel", id="btn-cancel-replace", variant="error")
                yield Button(
                    "Refactor All Files", id="btn-run-replace", variant="success"
                )

    @on(Button.Pressed, "#btn-cancel-replace")
    def cancel(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-run-replace")
    def run_replace(self):
        target = self.query_one("#target-input", Input).value
        replacement = self.query_one("#replace-input", Input).value
        if not target:
            return
        self.app.pop_screen()
        self.app.execute_global_replace(target, replacement)


class SplashScreen(ModalScreen):
    """A beautiful ASCII splash screen."""

    CSS = """
    SplashScreen {
        align: center middle;
        background: $surface;
    }
    
    #splash-logo {
        content-align: center middle;
        text-style: bold;
        color: green;
    }
    
    #splash-loading {
        content-align: center middle;
        margin-top: 2;
        color: white;
    }
    """

    def compose(self) -> ComposeResult:
        logo = r"""
  ______               _____ _____  ______ 
 |  ____|             |_   _|  __ \|  ____|
 | |__   ___ ___  __ _  | | | |  | | |__   
 |  __| / __/ __|/ _` | | | | |  | |  __|  
 | |____\__ \__ \ (_| |_| |_| |__| | |____ 
 |______|___/___/\__,_|_____|_____/|______|
                                           
        """
        yield Static(logo, id="splash-logo")
        yield Static("Initializing Workspace Components...", id="splash-loading")


class WorkspaceTrustModal(ModalScreen):
    """VS Code-style Workspace Trust dialog."""

    CSS = """
    WorkspaceTrustModal {
        align: center middle;
        background: $surface 80%;
    }
    #trust-dialog {
        width: 70;
        height: auto;
        background: #1a1b26;
        border: solid #f7768e;
        padding: 2 3;
    }
    #trust-title {
        text-style: bold;
        color: #f7768e;
        content-align: center middle;
        margin-bottom: 1;
    }
    #trust-body {
        color: #a9b1d6;
        margin-bottom: 2;
    }
    #trust-path {
        background: #24283b;
        color: #7aa2f7;
        padding: 0 1;
        margin-bottom: 2;
    }
    #trust-buttons {
        height: 3;
        align: center middle;
        layout: horizontal;
    }
    """

    def __init__(self, workspace_path: str):
        super().__init__()
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        with Vertical(id="trust-dialog"):
            yield Label("🔒 Do you trust this workspace?", id="trust-title")
            yield Label(
                "EssaIDE plugins can run arbitrary code. Only trust workspaces\n"
                "you created yourself or obtained from a source you trust.",
                id="trust-body",
            )
            yield Label(f"📂 {self.workspace_path}", id="trust-path")
            with Horizontal(id="trust-buttons"):
                yield Button(
                    "✅ Yes, I trust this workspace", id="btn-trust", variant="success"
                )
                yield Button("🚫 No, restrict plugins", id="btn-deny", variant="error")

    @on(Button.Pressed, "#btn-trust")
    def trust(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn-deny")
    def deny(self):
        self.dismiss(False)


class FolderPicker(ModalScreen):
    """A screen to pick a folder to open."""

    BINDINGS = [("o", "open_selected", "Open Folder"), ("escape", "cancel", "Cancel")]

    CSS = """
    FolderPicker {
        align: center middle;
        background: $surface 80%;
    }
    
    #picker-container {
        width: 80%;
        height: 80%;
        background: $panel;
        border: solid green;
    }
    
    #picker-tree {
        height: 1fr;
    }
    
    #picker-input {
        height: 3;
    }
    
    #picker-buttons {
        height: 3;
        align: center middle;
    }
    
    #picker-title {
        dock: top;
        height: 1;
        content-align: center middle;
        background: green;
        color: white;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-container"):
            yield Label(
                "Select Folder (Press 'O' to Open, Esc to Cancel)", id="picker-title"
            )
            yield DirectoryTree(str(Path.home()), id="picker-tree")
            yield Input(placeholder="Path to open...", id="picker-input")
            with Horizontal(id="picker-buttons"):
                yield Button("Open Folder", id="btn-open", variant="success")
                yield Button("Cancel", id="btn-close", variant="error")

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        event.stop()
        inp = self.query_one("#picker-input", Input)
        inp.value = str(event.path)

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        event.stop()
        inp = self.query_one("#picker-input", Input)
        inp.value = str(event.path.parent)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "picker-input":
            path_str = event.value
            if not path_str:
                return
            target = Path(path_str).expanduser().absolute()
            if target.is_dir():
                self.dismiss(target)
            else:
                event.input.value = "Error: Not a directory!"

    def action_open_selected(self) -> None:
        inp = self.query_one("#picker-input", Input)
        if inp.value:
            target = Path(inp.value)
            if target.is_dir():
                self.dismiss(target)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-open")
    def on_btn_open(self, event: Button.Pressed) -> None:
        self.action_open_selected()

    @on(Button.Pressed, "#btn-close")
    def on_btn_close(self, event: Button.Pressed) -> None:
        self.action_cancel()


class SettingsDashboard(ModalScreen):
    """IDE Settings Dashboard."""

    BINDINGS = [("escape", "dismiss_settings", "Close Settings")]

    CSS = """
    SettingsDashboard {
        align: center middle;
        background: $surface 80%;
    }
    
    #settings-container {
        width: 60%;
        height: auto;
        background: $panel;
        border: solid green;
        padding: 1 2;
    }
    
    .setting-row {
        layout: horizontal;
        height: 3;
        align: left middle;
    }
    
    .setting-label {
        width: 1fr;
        content-align: left middle;
    }
    
    #settings-title {
        dock: top;
        height: 1;
        content-align: center middle;
        background: green;
        color: white;
        margin-bottom: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("⚙️ EssaIDE Settings (Esc to close)", id="settings-title")

            app = self.app

            with Horizontal(classes="setting-row"):
                yield Label("Auto-Format on Save (Black)", classes="setting-label")
                yield Switch(
                    value=app.settings.get("auto_format", True),
                    id="setting-auto_format",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Real-Time Python Linter", classes="setting-label")
                yield Switch(
                    value=app.settings.get("linter", True), id="setting-linter"
                )

            with Horizontal(classes="setting-row"):
                yield Label("Show Line Numbers", classes="setting-label")
                yield Switch(
                    value=app.settings.get("line_numbers", True),
                    id="setting-line_numbers",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Use EssaCache Hot-Loading", classes="setting-label")
                yield Switch(
                    value=app.settings.get("cache_enabled", True),
                    id="setting-cache_enabled",
                )

            with Horizontal(classes="setting-row"):
                yield Label("Dark Mode Theme", classes="setting-label")
                yield Switch(value=app.theme == "textual-dark", id="setting-dark_mode")

            with Horizontal(classes="setting-row"):
                yield Label("Editor Theme", classes="setting-label")
                current_theme = app.settings.get("editor_theme", "monokai")
                yield Select(
                    [
                        ("Monokai", "monokai"),
                        ("VS Code Dark", "vscode_dark"),
                        ("GitHub Light", "github_light"),
                        ("Dracula", "dracula"),
                    ],
                    id="setting-editor_theme",
                    value=current_theme,
                )

    @on(Select.Changed, "#setting-editor_theme")
    def on_theme_changed(self, event: Select.Changed) -> None:
        if event.value != Select.BLANK:
            self.app.settings["editor_theme"] = event.value
            for editor in self.app.query(TextArea):
                editor.theme = event.value

    def on_switch_changed(self, event: Switch.Changed) -> None:
        setting_id = event.switch.id
        app = self.app
        if setting_id == "setting-auto_format":
            app.settings["auto_format"] = event.value
        elif setting_id == "setting-linter":
            app.settings["linter"] = event.value
            linter_lbl = app.query_one("#status-linter", Label)
            linter_lbl.display = event.value
        elif setting_id == "setting-line_numbers":
            app.settings["line_numbers"] = event.value
            for editor in app.query(TextArea):
                editor.show_line_numbers = event.value
        elif setting_id == "setting-cache_enabled":
            app.settings["cache_enabled"] = event.value
        elif setting_id == "setting-dark_mode":
            app.theme = "textual-dark" if event.value else "textual-light"

    def action_dismiss_settings(self) -> None:
        self.dismiss()


class TerminalArea(Vertical):
    """An interactive terminal emulator and log."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import os

        self.cwd = os.getcwd()

    def compose(self) -> ComposeResult:
        log = RichLog(id="term-log", wrap=True, markup=True)
        log.styles.height = "1fr"
        yield log
        inp = Input(placeholder="$ Type a command and press Enter...", id="term-input")
        inp.styles.dock = "bottom"
        yield inp

    def write(self, data: str) -> None:
        try:
            self.query_one("#term-log", RichLog).write(data)
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self.query_one("#term-log", RichLog).clear()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "term-input":
            return
        cmd = event.value
        if not cmd:
            return
        event.input.value = ""
        log = self.query_one("#term-log", RichLog)

        import os

        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            if target == "~":
                target = os.path.expanduser("~")
            try:
                os.chdir(target)
                self.cwd = os.getcwd()
                log.write(
                    f"[bold blue]$ {cmd}[/bold blue]\n[green]Changed directory to {self.cwd}[/green]"
                )
            except Exception as e:
                log.write(f"[bold blue]$ {cmd}[/bold blue]\n[red]{e}[/red]")
            return

        log.write(f"[bold blue]$ {cmd}[/bold blue]")

        try:
            import asyncio

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )

            async def read_stream(stream, is_stderr):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if is_stderr:
                        log.write(f"[red]{text}[/red]")
                    else:
                        log.write(text)

            await asyncio.gather(
                read_stream(process.stdout, False), read_stream(process.stderr, True)
            )
            await process.wait()
        except Exception as e:
            log.write(f"[red]Error executing command: {e}[/red]")


class CompletionModal(ModalScreen):
    def __init__(self, completions, editor_id, row, col):
        super().__init__()
        self.completions = completions
        self.editor_id = editor_id
        self.row = row
        self.col = col

    def compose(self):
        with Vertical(id="completion-dialog"):
            yield Label("🧩 LSP Completions (Press Enter)")
            lst = OptionList(id="completion-list")
            for c in self.completions:
                lst.add_option(c.get("label", str(c)))
            yield lst

    @on(OptionList.OptionSelected, "#completion-list")
    def on_selected(self, event):
        text = str(event.option.prompt)
        self.dismiss((self.editor_id, text, self.row, self.col))


class HoverModal(ModalScreen):
    def __init__(self, content):
        super().__init__()
        self.hover_content = content

    def compose(self):
        with Vertical(id="hover-dialog"):
            yield Label("Hover Documentation", classes="dialog-title")
            yield RichLog(id="hover-log", wrap=True, highlight=True, markup=True)
            yield Button("Close", id="btn-hover-close")

    def on_mount(self):
        log = self.query_one("#hover-log", RichLog)
        log.write(self.hover_content)

    @on(Button.Pressed, "#btn-hover-close")
    def close(self):
        self.dismiss()


class EssaIDEApp(App):
    """A Textual App to manage the EssaIDE."""

    current_file_path: Path | None = None
    open_tabs: dict = {}  # Map Path to tab_id for left pane
    split_open_tabs: dict = {}  # Map Path to tab_id for right pane
    active_split_id: str = "editor-tabs"

    settings: dict = {
        "auto_format": True,
        "linter": True,
        "line_numbers": True,
        "cache_enabled": True,
        "editor_theme": "monokai",
    }

    def __init__(self, workspace_path: str = ".", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_path = str(Path(workspace_path).absolute())
        self.repl_locals = {}
        self.repl_interp = code.InteractiveInterpreter(self.repl_locals)
        self.global_ast_index = {}
        self.open_tabs = {}
        self.split_open_tabs = {}
        self.workspace_trusted = False
        self._plugin_manifest: list[dict] = []  # security badge records

        self.live_server_process = None

        from lsp_client import LSPClient

        self.lsp_client = None
        self.pdb_wrapper = None

    CSS = """
    Screen {
        layout: vertical;
        background: #1a1b26;
    }
    
    #menubar {
        height: 1;
        dock: top;
        background: #16161e;
        layout: horizontal;
    }
    
    #menu-brand {
        background: #7aa2f7;
        color: #1a1b26;
        padding-left: 1;
        padding-right: 1;
        text-style: bold;
    }
    
    .menu-item {
        padding-left: 1;
        padding-right: 1;
        color: #a9b1d6;
        background: #16161e;
    }
    
    .menu-item:hover {
        background: #3d59a1;
        color: white;
    }
    
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    
    #activity-bar {
        width: 7;
        height: 1fr;
        background: #111116;
        border-right: solid #1a1b26;
        layout: vertical;
    }
    
    .activity-btn {
        width: 100%;
        height: 3;
        border: none;
        background: transparent;
        content-align: center middle;
        min-width: 4;
    }
    
    .activity-btn:hover {
        background: #292e42;
    }
    
    #sidebar {
        width: 30;
        border-right: solid #7aa2f7;
        height: 1fr;
        background: #16161e;
    }

    #sidebar.hidden {
        display: none;
    }
    
    VerticalResizer {
        width: 1;
        height: 1fr;
        background: #1a1b26;
    }
    VerticalResizer:hover {
        background: #7aa2f7;
    }
    HorizontalResizer {
        height: 1;
        width: 1fr;
        background: #1a1b26;
    }
    HorizontalResizer:hover {
        background: #bb9af7;
    }
    
    #sidebar-switcher {
        height: 1fr;
        width: 1fr;
    }
    
    #sidebar-search, #sidebar-plugins {
        height: 1fr;
        layout: vertical;
    }
    

    #completion-dialog, #hover-dialog {
        width: 60%;
        height: 60%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
        align: center middle;
    }

    #sidebar-search-results, #sidebar-plugins-list, #git-status-list {
        height: 1fr;
        background: #16161e;
    }
    
    #sidebar-search-input {
        dock: top;
    }
    
    .sidebar-title {
        background: #24283b;
        color: #bb9af7;
        width: 1fr;
        text-style: bold;
        padding: 0 1;
    }
    
    DirectoryTree {
        height: 1fr;
        background: #16161e;
    }
    
    #outline-tree {
        height: 1fr;
        border-top: solid #7aa2f7;
        background: #16161e;
    }
    
    #editor-container {
        width: 1fr;
        height: 1fr;
        layout: vertical;
        background: #1a1b26;
    }
    
    #search-input, #new-file-input {
        display: none;
        dock: top;
    }
    
    #search-input.-active, #new-file-input.-active {
        display: block;
    }
    
    #split-view {
        height: 2fr;
        layout: horizontal;
    }
    
    #editor-tabs {
        width: 1fr;
        height: 100%;
        background: #1a1b26;
        border: solid #3d59a1;
    }
    
    #editor-tabs-split {
        width: 1fr;
        height: 100%;
        background: #1a1b26;
        border: solid #3d59a1;
        border-left: double #7aa2f7;
    }
    
    .hidden {
        display: none;
    }
    
    StatusBar {
        height: 1;
        background: #007acc;
        color: white;
    }
    
    .status-item {
        padding: 0 1;
        background: #007acc;
        border-right: solid #1f8ad1;
    }
    
    .status-item:hover {
        background: #1f8ad1;
    }
    
    #status-linter.error {
        background: #f7768e;
        color: white;
    }

    #welcome-screen {
        width: 1fr;
        height: 1fr;
        align: center middle;
        background: #1a1b26;
        layout: vertical;
    }
    #welcome-screen.hidden { display: none; }
    #welcome-logo {
        content-align: center middle;
        color: #7aa2f7;
        text-style: bold;
    }
    #welcome-sub {
        content-align: center middle;
        color: #565f89;
        margin-bottom: 2;
    }
    .welcome-shortcut {
        content-align: center middle;
        color: #9ece6a;
        padding: 0 2;
    }
    
    #bottom-panel {
        height: 30%;
        border-top: solid #bb9af7;
        background: #16161e;
    }
    
    #bottom-panel.hidden {
        display: none;
    }
    
    TerminalArea, #problems-log, #console-log, #api-log, #monitor-log {
        height: 1fr;
        background: #16161e;
    }
    
    #console-container, #api-container, #monitor-container, #pkg-container {
        height: 1fr;
        layout: vertical;
    }
    
    .tab-close-btn {
        width: 3;
        height: 1;
        min-width: 3;
        background: transparent;
        border: none;
        color: #f7768e;
        padding: 0;
    }
    
    .tab-close-btn:hover {
        background: #f7768e;
        color: white;
    }

    #tab-bar-left, #tab-bar-right {
        height: 1;
        background: #16161e;
        align: right middle;
    }

    #editor-left-wrap, #editor-right-wrap {
        height: 1fr;
    }

    #editor-right-wrap.hidden {
        display: none;
    }

    #pkg-controls {
        height: 3;
        dock: top;
    }
    #pkg-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+shift+p", "command_palette", "Command Palette"),
        ("q", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+f", "search", "EssaSearch"),
        ("ctrl+n", "new_file", "New File"),
        ("ctrl+d", "delete_file", "Delete File"),
        ("ctrl+r", "run_code", "Run Code"),
        ("ctrl+w", "close_tab", "Close Tab"),
        ("ctrl+t", "toggle_dark", "Toggle Theme"),
        ("ctrl+b", "toggle_split", "Toggle Split"),
        ("ctrl+e", "switch_split", "Switch Split Focus"),
        ("ctrl+u", "go_up_dir", "Up Directory"),
        ("ctrl+o", "open_folder", "Open Folder"),
        ("ctrl+k", "toggle_breakpoint", "Breakpoint"),
        ("ctrl+y", "run_debugger", "Debug"),
        ("ctrl+space", "autocomplete", "Autocomplete"),
        ("f12", "go_definition", "Go to Definition"),
        ("ctrl+h", "hover_docs", "Hover Docs"),
        ("f8", "format_code", "Format Code"),
        ("f10", "dbg_next", "Step Over"),
        ("f11", "dbg_step", "Step In"),
        ("f5", "dbg_cont", "Continue"),
        ("f9", "dbg_stop", "Stop Debugger"),
        ("ctrl+j", "toggle_panel", "Toggle Panel"),
        ("ctrl+shift+e", "toggle_sidebar", "Toggle Explorer"),
        ("f2", "open_settings", "Settings"),
        ("f3", "new_window", "New Window"),
        ("f12", "go_to_definition", "Go To Def"),
        ("ctrl+p", "profile_run", "Profile Run"),
        ("ctrl+h", "global_replace", "Mass Refactor"),
        ("ctrl+m", "preview_markdown", "Preview MD"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Horizontal(id="menubar"):
            yield Label("🚀 EssaIDE", id="menu-brand")
            yield MenuLabel("Open Folder (Ctrl+O)", id="menu-open", classes="menu-item")
            yield MenuLabel("New File (Ctrl+N)", id="menu-file", classes="menu-item")
            yield MenuLabel("Search (Ctrl+F)", id="menu-edit", classes="menu-item")
            yield MenuLabel("Split View (Ctrl+B)", id="menu-view", classes="menu-item")
            yield MenuLabel("Run (Ctrl+R)", id="menu-run", classes="menu-item")
            yield MenuLabel("Debug (Ctrl+Y)", id="menu-debug", classes="menu-item")
            yield MenuLabel("Close File (Ctrl+W)", id="menu-close", classes="menu-item")
            yield MenuLabel("Settings (F2)", id="menu-settings", classes="menu-item")

        with Container(id="main-container"):
            with Vertical(id="activity-bar"):
                b1 = Button("📁\nFiles", id="activity-files", classes="activity-btn")
                b1.tooltip = "Explorer (Ctrl+E)"
                yield b1
                b2 = Button("🔍\nFind", id="activity-search", classes="activity-btn")
                b2.tooltip = "Global Search (Ctrl+F)"
                yield b2
                b3 = Button("🧩\nExts", id="activity-plugins", classes="activity-btn")
                b3.tooltip = "Extensions"
                yield b3
                b_git = Button("🌿\nGit", id="activity-git", classes="activity-btn")
                b_git.tooltip = "Source Control"
                yield b_git
                b4 = Button("⚙️\nSet", id="activity-settings", classes="activity-btn")
                b4.tooltip = "Settings (F2)"
                yield b4

            with Vertical(id="sidebar"):
                with ContentSwitcher(initial="sidebar-explorer", id="sidebar-switcher"):
                    with Vertical(id="sidebar-explorer"):
                        yield Label(
                            f"Explorer: {Path(self.workspace_path).name or '/'}",
                            id="workspace-path",
                            classes="sidebar-title",
                        )
                        yield DirectoryTree(self.workspace_path)
                        yield Label("Outline", classes="sidebar-title")
                        yield Tree("Symbols", id="outline-tree")
                    with Vertical(id="sidebar-search"):
                        yield Label("Global Search", classes="sidebar-title")
                        yield Input(
                            placeholder="Search workspace...", id="sidebar-search-input"
                        )
                        yield Button(
                            "Find All", id="btn-sidebar-search", variant="primary"
                        )
                        yield RichLog(id="sidebar-search-results", highlight=True)
                    with Vertical(id="sidebar-plugins"):
                        yield Label("Extensions", classes="sidebar-title")
                        yield OptionList(id="sidebar-plugins-list")
                    with Vertical(id="sidebar-git"):
                        yield Label("Source Control", classes="sidebar-title")
                        yield Button(
                            "↻ Refresh", id="btn-git-refresh", variant="primary"
                        )
                        yield OptionList(id="git-status-list")
                        yield Input(
                            id="git-commit-msg", placeholder="Commit message..."
                        )
                        yield Button(
                            "✔ Commit All", id="btn-git-commit", variant="success"
                        )

            yield VerticalResizer("sidebar", offset=7)

            with Vertical(id="editor-container"):
                yield Input(
                    placeholder="Search EssaSearch... (Press Enter to submit, Ctrl+F to close)",
                    id="search-input",
                )
                yield Input(
                    placeholder="Enter new file name... (Press Enter to create, Ctrl+N to close)",
                    id="new-file-input",
                )
                with Horizontal(id="split-view"):
                    with Vertical(id="editor-left-wrap"):
                        with Horizontal(id="tab-bar-left"):
                            yield Button(
                                "✕", id="btn-close-left", classes="tab-close-btn"
                            )
                        with Vertical(id="welcome-screen"):
                            yield Static("\n\n  🚀  EssaIDE  ", id="welcome-logo")
                            yield Static(
                                "  The Professional Terminal IDE\n", id="welcome-sub"
                            )
                            yield Static(
                                "  Ctrl+O        Open Folder",
                                classes="welcome-shortcut",
                            )
                            yield Static(
                                "  Ctrl+N        New File", classes="welcome-shortcut"
                            )
                            yield Static(
                                "  Ctrl+S        Save", classes="welcome-shortcut"
                            )
                            yield Static(
                                "  Ctrl+R        Run Code", classes="welcome-shortcut"
                            )
                            yield Static(
                                "  Ctrl+B        Toggle Split View",
                                classes="welcome-shortcut",
                            )
                            yield Static(
                                "  Ctrl+Shift+P  Command Palette",
                                classes="welcome-shortcut",
                            )
                        yield TabbedContent(id="editor-tabs")
                    yield VerticalResizer(
                        "editor-left-wrap",
                        offset=38,
                        id="split-resizer",
                        classes="hidden",
                    )
                    with Vertical(id="editor-right-wrap", classes="hidden"):
                        with Horizontal(id="tab-bar-right"):
                            yield Button(
                                "✕", id="btn-close-right", classes="tab-close-btn"
                            )
                        yield TabbedContent(id="editor-tabs-split")
                yield HorizontalResizer("bottom-panel", offset=2)
                with TabbedContent(id="bottom-panel"):
                    with TabPane("Output", id="tab-output"):
                        yield TerminalArea(id="terminal")
                    with TabPane("Debugger", id="tab-debugger"):
                        with Vertical():
                            with Horizontal(id="dbg-controls", classes="toolbar"):
                                yield Button("Step Over (F10)", id="btn-dbg-next", variant="primary")
                                yield Button("Step In (F11)", id="btn-dbg-step", variant="primary")
                                yield Button("Continue (F5)", id="btn-dbg-cont", variant="success")
                                yield Button("Stop (F9)", id="btn-dbg-stop", variant="error")
                            yield RichLog(id="dbg-log", highlight=True)
                    with TabPane("Problems", id="tab-problems"):
                        yield RichLog(id="problems-log", highlight=True, markup=True)
                    with TabPane("Console", id="tab-console"):
                        with Vertical(id="console-container"):
                            yield RichLog(id="console-log", highlight=True, markup=True)
                            yield Input(
                                placeholder=">>> Type Python code...",
                                id="console-input",
                            )
                    with TabPane("API Client", id="tab-api"):
                        with Vertical(id="api-container"):
                            yield Input(
                                placeholder="Enter API URL (e.g., https://api.github.com) and press Enter...",
                                id="api-input",
                            )
                            yield RichLog(id="api-log", highlight=True, markup=True)
                    with TabPane("Docker", id="tab-docker"):
                        with Vertical():
                            yield Button(
                                "Refresh Containers",
                                id="btn-docker-refresh",
                                variant="primary",
                            )
                            yield DataTable(id="docker-table")
                    with TabPane("Monitor", id="tab-monitor"):
                        with Vertical(id="monitor-container"):
                            yield Button(
                                "Refresh System Stats",
                                id="btn-monitor-refresh",
                                variant="success",
                            )
                            yield RichLog(id="monitor-log", highlight=True, markup=True)
                    with TabPane("Profiler", id="tab-profiler"):
                        with Vertical():
                            yield DataTable(id="profiler-table")
                    with TabPane("Packages", id="tab-packages"):
                        with Vertical(id="pkg-container"):
                            with Horizontal(id="pkg-controls"):
                                yield Input(
                                    placeholder="Enter package name (e.g. requests)...",
                                    id="pkg-input",
                                )
                                yield Button(
                                    "Install", id="btn-pkg-install", variant="success"
                                )
                                yield Button(
                                    "List Installed",
                                    id="btn-pkg-list",
                                    variant="primary",
                                )
                            yield DataTable(id="pkg-table")
                yield StatusBar(id="status-bar")
        yield Footer()

    # ── Workspace Trust ───────────────────────────────────────────────
    _TRUST_FILE = Path.home() / ".essaide" / "trusted_workspaces.json"

    def _load_trusted_workspaces(self) -> list:
        try:
            if self._TRUST_FILE.exists():
                import json

                return json.loads(self._TRUST_FILE.read_text())
        except Exception:
            pass
        return []

    def _save_trust(self, trusted: bool) -> None:
        import json

        self._TRUST_FILE.parent.mkdir(parents=True, exist_ok=True)
        trusted_list = self._load_trusted_workspaces()
        if trusted and self.workspace_path not in trusted_list:
            trusted_list.append(self.workspace_path)
        elif not trusted and self.workspace_path in trusted_list:
            trusted_list.remove(self.workspace_path)
        self._TRUST_FILE.write_text(json.dumps(trusted_list, indent=2))

    def on_mount(self) -> None:
        """Called when app starts."""
        self.push_screen(SplashScreen())
        already_trusted = self.workspace_path in self._load_trusted_workspaces()
        if already_trusted:
            self.workspace_trusted = True
            self.set_timer(1.5, self.finish_initialization)
        else:
            self.set_timer(1.5, self._show_trust_dialog)

    def _show_trust_dialog(self) -> None:
        self.pop_screen()  # dismiss splash

        def _after_trust(trusted: bool | None) -> None:
            self.workspace_trusted = bool(trusted)
            self._save_trust(self.workspace_trusted)
            self.finish_initialization(pop_splash=False)

        self.push_screen(WorkspaceTrustModal(self.workspace_path), _after_trust)

    def finish_initialization(self, pop_splash: bool = True) -> None:
        """Complete initialization after splash screen."""
        if pop_splash:
            self.pop_screen()

        terminal = self.query_one(TerminalArea)
        terminal.write("Initializing EssaIDE...")

        self.cache_client = None
        if EssaCacheClient:
            try:
                self.cache_client = EssaCacheClient()
                self.cache_client.ping()
                terminal.write("Connecting to EssaCache... [OK]")
            except Exception as e:
                terminal.write(f"Connecting to EssaCache... [FAILED: {e}]")
                self.cache_client = None
        else:
            terminal.write("Connecting to EssaCache... [FAILED: Client not found]")

        terminal.write("Ready.")

        import sys

        console = self.query_one("#console-log", RichLog)
        console.write(f"Python {sys.version.split()[0]} Interactive Console. Ready!")

        # Build Global AST Index
        import ast
        import threading

        def _build_ast_index():
            workspace = Path(self.workspace_path)
            count = 0
            for path in workspace.rglob("*.py"):
                if "__pycache__" in str(path) or path.name.startswith("."):
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                        ):
                            self.global_ast_index[node.name] = {
                                "file": path,
                                "line": node.lineno - 1,
                            }
                            count += 1
                except Exception:
                    continue
            self.call_from_thread(
                terminal.write,
                f"🧠 AST Indexer: Scanned {count} definitions across workspace.",
            )

        threading.Thread(target=_build_ast_index).start()

        # Load Extensions/Plugins (sandboxed)
        self._plugin_manifest = []
        plugins_dir = Path(self.workspace_path) / ".essa_plugins"
        if plugins_dir.exists() and plugins_dir.is_dir():
            if not self.workspace_trusted:
                terminal.write(
                    "🔒 [yellow]Plugins are DISABLED — workspace is not trusted.[/yellow]"
                )
                terminal.write(
                    "    Click the 🧩 Extensions icon and trust the workspace to enable."
                )
            else:
                import importlib.util, subprocess, tempfile, json as _json

                terminal.write("🧩 Scanning for Essa Extensions (sandboxed)...")
                loaded_count = 0
                for plugin_file in plugins_dir.glob("*.py"):
                    if plugin_file.name.startswith("_"):
                        continue
                    # --- Static analysis: detect risky imports ---
                    risks = []
                    try:
                        source = plugin_file.read_text(encoding="utf-8")
                        risky_modules = [
                            "os",
                            "subprocess",
                            "socket",
                            "shutil",
                            "sys",
                            "ctypes",
                            "eval",
                            "exec",
                        ]
                        for rm in risky_modules:
                            if (
                                f"import {rm}" in source
                                or f"from {rm}" in source
                                or f" {rm}." in source
                            ):
                                risks.append(rm)
                    except Exception:
                        pass

                    # --- Run plugin in sandboxed subprocess with timeout ---
                    badge = "✅ Safe" if not risks else f"⚠️ Uses: {', '.join(risks)}"
                    manifest_entry = {
                        "name": plugin_file.stem,
                        "file": plugin_file.name,
                        "risks": risks,
                        "badge": badge,
                        "loaded": False,
                    }

                    # Build a tiny runner that proxies only safe app methods via JSON-RPC over stdout
                    runner_code = f"""
import sys, json
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("{plugin_file.stem}", r"{plugin_file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "setup"):
        class _SafeApp:
            workspace_path = r"{self.workspace_path}"
            def notify(self, msg, **kw): print(json.dumps({{"action":"notify","msg":msg}}))
            def write_terminal(self, msg): print(json.dumps({{"action":"terminal","msg":msg}}))
        mod.setup(_SafeApp())
        print(json.dumps({{"status":"ok"}}))
    else:
        print(json.dumps({{"status":"no_setup"}}))
except Exception as e:
    print(json.dumps({{"status":"error","msg":str(e)}}))
"""
                    try:
                        result = subprocess.run(
                            [sys.executable, "-c", runner_code],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        output_lines = [
                            l
                            for l in result.stdout.strip().splitlines()
                            if l.startswith("{")
                        ]
                        for line in output_lines:
                            try:
                                msg = _json.loads(line)
                                if msg.get("action") == "terminal":
                                    terminal.write(
                                        f"  [dim][plugin][/dim] {msg.get('msg', '')}"
                                    )
                                elif msg.get("action") == "notify":
                                    self.notify(
                                        msg.get("msg", ""), title=plugin_file.stem
                                    )
                                elif msg.get("status") == "ok":
                                    terminal.write(
                                        f"  ✅ [bold cyan]{plugin_file.stem}[/bold cyan] — {badge}"
                                    )
                                    manifest_entry["loaded"] = True
                                    loaded_count += 1
                                elif msg.get("status") == "no_setup":
                                    terminal.write(
                                        f"  ⚠️ {plugin_file.name} missing setup()"
                                    )
                                elif msg.get("status") == "error":
                                    terminal.write(
                                        f"  ❌ {plugin_file.name}: {msg.get('msg', '')}"
                                    )
                            except Exception:
                                pass
                    except subprocess.TimeoutExpired:
                        terminal.write(
                            f"  ⏱️ {plugin_file.name} timed out (5s sandbox limit)"
                        )
                    except Exception as e:
                        terminal.write(f"  ❌ {plugin_file.name}: {e}")
                    self._plugin_manifest.append(manifest_entry)

                if loaded_count > 0:
                    terminal.write(
                        f"✨ Sandboxed {loaded_count} extension(s) successfully."
                    )

        # Restore Workspace Session
        try:
            import json

            session_file = Path(self.workspace_path) / ".essa_session.json"
            if session_file.exists():
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for path_str in data.get("left_tabs", []):
                    p = Path(path_str)
                    if p.exists():
                        self.load_file(p, "editor-tabs")

                for path_str in data.get("right_tabs", []):
                    p = Path(path_str)
                    if p.exists():
                        self.load_file(p, "editor-tabs-split")

                self.active_split_id = data.get("active_split", "editor-tabs")
                terminal.write("🔄 Workspace session restored.")
        except Exception:
            pass

    def save_session(self) -> None:
        """Serialize current workspace state to disk."""
        try:
            import json

            session_file = Path(self.workspace_path) / ".essa_session.json"
            session_data = {
                "left_tabs": [str(path) for path in self.open_tabs.keys()],
                "right_tabs": [str(path) for path in self.split_open_tabs.keys()],
                "active_split": self.active_split_id,
            }
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f)
        except Exception:
            pass

    @on(MenuLabel.Clicked)
    async def handle_menu_click(self, event: MenuLabel.Clicked) -> None:
        """Handle menu bar clicks."""
        menu_id = event.label_id
        if menu_id == "menu-open":
            self.action_open_folder()
        elif menu_id == "menu-file":
            self.action_new_file()
        elif menu_id == "menu-edit":
            self.action_search()
        elif menu_id == "menu-view":
            self.action_toggle_split()
        elif menu_id == "menu-run":
            await self.action_run_code()
        elif menu_id == "menu-debug":
            self.action_run_debugger()
        elif menu_id == "menu-close":
            self.action_close_tab()
        elif menu_id == "menu-settings":
            self.action_open_settings()

    def action_open_settings(self) -> None:
        self.push_screen(SettingsDashboard())

    def _activate_tab(self, tabs, tab_id):
        def _set():
            try:
                tabs.active = tab_id
            except Exception:
                pass

        self.call_after_refresh(_set)

    def load_file(self, file_path: Path, split_id: str) -> None:
        terminal = self.query_one(TerminalArea)
        tabs = self.query_one(f"#{split_id}", TabbedContent)

        open_tabs_map = (
            self.open_tabs if split_id == "editor-tabs" else self.split_open_tabs
        )

        if file_path in open_tabs_map:
            self._activate_tab(tabs, open_tabs_map[file_path])
            self.current_file_path = file_path
            return

        try:
            self.current_file_path = file_path

            cache_key = f"file:{file_path.absolute()}"
            cached_content = None

            if self.cache_client and self.settings.get("cache_enabled", True):
                try:
                    cached_content = self.cache_client.get(cache_key)
                except Exception:
                    pass

            if cached_content:
                terminal.write(
                    f"⚡ CACHE HIT: Loaded {file_path.name} instantly from memory!"
                )
                content = cached_content.decode("utf-8")
            else:
                terminal.write(f"🐢 CACHE MISS: Reading {file_path.name} from disk...")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if self.cache_client:
                    try:
                        self.cache_client.set(cache_key, content)
                        terminal.write(f"📦 Cached {file_path.name} for future loads.")
                    except Exception as e:
                        terminal.write(f"Failed to cache {file_path.name}: {e}")

            import uuid
            tab_id = f"tab_{uuid.uuid4().hex}"
            open_tabs_map[file_path] = tab_id
            # Hide welcome screen once any file is opened
            try:
                self.query_one("#welcome-screen").add_class("hidden")
            except Exception:
                pass

            ext = file_path.suffix.lower()

            if ext in [".db", ".sqlite", ".sqlite3"]:
                pane_widget = SQLQueryPane(str(file_path), widget_id=f"editor-{tab_id}")
                pane = TabPane(f"🗄 {file_path.name}  ✕", pane_widget, id=tab_id)
                tabs.add_pane(pane)
                self._activate_tab(tabs, tab_id)
                terminal.write(f"🗄️ Opened database: {file_path.name}")
                self.save_session()
                return

            if ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"]:
                import webbrowser
                import threading
                import os

                def open_image():
                    try:
                        if os.system(f"xdg-open '{file_path}' &> /dev/null") != 0:
                            webbrowser.open(f"file://{file_path.absolute()}")
                    except Exception:
                        webbrowser.open(f"file://{file_path.absolute()}")

                threading.Thread(target=open_image).start()

                log = RichLog(id=f"editor-{tab_id}", highlight=True, markup=True)
                pane = TabPane(f"{file_path.name}  ✕", log, id=tab_id)
                tabs.add_pane(pane)
                self._activate_tab(tabs, tab_id)

                log.write(f"\n[bold cyan]🖼️  Image File:[/bold cyan] {file_path.name}")
                log.write(
                    "\n[green]Image successfully launched in your system's external image viewer.[/green]"
                )
                log.write(
                    "\n[dim](Terminal rendering of high-res images is currently not supported natively in EssaIDE.)[/dim]"
                )

                self.save_session()
                return

            suffix_to_lang = {
                ".py": "python",
                ".md": "markdown",
                ".json": "json",
                ".html": "html",
                ".css": "css",
                ".sql": "sql",
                ".js": "javascript",
                ".ts": "javascript",
            }
            lang = suffix_to_lang.get(file_path.suffix.lower(), None)

            editor = TextArea(
                content,
                id=f"editor-{tab_id}",
                show_line_numbers=self.settings.get("line_numbers", True),
                language=lang,
                theme=self.settings.get("editor_theme", "monokai"),
            )

            pane = TabPane(f"{file_path.name}  ✕", editor, id=tab_id)
            tabs.add_pane(pane)
            self._activate_tab(tabs, tab_id)

            terminal.write(f"Opened: {file_path.name} in {split_id}")
            self.update_outline()
            self.save_session()
        except Exception as e:
            terminal.write(f"Error opening {file_path.name}: {e}")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Called when a file is selected in the directory tree."""
        event.stop()
        self.load_file(event.path, self.active_split_id)

    @on(Button.Pressed, "#btn-close-left")
    def close_left_tab(self) -> None:
        """Close the active tab in the left/main editor pane."""
        self.active_split_id = "editor-tabs"
        self.action_close_tab()

    @on(Button.Pressed, "#btn-close-right")
    def close_right_tab(self) -> None:
        """Close the active tab in the right split editor pane."""
        self.active_split_id = "editor-tabs-split"
        self.action_close_tab()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        """Update current_file_path when switching tabs."""
        if not event.pane:
            return
        pane_id = event.pane.id

        # Determine which split this came from
        if pane_id.startswith("editor-tabs-split"):
            self.active_split_id = "editor-tabs-split"
            open_tabs_map = self.split_open_tabs
        else:
            self.active_split_id = "editor-tabs"
            open_tabs_map = self.open_tabs

        for path, t_id in open_tabs_map.items():
            if t_id == pane_id:
                self.current_file_path = path
                self.update_outline()

                try:
                    ext = self.current_file_path.suffix.lower()
                    lang_map = {
                        ".py": "Python 🐍",
                        ".md": "Markdown 📄",
                        ".json": "JSON ⚙️",
                        ".txt": "Text",
                        ".js": "JS 🟨",
                        ".html": "HTML 🌐",
                        ".css": "CSS 🎨",
                    }
                    lang = lang_map.get(ext, "Plain Text")
                    self.query_one("#status-file", Label).update(f" {lang} ")
                    self.query_one("#status-cursor", Label).update("Ln 1, Col 1")
                except Exception:
                    pass
                break

    @on(events.MouseDown)
    def on_tab_close_click(self, event: events.MouseDown) -> None:
        """Handle clicking the ✕ on a tab to close it."""
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
        except Exception:
            return

        if not widget or widget.__class__.__name__ not in ("Tab", "ContentTab"):
            return

        # Mathematically perfect hit-box calculation
        tab_x = event.screen_x - widget.region.x
        if tab_x >= widget.size.width - 4:
            event.prevent_default()
            event.stop()
            pane_id = widget.id.replace("--content-tab-", "")

            # Find and remove from correct map
            if pane_id in self.split_open_tabs.values():
                path = next(
                    (k for k, v in self.split_open_tabs.items() if v == pane_id), None
                )
                if path:
                    self.split_open_tabs.pop(path)
                    if self.current_file_path == path:
                        self.current_file_path = None
                    self.query_one("#editor-tabs-split", TabbedContent).remove_pane(
                        pane_id
                    )
            elif pane_id in self.open_tabs.values():
                path = next(
                    (k for k, v in self.open_tabs.items() if v == pane_id), None
                )
                if path:
                    self.open_tabs.pop(path)
                    if self.current_file_path == path:
                        self.current_file_path = None
                    self.query_one("#editor-tabs", TabbedContent).remove_pane(pane_id)
            else:
                try:
                    self.query_one("#editor-tabs-split", TabbedContent).remove_pane(
                        pane_id
                    )
                except:
                    pass
                try:
                    self.query_one("#editor-tabs", TabbedContent).remove_pane(pane_id)
                except:
                    pass

            self.query_one(TerminalArea).write("Tab closed.")
            if not self.open_tabs and not self.split_open_tabs:
                try:
                    self.query_one("#welcome-screen").remove_class("hidden")
                except Exception:
                    pass

    @on(TextArea.SelectionChanged)
    def on_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        """Update cursor position in the Status Bar."""
        try:
            if not self.query("StatusBar"):
                return
            cursor = event.text_area.cursor_location
            self.query_one("#status-cursor", Label).update(
                f"Ln {cursor[0] + 1}, Col {cursor[1] + 1}"
            )
        except Exception:
            pass

    def action_save(self) -> None:
        """Action for Ctrl+S."""
        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        if self.current_file_path and self.current_file_path in open_tabs_map:
            tab_id = open_tabs_map[self.current_file_path]
            editor = self.query_one(f"#editor-{tab_id}", TextArea)
            try:
                with open(self.current_file_path, "w", encoding="utf-8") as f:
                    f.write(editor.text)

                # Auto-format with Black
                if self.current_file_path.suffix == ".py" and self.settings.get(
                    "auto_format", True
                ):
                    import subprocess

                    try:
                        subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "black",
                                "-q",
                                str(self.current_file_path),
                            ],
                            check=True,
                        )
                        with open(self.current_file_path, "r", encoding="utf-8") as f:
                            formatted_text = f.read()
                        if editor.text != formatted_text:
                            editor.load_text(formatted_text)
                            self.query_one(TerminalArea).write(
                                "✨ Auto-formatted with Black"
                            )
                    except Exception:
                        pass

                self.update_outline()

                # Remove asterisk from tab
                tabs = self.query_one(f"#{self.active_split_id}", TabbedContent)
                try:
                    tab = tabs.get_tab(tab_id)
                    if str(tab.label).endswith("*"):
                        tab.label = str(tab.label)[:-2]
                except Exception:
                    pass

                # Update cache on save
                if self.cache_client:
                    try:
                        cache_key = f"file:{self.current_file_path.absolute()}"
                        self.cache_client.set(cache_key, editor.text)
                        self.query_one(TerminalArea).write(
                            f"🔄 Cache updated for {self.current_file_path.name}"
                        )
                    except Exception:
                        pass

                self.notify(f"Saved {self.current_file_path.name}", title="Success")
                self.query_one(TerminalArea).write(
                    f"Saved: {self.current_file_path.name}"
                )
            except Exception as e:
                self.notify(f"Error saving file: {e}", title="Error", severity="error")
                self.query_one(TerminalArea).write(
                    f"Error saving {self.current_file_path.name}: {e}"
                )
        else:
            self.notify(
                "No file selected to save.", title="Warning", severity="warning"
            )

    def action_toggle_split(self) -> None:
        """Toggle split screen editing."""
        split = self.query_one("#editor-right-wrap")
        resizer = self.query_one("#split-resizer")
        if split.has_class("hidden"):
            split.remove_class("hidden")
            resizer.remove_class("hidden")
            self.active_split_id = "editor-tabs-split"
            self.query_one(TerminalArea).write(
                "Split view opened. Focus moved to right pane."
            )
            if self.current_file_path:
                self.load_file(self.current_file_path, "editor-tabs-split")
        else:
            split.add_class("hidden")
            resizer.add_class("hidden")
            self.active_split_id = "editor-tabs"
            self.query_one(TerminalArea).write("Split view closed.")

    def action_switch_split(self) -> None:
        """Switch focus between splits."""
        if self.query_one("#editor-right-wrap").has_class("hidden"):
            return
        if self.active_split_id == "editor-tabs":
            self.active_split_id = "editor-tabs-split"
            self.query_one(TerminalArea).write("Focus moved to right pane.")
        else:
            self.active_split_id = "editor-tabs"
            self.query_one(TerminalArea).write("Focus moved to left pane.")

    def action_toggle_panel(self) -> None:
        """Toggle the bottom terminal panel."""
        panel = self.query_one("#bottom-panel")
        if panel.has_class("hidden"):
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")

    def action_toggle_sidebar(self) -> None:
        """Toggle the left sidebar."""
        sidebar = self.query_one("#sidebar")
        if sidebar.has_class("hidden"):
            sidebar.remove_class("hidden")
        else:
            sidebar.add_class("hidden")

    def action_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        if search_input.has_class("-active"):
            search_input.remove_class("-active")
            self.query_one(f"#{self.active_split_id}").focus()
        else:
            search_input.add_class("-active")
            search_input.focus()

    def action_new_file(self) -> None:
        new_file_input = self.query_one("#new-file-input", Input)
        if new_file_input.has_class("-active"):
            new_file_input.remove_class("-active")
            self.query_one(f"#{self.active_split_id}").focus()
        else:
            new_file_input.add_class("-active")
            new_file_input.focus()

    def action_open_folder(self) -> None:
        def check_folder(path: Path | None) -> None:
            if path is not None and path.is_dir():
                self.workspace_path = str(path)
                tree = self.query_one("#sidebar DirectoryTree", DirectoryTree)
                tree.path = str(path)

                lbl = self.query_one("#workspace-path", Label)
                lbl.update(f"Explorer: {path.name or '/'}")

                self.query_one(TerminalArea).write(f"📂 Workspace changed to: {path}")

                # Start LSP
                from lsp_client import LSPClient

                self.lsp_client = LSPClient(self.workspace_path)
                self.lsp_client.on_diagnostics = self.handle_diagnostics
                import asyncio

                asyncio.create_task(self.lsp_client.start())
                self.query_one(TerminalArea).write(
                    "🚀 LSP Background Client Initialized."
                )

                self.query_one(f"#{self.active_split_id}").focus()

        self.push_screen(FolderPicker(), check_folder)

    def load_settings(self):
        try:
            import json
            from pathlib import Path

            settings_path = Path(self.workspace_path) / ".essa_settings.json"
            if settings_path.exists():
                with open(settings_path, "r") as f:
                    data = json.load(f)
                if "dark" in data:
                    self.dark = data["dark"]
        except Exception:
            pass

    def save_settings(self):
        try:
            import json
            from pathlib import Path

            settings_path = Path(self.workspace_path) / ".essa_settings.json"
            data = {"dark": self.dark}
            with open(settings_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark
        self.save_settings()

    def action_go_up_dir(self) -> None:
        """Navigate the DirectoryTree up one level."""
        tree = self.query_one(DirectoryTree)
        current = Path(tree.path)
        if current.parent and current.parent != current:
            new_path = current.parent
            tree.path = str(new_path)
            self.workspace_path = str(new_path)

            lbl = self.query_one("#workspace-path", Label)
            lbl.update(f"Explorer: {new_path.name or '/'}")

            self.query_one(TerminalArea).write(f"📂 Workspace moved up to: {new_path}")

    def action_close_tab(self) -> None:
        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        if not self.current_file_path or self.current_file_path not in open_tabs_map:
            return

        tab_id = open_tabs_map.pop(self.current_file_path)
        tabs = self.query_one(f"#{self.active_split_id}", TabbedContent)
        tabs.remove_pane(tab_id)

        self.current_file_path = None
        self.query_one(TerminalArea).write("Tab closed.")
        # Show welcome screen if no tabs remain
        if not self.open_tabs and not self.split_open_tabs:
            try:
                self.query_one("#welcome-screen").remove_class("hidden")
            except Exception:
                pass

    def _count_unsaved(self) -> int:
        """Count tabs with unsaved changes (label contains '*')."""
        count = 0
        for tc_id in ("#editor-tabs", "#editor-tabs-split"):
            try:
                tc = self.query_one(tc_id, TabbedContent)
                for tab in tc.query("Tab"):
                    if "*" in str(tab.label):
                        count += 1
            except Exception:
                pass
        return count

    def action_quit(self) -> None:
        """Quit with unsaved-changes guard."""
        unsaved = self._count_unsaved()
        if unsaved == 0:
            super().action_quit()
            return

        def _after(choice):
            if choice == "save":
                self.action_save()
                super(EssaIDEApp, self).action_quit()
            elif choice == "force":
                super(EssaIDEApp, self).action_quit()

        self.push_screen(UnsavedChangesModal(unsaved), _after)

    def handle_diagnostics(self, uri, diagnostics):
        self.call_from_thread(self._render_diagnostics, uri, diagnostics)

    def _render_diagnostics(self, uri, diagnostics):
        try:
            log = self.query_one("#problems-log", RichLog)
            log.clear()
            if not diagnostics:
                log.write("[bold green]✅ No problems detected.[/bold green]")
                return

            file_name = uri.split("/")[-1]
            log.write(
                f"[bold underline]Found {len(diagnostics)} problems in {file_name}:[/bold underline]\n"
            )

            for d in diagnostics:
                sev = d.get("severity", 1)
                msg = d.get("message", "Unknown error")
                r = d.get("range", {}).get("start", {})
                line = r.get("line", 0) + 1
                col = r.get("character", 0) + 1

                if sev == 1:
                    prefix = "[bold red]✖ Error[/bold red]"
                elif sev == 2:
                    prefix = "[bold yellow]⚠ Warning[/bold yellow]"
                else:
                    prefix = "[bold blue]ℹ Info[/bold blue]"

                log.write(f"{prefix} Line {line}:{col} - {msg}")
        except:
            pass

    def get_active_editor(self):
        try:
            tabs = self.query_one(f"#{self.active_split_id}", TabbedContent)
            tab_id = tabs.active
            if not tab_id:
                return None
            return self.query_one(f"#editor-{tab_id}", TextArea)
        except:
            return None

    def action_autocomplete(self) -> None:
        editor = self.get_active_editor()
        if not editor or not self.lsp_client or not self.lsp_client.is_ready:
            return
        row, col = editor.cursor_location
        uri = f"file://{self.current_file_path}"

        async def fetch():
            res = await self.lsp_client.get_completions(uri, row, col)
            if res:
                items = res if isinstance(res, list) else res.get("items", [])
                if items:
                    self.call_from_thread(
                        self.push_screen,
                        CompletionModal(items, editor.id, row, col),
                        self.insert_completion,
                    )

        import asyncio

        asyncio.create_task(fetch())

    def insert_completion(self, result) -> None:
        if not result:
            return
        editor_id, text, row, col = result
        try:
            editor = self.query_one(f"#{editor_id}", TextArea)
            # Find the start of the current word
            line_text = editor.document.get_line(row)
            start_col = col
            while start_col > 0 and (
                line_text[start_col - 1].isalnum() or line_text[start_col - 1] == "_"
            ):
                start_col -= 1
            editor.replace(text, (row, start_col), (row, col))
        except:
            pass

    def action_format_code(self) -> None:
        editor = self.get_active_editor()
        if not editor or not self.current_file_path:
            return

        # We only format Python files for now
        if not str(self.current_file_path).endswith(".py"):
            self.notify(
                "Auto-formatter is currently only supported for Python files.",
                title="Formatter",
                severity="warning",
            )
            return

        try:
            import black

            # Save cursor position
            old_cursor = editor.cursor_location

            # Format
            formatted_text = black.format_str(editor.text, mode=black.Mode())

            if formatted_text != editor.text:
                editor.text = formatted_text
                # Try to restore cursor safely
                max_lines = len(editor.document.lines)
                r = min(old_cursor[0], max_lines - 1)
                c = min(old_cursor[1], len(editor.document.get_line(r)))
                editor.cursor_location = (r, c)

                self.notify(
                    "Successfully formatted file with Black!", title="Formatter"
                )
            else:
                self.notify("File is already well-formatted.", title="Formatter")

        except ImportError:
            self.notify(
                "Black formatter not installed. Run 'pip install black'.",
                title="Formatter Error",
                severity="error",
            )
        except Exception as e:
            self.notify(
                f"Syntax error prevents formatting: {str(e).split('Cannot parse: ')[-1]}",
                title="Formatter Error",
                severity="error",
            )

    def action_hover_docs(self) -> None:
        editor = self.get_active_editor()
        if not editor or not self.lsp_client or not self.lsp_client.is_ready:
            return
        row, col = editor.cursor_location
        uri = f"file://{self.current_file_path}"

        async def fetch():
            res = await self.lsp_client.get_hover(uri, row, col)
            if res and "contents" in res:
                contents = res["contents"]
                val = (
                    contents.get("value", str(contents))
                    if isinstance(contents, dict)
                    else str(contents)
                )
                self.call_from_thread(self.push_screen, HoverModal(val))

        import asyncio

        asyncio.create_task(fetch())

    def action_go_definition(self) -> None:
        editor = self.get_active_editor()
        if not editor or not self.lsp_client or not self.lsp_client.is_ready:
            return
        row, col = editor.cursor_location
        uri = f"file://{self.current_file_path}"

        async def fetch():
            res = await self.lsp_client.get_definition(uri, row, col)
            if res and isinstance(res, list) and len(res) > 0:
                target = res[0]
                target_uri = target.get("uri", "").replace("file://", "")
                r = target.get("range", {}).get("start", {})
                t_row, t_col = r.get("line", 0), r.get("character", 0)

                def apply_goto():
                    if target_uri != str(self.current_file_path):
                        from pathlib import Path

                        self.load_file(Path(target_uri), self.active_split_id)
                    try:
                        new_editor = self.get_active_editor()
                        new_editor.cursor_location = (t_row, t_col)
                        new_editor.focus()
                    except:
                        pass

                self.call_from_thread(apply_goto)

        import asyncio

        asyncio.create_task(fetch())

    def action_command_palette(self) -> None:
        self.push_screen(CommandPaletteModal())

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        editor_id = event.text_area.id
        if not editor_id:
            return
        tab_id = editor_id.replace("editor-", "")
        split_id = (
            "editor-tabs-split"
            if tab_id.startswith("editor-tabs-split")
            else "editor-tabs"
        )

        try:
            tabs = self.query_one(f"#{split_id}", TabbedContent)
            tab = tabs.get_tab(tab_id)
            if not str(tab.label).endswith("*"):
                tab.label = f"{tab.label} *"

            if (
                self.lsp_client
                and self.lsp_client.is_ready
                and self.current_file_path
                and str(self.current_file_path).endswith(".py")
            ):
                # Simple debounce mechanism
                if not hasattr(self, "_lsp_debounce_task"):
                    self._lsp_debounce_task = None

                import asyncio

                if self._lsp_debounce_task:
                    self._lsp_debounce_task.cancel()

                async def debounced_change(uri, text):
                    await asyncio.sleep(0.4)  # 400ms debounce
                    self.lsp_client.did_change(uri, text)

                self._lsp_debounce_task = asyncio.create_task(
                    debounced_change(
                        f"file://{self.current_file_path}", event.text_area.text
                    )
                )

        except Exception:
            pass

        # Real-time Linter for Python
        if (
            self.current_file_path
            and self.current_file_path.suffix == ".py"
            and self.settings.get("linter", True)
        ):
            linter_label = self.query_one("#status-linter", Label)
            try:
                ast.parse(event.text_area.text)
                linter_label.update("✅ Linter: No syntax errors")
                linter_label.remove_class("error")
                self.update_outline()
            except SyntaxError as e:
                linter_label.update(f"❌ Syntax Error (Line {e.lineno}): {e.msg}")
                linter_label.add_class("error")
                problems = self.query_one("#problems-log", RichLog)
                problems.write(
                    f"[red]Syntax Error in {self.current_file_path.name} line {e.lineno}: {e.msg}[/red]"
                )
            except Exception:
                pass

    def action_new_window(self) -> None:
        """Spawn a completely new instance of EssaIDE in a new terminal window."""
        import os

        terminal = self.query_one(TerminalArea)
        try:
            cmd = f"gnome-terminal -- bash -c 'essa-ide \"{self.workspace_path}\"; exec bash' &"
            res = os.system(cmd)
            if res != 0:
                cmd2 = f'x-terminal-emulator -e \'bash -c "essa-ide \\"{self.workspace_path}\\"; exec bash"\' &'
                os.system(cmd2)
            terminal.write("🚀 Spawning new IDE window...")
        except Exception as e:
            terminal.write(f"❌ Could not spawn new window: {e}")

    def action_delete_file(self) -> None:
        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        if self.current_file_path and self.current_file_path.exists():
            try:
                self.current_file_path.unlink()
                self.notify(
                    f"Deleted {self.current_file_path.name}",
                    title="Deleted",
                    severity="warning",
                )
                self.query_one(TerminalArea).write(
                    f"🗑️ Deleted {self.current_file_path.name}"
                )

                if self.current_file_path in open_tabs_map:
                    tab_id = open_tabs_map.pop(self.current_file_path)
                    tabs = self.query_one(f"#{self.active_split_id}", TabbedContent)
                    tabs.remove_pane(tab_id)

                self.current_file_path = None
                self.query_one(DirectoryTree).reload()
            except Exception as e:
                self.notify(
                    f"Error deleting file: {e}", title="Error", severity="error"
                )
        else:
            self.notify(
                "No file selected to delete.", title="Warning", severity="warning"
            )

    def update_outline(self) -> None:
        """Update the symbol outline tree for Python files."""
        tree = self.query_one("#outline-tree", Tree)
        tree.root.remove_children()

        if not self.current_file_path or self.current_file_path.suffix != ".py":
            tree.root.set_label("No Symbols")
            return

        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        tab_id = open_tabs_map.get(self.current_file_path)
        if not tab_id:
            return

        editor = self.query_one(f"#editor-{tab_id}", TextArea)

        try:
            tree.root.set_label(self.current_file_path.name)
            tree.root.expand()

            parsed = ast.parse(editor.text)
            for node in parsed.body:
                if isinstance(node, ast.ClassDef):
                    class_node = tree.root.add(f"🔶 {node.name}", data=node.lineno)
                    class_node.expand()
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            class_node.add(f"🔸 {item.name}", data=item.lineno)
                elif isinstance(node, ast.FunctionDef):
                    tree.root.add(f"🔸 {node.name}", data=node.lineno)
        except SyntaxError:
            pass

    @on(Tree.NodeSelected, "#outline-tree")
    def on_outline_node_selected(self, event: Tree.NodeSelected) -> None:
        """Jump to the symbol's line number in the editor."""
        if event.node.data:
            line_no = event.node.data
            open_tabs_map = (
                self.open_tabs
                if self.active_split_id == "editor-tabs"
                else self.split_open_tabs
            )
            if self.current_file_path in open_tabs_map:
                tab_id = open_tabs_map[self.current_file_path]
                editor = self.query_one(f"#editor-{tab_id}", TextArea)
                editor.move_cursor((line_no - 1, 0))
                editor.focus()

    async def action_run_code(self) -> None:
        if not self.current_file_path:
            self.notify("No file selected to run.", title="Warning", severity="warning")
            return

        terminal = self.query_one(TerminalArea)
        self.action_save()

        ext = self.current_file_path.suffix.lower()
        filepath = str(self.current_file_path)
        parent = str(self.current_file_path.parent)
        name = self.current_file_path.stem

        if ext in [".html", ".htm"]:
            terminal.write(
                f"🌐 Starting Live Server for {self.current_file_path.name}..."
            )
            import subprocess
            import webbrowser

            try:
                subprocess.Popen(
                    [sys.executable, "-m", "http.server", "8080"], cwd=parent
                )
                webbrowser.open(f"http://localhost:8080/{self.current_file_path.name}")
                terminal.write(
                    "✅ Live Server started on port 8080. Check your browser!"
                )
            except Exception as e:
                terminal.write(f"❌ Failed to start Live Server: {e}")
            return

        elif ext == ".json":
            terminal.write(f"🔍 Validating JSON: {self.current_file_path.name}...")
            import json

            try:
                with open(self.current_file_path, "r", encoding="utf-8") as f:
                    json.load(f)
                terminal.write("✅ JSON is perfectly valid.")
            except Exception as e:
                terminal.write(f"❌ Invalid JSON: {e}")
            return

        interpreters = {
            ".py": [sys.executable, filepath],
            ".sh": ["bash", filepath],
            ".js": ["node", filepath],
            ".ts": ["ts-node", filepath],
            ".rb": ["ruby", filepath],
            ".go": ["go", "run", filepath],
            ".java": ["java", filepath],
            ".php": ["php", filepath],
            ".pl": ["perl", filepath],
            ".lua": ["lua", filepath],
            ".r": ["Rscript", filepath],
        }

        compilers = {
            ".c": f"gcc '{filepath}' -o '{parent}/{name}.out' && '{parent}/{name}.out'",
            ".cpp": f"g++ '{filepath}' -o '{parent}/{name}.out' && '{parent}/{name}.out'",
            ".rs": f"rustc '{filepath}' -o '{parent}/{name}.out' && '{parent}/{name}.out'",
        }

        try:
            if ext in interpreters:
                cmd = interpreters[ext]
                terminal.write(
                    f"🚀 Running {cmd[0].upper()}: {self.current_file_path.name}..."
                )
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=parent,
                )
            elif ext in compilers:
                cmd = compilers[ext]
                terminal.write(
                    f"⚙️ Compiling & Running: {self.current_file_path.name}..."
                )
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=parent,
                )
            else:
                self.notify(
                    f"Runner not supported for {ext} files.",
                    title="Unsupported",
                    severity="error",
                )
                return

            async def read_stdout(stream):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    terminal.write(line.decode("utf-8", errors="replace").rstrip())

            async def read_stderr(stream):
                problems = self.query_one("#problems-log", RichLog)
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    problems.write(
                        f"[red]{line.decode('utf-8', errors='replace').rstrip()}[/red]"
                    )
                    self.query_one("#bottom-panel", TabbedContent).active = (
                        "tab-problems"
                    )

            await asyncio.gather(
                read_stdout(process.stdout), read_stderr(process.stderr)
            )

            await process.wait()
            status = "✅" if process.returncode == 0 else "❌"
            terminal.write(f"{status} Process exited with code {process.returncode}")
        except Exception as e:
            terminal.write(f"❌ Stream error: {e}")

    def action_toggle_breakpoint(self) -> None:
        """Inject a breakpoint() at the cursor."""
        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        if self.current_file_path and self.current_file_path in open_tabs_map:
            if self.current_file_path.suffix == ".py":
                tab_id = open_tabs_map[self.current_file_path]
                editor = self.query_one(f"#editor-{tab_id}", TextArea)

                # Get current indentation
                cursor_loc = editor.cursor_location
                row_text = editor.get_text_range(
                    (cursor_loc[0], 0), (cursor_loc[0], cursor_loc[1])
                )
                indent = len(row_text) - len(row_text.lstrip())

                editor.insert(f"breakpoint()\n{' ' * indent}")
                self.notify("Breakpoint injected!", title="Debugger")
                self.query_one(TerminalArea).write(
                    "🔴 Breakpoint added. Use Ctrl+Y to run in Debug Mode."
                )
            else:
                self.notify(
                    "Breakpoints are only supported in Python.", severity="error"
                )

    def action_run_debugger(self) -> None:
        if not self.current_file_path or self.current_file_path.suffix != ".py":
            self.notify("Only Python files can be debugged.", severity="error")
            return
        self.action_save()
        
        self.query_one("#bottom-panel", TabbedContent).active = "tab-debugger"
        log = self.query_one("#dbg-log", RichLog)
        log.clear()
        log.write(f"🐛 Starting Debugger for {self.current_file_path.name}...")
        
        from pdb_client import PdbWrapper
        if getattr(self, "pdb_wrapper", None):
            self.pdb_wrapper.terminate()
            
        self.pdb_wrapper = PdbWrapper(str(self.current_file_path), self.workspace_path)
        
        def on_output(text):
            self.call_from_thread(log.write, text)
            
        def on_line_changed(filepath, lineno):
            def _update_ui():
                if str(self.current_file_path) != filepath:
                    from pathlib import Path
                    self.load_file(Path(filepath), self.active_split_id)
                editor = self.get_active_editor()
                if editor:
                    from textual.widgets.text_area import Selection
                    try:
                        row = lineno - 1
                        line_len = len(editor.document.get_line(row))
                        editor.cursor_location = (row, 0)
                        editor.selection = Selection((row, 0), (row, line_len))
                        editor.focus()
                    except: pass
            self.call_from_thread(_update_ui)
            
        def on_finished():
            self.call_from_thread(self.notify, "Debugger finished.", title="Debugger")
            self.call_from_thread(log.write, "[bold green]Program Exited.[/bold green]")
            self.pdb_wrapper = None
            
        self.pdb_wrapper.on_output = on_output
        self.pdb_wrapper.on_line_changed = on_line_changed
        self.pdb_wrapper.on_finished = on_finished
        
        import asyncio
        asyncio.create_task(self.pdb_wrapper.start())

    def _send_dbg(self, cmd):
        if getattr(self, "pdb_wrapper", None):
            self.pdb_wrapper.send_command(cmd)
        else:
            self.notify("Debugger not running.", severity="warning")

    def action_dbg_next(self) -> None: self._send_dbg("n")
    def action_dbg_step(self) -> None: self._send_dbg("s")
    def action_dbg_cont(self) -> None: self._send_dbg("c")
    def action_dbg_stop(self) -> None:
        if getattr(self, "pdb_wrapper", None):
            self.pdb_wrapper.send_command("q")
            self.pdb_wrapper.terminate()
            self.pdb_wrapper = None
            self.notify("Debugger stopped.")
            
    @on(Button.Pressed, "#btn-dbg-next")
    def btn_dbg_next(self): self.action_dbg_next()
    @on(Button.Pressed, "#btn-dbg-step")
    def btn_dbg_step(self): self.action_dbg_step()
    @on(Button.Pressed, "#btn-dbg-cont")
    def btn_dbg_cont(self): self.action_dbg_cont()
    @on(Button.Pressed, "#btn-dbg-stop")
    def btn_dbg_stop(self): self.action_dbg_stop()


    async def action_profile_run(self) -> None:
        """Run the current python script with cProfile and generate a performance table."""
        if not self.current_file_path or self.current_file_path.suffix != ".py":
            self.notify("Only Python files can be profiled.", severity="warning")
            return

        self.action_save()
        terminal = self.query_one(TerminalArea)
        terminal.write(f"⏱️ Profiling {self.current_file_path.name}...")

        tabbed_content = self.query_one("#bottom-panel", TabbedContent)
        tabbed_content.remove_class("hidden")
        tabbed_content.active = "tab-profiler"

        table = self.query_one("#profiler-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Calls", "Tot Time", "Per Call", "Cum Time", "Function/Line")

        import asyncio

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "cProfile",
            "-s",
            "tottime",
            str(self.current_file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.current_file_path.parent),
        )

        stdout, stderr = await process.communicate()

        if stderr:
            terminal.write(f"⚠️ Profiler Stderr: {stderr.decode('utf-8')}")

        output = stdout.decode("utf-8")
        lines = output.split("\n")

        started_parsing = False
        count = 0
        for line in lines:
            if "ncalls  tottime" in line:
                started_parsing = True
                continue
            if started_parsing and line.strip():
                parts = line.split(None, 5)
                if len(parts) >= 5:
                    try:
                        ncalls = parts[0]
                        tottime = float(parts[1])
                        percall1 = parts[2]
                        cumtime = float(parts[3])
                        func = parts[5] if len(parts) > 5 else parts[4]

                        if tottime > 1.0:
                            t_str = f"[red bold]{tottime:.4f}s[/red bold]"
                        elif tottime > 0.1:
                            t_str = f"[yellow]{tottime:.4f}s[/yellow]"
                        else:
                            t_str = f"[green]{tottime:.4f}s[/green]"

                        if cumtime > 1.0:
                            c_str = f"[red bold]{cumtime:.4f}s[/red bold]"
                        elif cumtime > 0.1:
                            c_str = f"[yellow]{cumtime:.4f}s[/yellow]"
                        else:
                            c_str = f"[green]{cumtime:.4f}s[/green]"

                        table.add_row(ncalls, t_str, percall1, c_str, func)
                        count += 1
                        if count > 50:
                            break
                    except Exception:
                        pass

        terminal.write(f"✅ Profiling complete. Generated {count} heatmap rows.")

    def action_go_to_definition(self) -> None:
        """Jump to the definition of the word under the cursor using AST index."""
        terminal = self.query_one(TerminalArea)
        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )

        if self.current_file_path not in open_tabs_map:
            return

        tab_id = open_tabs_map[self.current_file_path]
        editor = self.query_one(f"#editor-{tab_id}", TextArea)

        if not editor:
            return

        cursor_row, cursor_col = editor.cursor_location
        line = editor.document.get_line(cursor_row)

        import re

        words = re.finditer(r"\b\w+\b", line)
        target_word = None
        for match in words:
            if match.start() <= cursor_col <= match.end():
                target_word = match.group()
                break

        if not target_word:
            terminal.write("❌ No word found under cursor.")
            return

        if target_word in self.global_ast_index:
            loc = self.global_ast_index[target_word]
            path = loc["file"]
            line_idx = loc["line"]

            terminal.write(
                f"🎯 AST Match: Jumping to definition in {path.name} (Line {line_idx+1})"
            )

            self.load_file(path, self.active_split_id)
            new_tab_id = open_tabs_map.get(path)
            if new_tab_id:
                new_editor = self.query_one(f"#editor-{new_tab_id}", TextArea)
                new_editor.move_cursor((line_idx, 0))
                new_editor.focus()
        else:
            terminal.write(f"❌ '{target_word}' not found in Global AST Index.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-file-input":
            filename = event.value.strip()
            if not filename: return
            
            try:
                from pathlib import Path
                new_path = Path(self.workspace_path) / filename
                if not new_path.exists():
                    new_path.touch()
                self.load_file(new_path, self.active_split_id)
                self.query_one(TerminalArea).write(f"📄 Created and opened {filename}")
            except Exception as e:
                self.notify(f"Failed to create file: {e}", severity="error")
                
            event.input.value = ""
            event.input.remove_class("-active")
            try:
                self.query_one(f"#{self.active_split_id}").focus()
            except: pass
            return

        if event.input.id == "search-input":
            query = event.value
            if not query:
                return

            terminal = self.query_one(TerminalArea)
            terminal.write(f"🔍 Global Search for: '{query}'...")

            found = False
            workspace = Path(self.workspace_path)

            for path in workspace.rglob("*"):
                if (
                    path.is_file()
                    and not path.name.startswith(".")
                    and "__pycache__" not in str(path)
                ):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f):
                                if query in line:
                                    terminal.write(
                                        f"🎯 Found in {path.name} (Line {i+1})"
                                    )
                                    self.load_file(path, self.active_split_id)

                                    open_tabs_map = (
                                        self.open_tabs
                                        if self.active_split_id == "editor-tabs"
                                        else self.split_open_tabs
                                    )
                                    if path in open_tabs_map:
                                        tab_id = open_tabs_map[path]
                                        editor = self.query_one(
                                            f"#editor-{tab_id}", TextArea
                                        )
                                        editor.move_cursor((i, line.find(query)))
                                        editor.focus()

                                    found = True
                                    break
                        if found:
                            break
                    except Exception:
                        pass

            if not found:
                terminal.write(f"❌ '{query}' not found in any workspace files.")

            event.input.remove_class("-active")
            event.input.value = ""

        elif event.input.id == "new-file-input":
            filename = event.value
            if not filename:
                return

            base_dir = Path(self.workspace_path)
            if self.current_file_path:
                base_dir = self.current_file_path.parent

            new_path = base_dir / filename
            try:
                new_path.touch(exist_ok=False)
                self.notify(f"Created {filename}", title="Success")
                terminal = self.query_one(TerminalArea)
                terminal.write(f"✨ Created new file: {new_path.name}")

                event.input.remove_class("-active")
                event.input.value = ""

                self.query_one(DirectoryTree).reload()

                self.load_file(new_path, self.active_split_id)
            except FileExistsError:
                self.notify(
                    f"File {filename} already exists!", title="Error", severity="error"
                )
            except Exception as e:
                self.notify(
                    f"Failed to create file: {e}", title="Error", severity="error"
                )

        elif event.input.id == "api-input":
            url = event.value
            if not url:
                return

            api_log = self.query_one("#api-log", RichLog)
            if not url.startswith("http"):
                url = "http://" + url

            api_log.write(f"🌍 GET {url} ...")

            import threading
            import requests
            import json

            def fetch_api():
                try:
                    res = requests.get(url, timeout=10)
                    try:
                        data = res.json()
                        formatted = json.dumps(data, indent=2)
                        self.call_from_thread(
                            api_log.write,
                            f"[green]Status: {res.status_code}[/green]\n```json\n{formatted}\n```",
                        )
                    except Exception:
                        self.call_from_thread(
                            api_log.write,
                            f"[green]Status: {res.status_code}[/green]\n{res.text[:1000]}",
                        )
                except Exception as e:
                    self.call_from_thread(api_log.write, f"[red]Error: {e}[/red]")

            threading.Thread(target=fetch_api).start()
            event.input.value = ""

        elif event.input.id == "console-input":
            cmd = event.value
            console_log = self.query_one("#console-log", RichLog)
            console_log.write(f">>> {cmd}")

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = sys.stdout

            try:
                more = self.repl_interp.runsource(cmd)
                output = sys.stdout.getvalue()
                if output:
                    console_log.write(output.rstrip())

                if more:
                    event.input.placeholder = "... (continuation)"
                else:
                    event.input.placeholder = ">>> Type Python code..."
            except Exception as e:
                console_log.write(f"[red]Error: {e}[/red]")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            event.input.value = ""

    @on(Button.Pressed, "#btn-docker-refresh")
    def refresh_docker(self, event: Button.Pressed) -> None:
        table = self.query_one("#docker-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Image", "Status", "Ports", "Names")
        import subprocess

        try:
            out = subprocess.check_output(
                [
                    "docker",
                    "ps",
                    "--format",
                    "{{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}",
                ],
                text=True,
            )
            for line in out.strip().split("\n"):
                if line:
                    table.add_row(*line.split("\t"))
        except Exception as e:
            table.add_row(f"Error connecting to Docker: {e}", "", "", "", "")

    @on(Button.Pressed, "#btn-monitor-refresh")
    def refresh_monitor(self, event: Button.Pressed) -> None:
        log = self.query_one("#monitor-log", RichLog)
        log.clear()
        import subprocess

        try:
            mem = subprocess.check_output(["free", "-h"], text=True)
            log.write("[bold cyan]=== MEMORY USAGE ===[/bold cyan]")
            log.write(mem.strip())

            disk = subprocess.check_output(["df", "-h", "/"], text=True)
            log.write("\n[bold cyan]=== DISK USAGE ===[/bold cyan]")
            log.write(disk.strip())

            ps = subprocess.check_output(["ps", "aux", "--sort=-%cpu"], text=True)
            lines = ps.strip().split("\n")
            log.write("\n[bold cyan]=== TOP PROCESSES (CPU) ===[/bold cyan]")
            for i in range(min(12, len(lines))):
                log.write(lines[i])
        except Exception as e:
            log.write(f"[red]Error fetching system stats: {e}[/red]")

    @on(events.Key)
    def handle_auto_pairs(self, event: events.Key) -> None:
        """Provide IDE-like keyboard superpowers."""
        focused = self.focused
        if not isinstance(focused, TextArea):
            return

        # --- HTML Auto-Tag Closing ---
        if event.character == ">":
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            col = loc[1]
            tag = ""
            is_tag = False
            for i in range(col - 1, -1, -1):
                if line[i] == "<":
                    if i < col - 1 and line[i + 1] != "/":
                        is_tag = True
                    break
                elif not line[i].isalnum():
                    break
                else:
                    tag = line[i] + tag

            void_elements = [
                "br",
                "img",
                "hr",
                "meta",
                "link",
                "input",
                "source",
                "area",
            ]
            if is_tag and tag and tag.lower() not in void_elements:
                focused.insert(f"></{tag}>")
                for _ in range(len(tag) + 3):
                    focused.action_cursor_left()
                event.stop()
                return

        # --- Quick Delete Line (Ctrl+X) ---
        if event.key == "ctrl+x":
            if not focused.selected_text:
                loc = focused.cursor_location
                line = focused.document.get_line(loc[0])
                if loc[0] < focused.document.line_count - 1:
                    focused.delete((loc[0], 0), (loc[0] + 1, 0))
                else:
                    focused.delete((loc[0], 0), (loc[0], len(line)))
                event.stop()
                return

        # --- Line Duplication (Alt+Shift+Down) ---
        if event.key in ["alt+shift+down", "shift+alt+down"]:
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            # Append line below
            focused.move_cursor((loc[0], len(line)))
            focused.insert("\n" + line)
            # Restore cursor column on the new line
            focused.move_cursor((loc[0] + 1, loc[1]))
            event.stop()
            return

        # --- Smart Auto-Indent on Enter ---
        if event.key == "enter":
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            if loc[1] == len(line) and line.rstrip().endswith(":"):
                indent = len(line) - len(line.lstrip())
                new_indent = indent + 4
                focused.insert("\n" + " " * new_indent)
                event.stop()
                return

        # --- Smart Comment Toggle (Ctrl+T) ---
        if event.key == "ctrl+t":
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            if line.lstrip().startswith("#"):
                new_line = (
                    line.replace("# ", "", 1)
                    if line.lstrip().startswith("# ")
                    else line.replace("#", "", 1)
                )
            else:
                indent = len(line) - len(line.lstrip())
                new_line = line[:indent] + "# " + line[indent:]

            focused.delete((loc[0], 0), (loc[0], len(line)))
            focused.move_cursor((loc[0], 0))
            focused.insert(new_line)
            focused.move_cursor((loc[0], loc[1]))
            event.stop()
            return

        # --- Smart Line Moving ---
        if event.key == "alt+up":
            loc = focused.cursor_location
            if loc[0] > 0:
                curr = focused.document.get_line(loc[0])
                above = focused.document.get_line(loc[0] - 1)
                focused.delete((loc[0] - 1, 0), (loc[0], len(curr)))
                focused.move_cursor((loc[0] - 1, 0))
                focused.insert(f"{curr}\n{above}")
                focused.move_cursor((loc[0] - 1, loc[1]))
            event.stop()
            return

        if event.key == "alt+down":
            loc = focused.cursor_location
            if loc[0] < focused.document.line_count - 1:
                curr = focused.document.get_line(loc[0])
                below = focused.document.get_line(loc[0] + 1)
                focused.delete((loc[0], 0), (loc[0] + 1, len(below)))
                focused.move_cursor((loc[0], 0))
                focused.insert(f"{below}\n{curr}")
                focused.move_cursor((loc[0] + 1, loc[1]))
            event.stop()
            return

        # --- Tab Snippets Expansion ---
        if event.key == "tab":
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            col = loc[1]

            word = ""
            for i in range(col - 1, -1, -1):
                if line[i].isalpha():
                    word = line[i] + word
                else:
                    break

            snippets = {
                "pr": ("print()", 1),
                "df": ("def ():", 3),
                "cl": ("class :", 1),
                "im": ("import ", 0),
                "rt": ("return ", 0),
                "ifm": ("if __name__ == '__main__':\n    ", 0),
            }

            if word in snippets:
                snippet, left_moves = snippets[word]
                focused.delete((loc[0], col - len(word)), (loc[0], col))
                focused.insert(snippet)
                for _ in range(left_moves):
                    focused.action_cursor_left()
                event.stop()
                return

        pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

        # Step over closing characters if typed
        if event.character in pairs.values():
            loc = focused.cursor_location
            line = focused.document.get_line(loc[0])
            if loc[1] < len(line) and line[loc[1]] == event.character:
                focused.move_cursor((loc[0], loc[1] + 1))
                event.stop()
                return

        # Insert auto-pair
        if event.character in pairs:
            closing = pairs[event.character]
            focused.insert(event.character + closing)
            loc = focused.cursor_location
            focused.move_cursor((loc[0], loc[1] - 1))
            event.stop()
            return

        # Delete pair together on backspace
        if event.key == "backspace":
            loc = focused.cursor_location
            if loc[1] > 0:
                line = focused.document.get_line(loc[0])
                if loc[1] < len(line):
                    prev_char = line[loc[1] - 1]
                    next_char = line[loc[1]]
                    if prev_char in pairs and pairs[prev_char] == next_char:
                        # Delete closing character manually, allow default backspace to delete opening char
                        focused.delete((loc[0], loc[1]), (loc[0], loc[1] + 1))

    def action_global_replace(self) -> None:
        self.push_screen(GlobalReplaceModal())

    def execute_global_replace(self, target: str, replacement: str) -> None:
        import threading

        terminal = self.query_one(TerminalArea)
        terminal.write(
            f"🔄 Executing Global Refactor: '{target}' -> '{replacement}'..."
        )

        def _replace():
            from pathlib import Path

            workspace = Path(self.workspace_path)
            files_changed = 0
            lines_changed = 0

            for path in workspace.rglob("*"):
                if (
                    path.is_file()
                    and not path.name.startswith(".")
                    and "__pycache__" not in str(path)
                    and "node_modules" not in str(path)
                    and ".git" not in str(path)
                ):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()

                        if target in content:
                            new_content = content.replace(target, replacement)
                            lines_changed += content.count(target)

                            with open(path, "w", encoding="utf-8") as f:
                                f.write(new_content)

                            files_changed += 1
                    except Exception:
                        pass

            def _update_ui():
                terminal.write(
                    f"✅ Refactoring Complete! Modified {lines_changed} instances across {files_changed} files."
                )

            self.call_from_thread(_update_ui)

        threading.Thread(target=_replace).start()

    @on(Button.Pressed, "#btn-pkg-list")
    def list_packages(self, event=None) -> None:
        table = self.query_one("#pkg-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Package", "Version")

        import subprocess
        import json
        import threading

        def _list():
            try:
                out = subprocess.check_output(
                    [sys.executable, "-m", "pip", "list", "--format=json"], text=True
                )
                pkgs = json.loads(out)
                self.call_from_thread(self._populate_pkg_table, pkgs)
            except Exception as e:
                pass

        threading.Thread(target=_list).start()

    def _populate_pkg_table(self, pkgs):
        table = self.query_one("#pkg-table", DataTable)
        for p in pkgs:
            table.add_row(p.get("name", ""), p.get("version", ""))

    @on(Button.Pressed, "#btn-pkg-install")
    def install_package(self, event: Button.Pressed) -> None:
        pkg_name = self.query_one("#pkg-input", Input).value.strip()
        if not pkg_name:
            return

        terminal = self.query_one(TerminalArea)
        terminal.write(f"📦 Installing '{pkg_name}' via pip...")

        import threading
        import subprocess

        def _install():
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", pkg_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                for line in proc.stdout:
                    self.call_from_thread(terminal.write, f"[dim]{line.strip()}[/dim]")
                proc.wait()

                if proc.returncode == 0:
                    self.call_from_thread(
                        terminal.write, f"✅ Successfully installed {pkg_name}!"
                    )
                    self.call_from_thread(self._update_requirements, pkg_name)
                    self.call_from_thread(self.list_packages)
                else:
                    self.call_from_thread(
                        terminal.write, f"❌ Failed to install {pkg_name}."
                    )
            except Exception as e:
                self.call_from_thread(terminal.write, f"Error: {e}")

        threading.Thread(target=_install).start()

    def _update_requirements(self, pkg_name):
        from pathlib import Path

        req_file = Path(self.workspace_path) / "requirements.txt"
        try:
            if req_file.exists():
                with open(req_file, "r") as f:
                    content = f.read()
                if pkg_name.lower() not in content.lower():
                    with open(req_file, "a") as f:
                        f.write(f"\n{pkg_name}")
            else:
                with open(req_file, "w") as f:
                    f.write(f"{pkg_name}\n")
            self.query_one(TerminalArea).write(
                f"📝 Added {pkg_name} to requirements.txt"
            )
        except Exception:
            pass

    def action_preview_markdown(self) -> None:
        """Render the current Markdown file visually in a split pane."""
        if not self.current_file_path or self.current_file_path.suffix != ".md":
            self.notify(
                "Only Markdown (.md) files can be previewed.", severity="warning"
            )
            return

        open_tabs_map = (
            self.open_tabs
            if self.active_split_id == "editor-tabs"
            else self.split_open_tabs
        )
        tab_id = open_tabs_map.get(self.current_file_path)
        if not tab_id:
            return

        editor = self.query_one(f"#editor-{tab_id}", TextArea)
        md_content = editor.text

        split_container = self.query_one("#editor-right-wrap")

        if split_container.has_class("hidden"):
            split_container.remove_class("hidden")
            self.query_one("#split-resizer").remove_class("hidden")
            self.query_one(TerminalArea).write(
                "Split view opened for Markdown Preview."
            )

        split_tabs = self.query_one("#editor-tabs-split", TabbedContent)
        preview_tab_id = f"preview-{tab_id}"

        from textual.widgets import Markdown

        try:
            md_viewer = self.query_one(f"#{preview_tab_id}-content", Markdown)
            md_viewer.update(md_content)
            split_tabs.active = preview_tab_id
            self.query_one(TerminalArea).write(
                f"🔄 Refreshed Live Markdown Preview for {self.current_file_path.name}"
            )
            return
        except Exception:
            pass

        md_viewer = Markdown(md_content, id=f"{preview_tab_id}-content")
        pane = TabPane(
            f"👀 {self.current_file_path.name}  ✕", md_viewer, id=preview_tab_id
        )
        split_tabs.add_pane(pane)
        split_tabs.active = preview_tab_id
        self.query_one(TerminalArea).write(
            f"📖 Live Markdown Preview launched for {self.current_file_path.name}"
        )

    def action_start_live_server(self) -> None:
        """Toggle a local HTTP live server on port 8000."""
        term = self.query_one(TerminalArea)
        if self.live_server_process is not None:
            self.live_server_process.terminate()
            self.live_server_process = None
            term.write("[bold yellow]🛑 Live Server stopped.[/bold yellow]")
            self.notify("Live Server Stopped", title="Server")
        else:
            try:
                import subprocess
                import sys

                self.live_server_process = subprocess.Popen(
                    [sys.executable, "-m", "http.server", "8000"],
                    cwd=self.workspace_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                term.write(
                    "[bold green]🌐 Live Server started at http://localhost:8000[/bold green]"
                )
                term.write(f"Serving directory: {self.workspace_path}")
                self.notify("Live Server running on port 8000", title="Server")
            except Exception as e:
                term.write(f"[bold red]Failed to start Live Server: {e}[/bold red]")
                self.notify(f"Failed to start: {e}", severity="error")

    @on(Button.Pressed, "#activity-files")
    def show_files(self):
        self.query_one("#sidebar-switcher").current = "sidebar-explorer"

    @on(Button.Pressed, "#activity-search")
    def show_search(self):
        self.query_one("#sidebar-switcher").current = "sidebar-search"
        self.query_one("#sidebar-search-input").focus()

    @on(Button.Pressed, "#activity-git")
    def show_git(self) -> None:
        self.query_one("#sidebar-switcher", ContentSwitcher).current = "sidebar-git"
        self.action_refresh_git()

    def action_refresh_git(self) -> None:
        async def fetch_git():
            try:
                import asyncio

                proc = await asyncio.create_subprocess_shell(
                    "git status -s",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace_path,
                )
                stdout, _ = await proc.communicate()
                status = stdout.decode().strip()

                def update_ui():
                    lst = self.query_one("#git-status-list", OptionList)
                    lst.clear_options()
                    if not status:
                        lst.add_option("✨ Working tree clean", disabled=True)
                    else:
                        for line in status.split("\n"):
                            if line.strip():
                                lst.add_option(line, disabled=True)

                self.call_from_thread(update_ui)
            except Exception:
                pass

        import asyncio

        asyncio.create_task(fetch_git())

    @on(Button.Pressed, "#btn-git-refresh")
    def on_git_refresh(self) -> None:
        self.action_refresh_git()

    @on(Button.Pressed, "#btn-git-commit")
    def on_git_commit(self) -> None:
        msg_input = self.query_one("#git-commit-msg", Input)
        msg = msg_input.value
        if not msg:
            self.notify(
                "Commit message cannot be empty!", title="Git", severity="error"
            )
            return

        async def do_commit():
            try:
                import asyncio

                proc_add = await asyncio.create_subprocess_shell(
                    "git add .", cwd=self.workspace_path
                )
                await proc_add.communicate()
                proc_cmt = await asyncio.create_subprocess_shell(
                    f'git commit -m "{msg}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace_path,
                )
                stdout, stderr = await proc_cmt.communicate()

                def post_commit():
                    msg_input.value = ""
                    self.action_refresh_git()
                    self.notify(f"Committed: {msg}", title="Git")

                self.call_from_thread(post_commit)
            except Exception as e:
                self.call_from_thread(
                    self.notify, str(e), title="Git Error", severity="error"
                )

        import asyncio

        asyncio.create_task(do_commit())

    @on(Button.Pressed, "#activity-plugins")
    def show_plugins(self):
        self.query_one("#sidebar-switcher").current = "sidebar-plugins"
        lst = self.query_one("#sidebar-plugins-list", OptionList)
        lst.clear_options()
        if not self.workspace_trusted:
            lst.add_option("🔒 Workspace Restricted - Plugins disabled")
            return

        lst.add_option("✅ Workspace Trusted")
        if self._plugin_manifest:
            lst.add_option("--- Installed Extensions ---")
            for entry in self._plugin_manifest:
                loaded = "✅" if entry.get("loaded") else "❌"
                lst.add_option(
                    f"🧩 {entry.get('name')} {loaded} (v{entry.get('version')})"
                )
        else:
            from pathlib import Path

            plugins_dir = Path(self.workspace_path) / ".essa_plugins"
            if plugins_dir.exists():
                for p in plugins_dir.glob("*.py"):
                    if not p.name.startswith("_"):
                        lst.add_option(f"🧩 {p.name} (not loaded)")
            else:
                lst.add_option("No plugins directory found.")

    @on(OptionList.OptionSelected, "#sidebar-plugins-list")
    def on_plugin_selected(self, event: OptionList.OptionSelected) -> None:
        prompt_text = str(event.option.prompt)
        if "🧩" in prompt_text:
            ext_name = prompt_text.split("(")[0].replace("🧩", "").strip()
            self.notify(f"Selected extension: {ext_name}", title="Extensions")
            self.query_one(TerminalArea).write(
                f"[bold cyan]Extension {ext_name} activated.[/bold cyan]"
            )

    @on(Button.Pressed, "#activity-settings")
    def show_settings(self):
        self.action_open_settings()

    @on(Button.Pressed, "#btn-sidebar-search")
    def do_sidebar_search(self):
        query = self.query_one("#sidebar-search-input", Input).value
        log = self.query_one("#sidebar-search-results", RichLog)
        log.clear()
        if not query:
            return
        import threading
        import subprocess

        log.write(f"Searching for '{query}'...\n")

        def _search():
            try:
                out = subprocess.check_output(
                    ["grep", "-rn", query, self.workspace_path], text=True
                )
                lines = out.splitlines()
                if not lines:
                    self.call_from_thread(log.write, "No results found.")
                for line in lines[:100]:
                    self.call_from_thread(log.write, line)
                if len(lines) > 100:
                    self.call_from_thread(
                        log.write, f"\n...and {len(lines) - 100} more results."
                    )
            except Exception:
                self.call_from_thread(log.write, "No results found.")

        threading.Thread(target=_search).start()


def run():
    """CLI entry point for EssaIDE."""
    parser = argparse.ArgumentParser(description="EssaIDE - The Custom Terminal IDE")
    parser.add_argument("path", nargs="?", default=".", help="Workspace path to open")
    args = parser.parse_args()

    app = EssaIDEApp(workspace_path=args.path)
    app.run()


if __name__ == "__main__":
    run()
