# 🧘 Zenpad

> **A modern, lightweight text editor built for the flow state.**

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-GPL--2.0-green.svg)

---

**Zenpad** is designed to be fast, minimal, and efficient. It gets out of your way so you can focus on what matters: your code.  
Whether you're tweaking a config file or writing your next masterpiece, Zenpad provides a clean, distraction-free environment with all the modern essentials.

## ✨ Features

*   **⚡ Lightning Fast**: Starts instantly, designed for speed.
*   **🎨 Syntax Highlighting**: Powered by `GtkSourceView 4`, supporting hundreds of languages.
*   **📂 Tabbed Interface**: Effortlessly switch between multiple files.
*   **🧠 Smart Helpers**:
    *   Auto-indentation & Bracket matching.
    *   **"No Distractions" Mode**: Disabled line highlighting by default for a clearer view.
*   **🔍 Power Search**: Incremental search with real-time match counting.
*   **💾 Session Restore**: Pick up exactly where you left off.
*   **🐧 Native Integration**: Follows Linux system themes (Dark/Light) automatically.

##  Installation

### 📦 Debian / Ubuntu (Recommended)

Get the latest `.deb` release and install it via terminal:

```bash
sudo dpkg -i zenpad_1.0.0_all.deb
sudo apt-get install -f  # Fixes dependencies automatically
```

### 🔓 Native Build

Want to hack on it? Build it clearly from source:

```bash
# 1. Grab dependencies
sudo apt install build-essential fakeroot debhelper dh-python python3-all python3-gi gir1.2-gtksource-4

# 2. Build the package
dpkg-buildpackage -us -uc
```

## 🎮 Usage

Launch from your app menu or command line:

```bash
zenpad                 # Start empty
zenpad my_script.py    # Open a file
```

---

*Made by **Team Zenpad**.*
