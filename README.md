# EssaIDE

**EssaIDE** is an ultra-fast, cross-platform, AI-powered terminal IDE built entirely in Python using the Textual framework. Designed for the modern terminal, it brings native syntax highlighting, a multi-pane split view, an integrated shell, a live server, and sandboxed extensions into a beautiful, mouse-friendly CLI UI.

It is fully capable of running natively on macOS, Linux, and Windows.

---

## 🚀 Features

- **Multi-color Syntax Highlighting:** Powered by `tree-sitter` for flawless AST-based syntax coloring.
- **Integrated Interactive Terminal:** A fully asynchronous, built-in shell emulator.
- **Live HTTP Server:** Instantly host your workspace locally via the Command Palette.
- **Split Views:** Horizontally and vertically split text editors to boost productivity.
- **Sandboxed Extensions:** Secure plugin architecture with workspace trust mechanisms.
- **Theme Engine:** Instantly swap between themes like Monokai, VS Code Dark, Dracula, and GitHub Light.
- **Fuzzy Command Palette:** Press `Ctrl+Shift+P` to access any action instantly.

---

## 🛠️ Installation Guide

EssaIDE is designed to run seamlessly on **Windows, macOS, and Linux**.

### Prerequisites
Make sure you have **Python 3.10+** installed on your system.

### Option 1: Quick Install (Development / Portable)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/EssaIDE.git
   cd EssaIDE
   ```

2. **Create a virtual environment (Recommended):**
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows:**
     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the IDE:**
   ```bash
   python main.py
   ```

---

### Option 2: System-wide Global Install (CLI Command)

If you want to install EssaIDE globally so you can launch it from any directory using the `essa-ide` command, use the `setup.py` installer.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/EssaIDE.git
   cd EssaIDE
   ```

2. **Install globally via PIP:**
   ```bash
   pip install .
   ```
   *(On some systems, you may need to run `pipx install .` or use `--user`)*

3. **Launch the IDE from anywhere:**
   ```bash
   essa-ide
   ```
   *(This will automatically open the IDE in your current working directory)*

---

## 💻 Keyboard Shortcuts

- **`Ctrl+Shift+P`** : Open Command Palette
- **`Ctrl+O`** : Open Workspace Folder
- **`Ctrl+N`** : Create New File
- **`Ctrl+S`** : Save Current File
- **`Ctrl+F`** : Search across workspace
- **`F2`** : Open Settings Dashboard
- **`Ctrl+Q`** : Quit Application

---

## 🛡️ License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
