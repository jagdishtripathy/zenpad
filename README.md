# Zenpad

![Platform](https://img.shields.io/badge/PLATFORM-LINUX-blue?style=flat-square&labelColor=333)
![Built With](https://img.shields.io/badge/PYTHON-GTK+-green?style=flat-square&labelColor=333)
![Editor](https://img.shields.io/badge/EDITOR-GtkSourceView%204-orange?style=flat-square&labelColor=333)
![Version](https://img.shields.io/badge/VERSION-1.5.0-yellow?style=flat-square&labelColor=333)
![License](https://img.shields.io/badge/LICENSE-GPL--2.0-brightgreen?style=flat-square&labelColor=333)

**Zenpad** is a keyboard-first text editor for developers who find traditional editors like gedit or mousepad too mouse-dependent. Built with Python and GTK+, it brings IDE-level keyboard navigation to a lightweight notepad—duplicate lines with `Ctrl+D`, delete lines instantly with `Ctrl+Shift+K`, jump between tabs without touching your mouse, and never lose your work with automatic session restore.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [Code of Conduct](#code-of-conduct)
- [License](#license)

## Features

### What Zenpad Does That Others Don't

*   **Keyboard-First Editing:** IDE shortcuts in a lightweight editor—`Ctrl+D` to duplicate lines, `Ctrl+Shift+K` to delete lines, `Ctrl+/` to toggle comments. No reaching for the mouse.
*   **Session Memory:** Close Zenpad with 10 tabs open, reopen it tomorrow—all tabs restored exactly where you left off. gedit doesn't do this.
*   **Smart Auto-Pairing:** Context-aware bracket and quote completion. Type `(` after a word? Just inserts `(`. At end of line? Inserts `()` and places cursor inside. Select text and press `"`? Wraps it.
*   **Binary File Safety:** Open a `.exe` or image by accident? Zenpad detects it, shows a hex preview, and prevents corruption. Other editors just show garbage.
*   **Encoding Intelligence:** Auto-detects UTF-8, Windows-1252, ISO-8859-1. Switch encodings on the fly without closing the file.
*   **Real-Time Search Stats:** See "3 of 47 matches" as you type—incremental search with live occurrence counting.

### Core Capabilities

*   **Syntax Highlighting:** 100+ languages via GtkSourceView 4.
*   **Multi-Tab Interface:** Manage multiple files with keyboard navigation (`Ctrl+Page Up/Down`).
*   **Distraction-Free:** No toolbars if you don't want them. Toggle everything with keyboard shortcuts.

## Requirements

Zenpad requires a standard GNOME/GTK environment.

*   Python 3.6+
*   GTK+ 3.22+
*   GtkSourceView 4
*   PyGObject (python3-gi)

## Installation

### APT Repository (Recommended)

Install Zenpad from our official APT repository:

```bash
# Add GPG key
curl -fsSL https://zenpad-dev.github.io/apt/zenpad.gpg | sudo gpg --dearmor -o /usr/share/keyrings/zenpad.gpg

# Add repository
echo "deb [signed-by=/usr/share/keyrings/zenpad.gpg] https://zenpad-dev.github.io/apt stable main" | sudo tee /etc/apt/sources.list.d/zenpad.list

# Install
sudo apt update
sudo apt install zenpad
```

**Updates:** `sudo apt update && sudo apt upgrade zenpad`

### Manual Installation (Debian / Ubuntu)

Download the latest `.deb` from [Releases](https://github.com/jagdishtripathy/zenpad/releases):

```bash
sudo dpkg -i zenpad_1.5.0_all.deb
sudo apt-get install -f
```

### Source Installation

```bash
pip install . # for local development only
```

## Usage

Zenpad can be launched from the application menu or via the terminal.

**Command Line Arguments:**
```bash
zenpad [filename]...
```

**Examples:**
```bash
zenpad                   # Launch with empty buffer
zenpad README.md         # Open specific file
zenpad file1.py file2.js # Open multiple files
```

## Development

**We actively invite the developer and cybersecurity communities to collaborate on Zenpad.** 

We believe that the best software is built through transparency and rigorous testing. Whether you are interested in auditing the codebase for security vulnerabilities, optimizing GTK rendering performance, or implementing new features, your expertise is welcome here.

### Contributing

Please read our **[Contributing Guide](CONTRIBUTING.md)** for detailed instructions on:

- Setting up the development environment
- Making changes and testing
- Commit message guidelines
- Submitting pull requests
- Building the Debian package

### Quick Start

To run Zenpad from source for development:

```bash
# Clone the repository
git clone https://github.com/jagdishtripathy/zenpad.git
cd zenpad

# Run from source
python3 -m zenpad.main
```

### Build Debian Package

Install the required build dependencies:

```bash
sudo apt install build-essential fakeroot debhelper dh-python python3-all python3-gi gir1.2-gtksource-4
```

Build the package:

```bash
dpkg-buildpackage -us -uc
```

The `.deb` file will be created in the parent directory.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes and version releases.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

Zenpad is open-source software licensed under the **GPL-2.0**.
See the [LICENSE](LICENSE) file for more details.

---
Copyright © 2025 **Team Zenpad**
