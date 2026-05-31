# EssaIDE: Comprehensive User Manual

Welcome to **EssaIDE**, a high-performance, AI-powered terminal-based IDE designed to bring the capabilities of desktop editors (like VS Code) directly into your command-line environment.

This manual will guide you through all the features, layouts, and tools available in the editor so you can maximize your productivity.

---

## 1. The Interface Layout

EssaIDE is organized into four main areas:

1. **Activity Bar (Leftmost Edge):** Contains quick-access icons to toggle your sidebars.
   - 📁 **Files:** Opens the Directory Explorer.
   - 🔍 **Search:** Opens the Global Search panel.
   - 🧩 **Extensions:** Opens the Plugin & Security Manager.
   - ⚙️ **Settings:** Opens the Settings Dashboard.
2. **Sidebar (Left Panel):** Contextually changes based on the Activity Bar selection.
3. **Editor Area (Center):** The main workspace where you read and write code. Supports split-pane viewing.
4. **Bottom Panel (Bottom):** Contains your Integrated Terminal, Output logs, and debug tools.

---

## 2. Core Workflows

### Launching the IDE
EssaIDE includes one-click automation scripts to handle environments and dependencies for you.
- **Windows:** Double-click `start_windows.bat` from your file explorer.
- **macOS / Linux:** Run `./start_unix.sh` from your terminal.
Both scripts will automatically spawn the IDE in your terminal.

### Opening a Project
1. Press `Ctrl+O` or `Ctrl+Shift+P` -> Select **Open Folder**.
2. Type the absolute path to your project directory.
3. Press `Enter`. The Directory Tree in the Sidebar will automatically populate.

### Creating & Managing Files
- **New File:** Press `Ctrl+N`, type the filename, and hit `Enter`.
- **Open File:** Navigate the Directory Explorer and click on a file, or hit `Enter` while highlighting it.
- **Save File:** Press `Ctrl+S` to save any unsaved changes. (Unsaved files are marked with a `*` indicator in the tab).
- **Delete File:** Open the Command Palette (`Ctrl+Shift+P`) and type `Delete File` to delete the currently focused file.

### Searching the Workspace
1. Click the **🔍 Search** icon in the Activity Bar.
2. Type your query into the input field and click **Find All**.
3. Results will be asynchronously scraped from your workspace using `grep` and printed in the results panel.

---

## 3. Advanced Features

### 🖥️ Integrated Terminal
EssaIDE ships with a fully asynchronous pseudo-terminal emulator built directly into the bottom panel.
1. Press `Ctrl+Shift+P` -> **Toggle Bottom Panel** (or click the bottom bar) to open it.
2. Navigate to the **Output** tab.
3. Type shell commands (e.g., `git status`, `pip install`, `ls -la`) directly into the input field at the very bottom.
4. The terminal respects `cd` commands, meaning you can easily change directories without breaking the session.

### 🌐 Live HTTP Server
You can instantly host your current project locally (perfect for web developers):
1. Open the Command Palette (`Ctrl+Shift+P`).
2. Select **🌐 Toggle Live Server**.
3. The IDE will spin up an asynchronous background server on `http://localhost:8000`. You can stop it at any time by triggering the command again.

### 🌓 Theme Engine & Syntax Highlighting
EssaIDE uses `tree-sitter` for rapid, multi-colored AST syntax highlighting. You can customize the look of the editor:
1. Press `F2` to open Settings.
2. Use the **Editor Theme** dropdown to select between modern themes: *Monokai, VS Code Dark, GitHub Light, or Dracula.*
3. Your editor will instantly hot-reload with the new color palette.

### ✂️ Split View Editing
Compare files side-by-side without leaving your terminal.
1. Open the Command Palette (`Ctrl+Shift+P`).
2. Select **↔️ Toggle Split View**.
3. Use the **Close Tab** (`Ctrl+Shift+P -> Close Tab`) action or click the `X` to manage your split editors.

### 🔒 Workspace Trust & Sandboxed Extensions
To prevent malicious code execution, EssaIDE implements a Workspace Trust Model.
1. When opening a new folder, you will be prompted to **Trust** or **Restrict** the workspace.
2. **Trusted:** Allows local `.essa_plugins` to execute Python code safely.
3. **Restricted:** Disables plugins.
You can view your loaded Extensions by clicking the **🧩 Exts** icon in the Activity Bar. Click on any extension in the list to activate it.

---

## 4. Keyboard Shortcuts Reference

| Shortcut | Action |
| :--- | :--- |
| **`Ctrl+Shift+P`** | Open Command Palette |
| **`Ctrl+O`** | Open Workspace Folder / Project |
| **`Ctrl+N`** | Create a New File |
| **`Ctrl+S`** | Save Current File |
| **`Ctrl+F`** | Focus Search Panel |
| **`F2`** | Open Settings Dashboard |
| **`Ctrl+Q`** | Quit Application (Safely prompts on unsaved files) |

---

## 5. Troubleshooting & FAQ

**Q: My syntax highlighting isn't working for a specific language.**
A: Ensure that `textual[syntax]` is correctly installed in your environment. Tree-sitter dynamically downloads language grammars as needed, so ensure you have an active internet connection on the first load of a new language.

**Q: The terminal process is frozen.**
A: If you run an interactive TTY program (like `vim` or `nano`) inside the Integrated Terminal, it may stall because it is a pseudo-terminal (not a full PTY). Stick to standard CLI output commands.

**Q: Where are my settings saved?**
A: Editor settings are saved in memory and persist across hot-reloads during your session. Workspace trust configurations are saved to a local `.essa_session.json` file inside your project root.
