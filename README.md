# Zenpad

![Version 1.2.0](https://img.shields.io/badge/version-1.2.0-blue.svg)
![License GPL-2.0](https://img.shields.io/badge/license-GPL--2.0-green.svg)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)

**Zenpad** is a lightweight, keyboard-driven text editor for the Linux desktop, built with Python and GTK+. Designed to provide a distraction-free environment for power users and developers, it combines the speed of a simple notepad with IDE-inspired keyboard shortcuts for fast navigation, text manipulation, and efficient editing. Unlike traditional click-based editors, Zenpad focuses on a keyboard-centric workflow to maximize productivity.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [License](#license)

## Features

Zenpad leverages `GtkSourceView 4` to provide robust text editing capabilities while maintaining a minimal footprint.

*   **Syntax Highlighting:** Support for over 100 programming languages.
*   **Multi-Tab Interface:** Efficiently manage multiple files in a single window.
*   **Smart Editing:**
    *   Automatic indentation and bracket matching.
    *   Configurable word wrap and line numbering.
    *   Toggleable "Highlight Current Line" for focused editing.
*   **Search and Replace:** Incremental search with real-time occurrence counting.
*   **Session Persistence:** Automatically restores open tabs and window state across sessions.
*   **System Integration:** Seamlessly integrates with Linux desktop themes and workflows.

## Requirements

Zenpad requires a standard GNOME/GTK environment.

*   Python 3.6+
*   GTK+ 3.22+
*   GtkSourceView 4
*   PyGObject (python3-gi)

## Installation

### Debian / Ubuntu

The recommended way to install Zenpad is via the pre-built Debian package.

1.  **Download** the latest release (`.deb`).
2.  **Install** via command line:

    ```bash
    sudo dpkg -i zenpad_1.2.0_all.deb
    sudo apt-get install -f
    ```

### Source Installation

To run Zenpad directly from the source code:

```bash
pip install .
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

We believe that the best software is built through transparency and rigorous testing. Whether you are interested in auditing the codebase for security vulnerabilities, optimizing GTK rendering performance, or implementing new features, your expertise is welcome here. Please feel free to fork the repository, submit pull requests, or open issues for any findings.

To build the Debian package from source, ensure you have the necessary build tools installed:

```bash
sudo apt install build-essential fakeroot debhelper dh-python python3-all python3-gi gir1.2-gtksource-4
```

Build the package:
```bash
dpkg-buildpackage -us -uc
```

## License

Zenpad is open-source software licensed under the **GPL-2.0**.
See the [LICENSE](LICENSE) file for more details.

---
Copyright © 2025 **Team Zenpad**.
