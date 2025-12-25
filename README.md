# Zenpad

![Version 1.0.0](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License GPL-2.0](https://img.shields.io/badge/license-GPL--2.0-green.svg)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)

**Zenpad** is a lightweight, high-performance text editor for the Linux desktop, built with Python and GTK+. detailed to provide a distraction-free coding environment, it combines the speed of a simple notepad with the essential features required by developers and power users.

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
    sudo dpkg -i zenpad_1.0.0_all.deb
    sudo apt-get install -f
    ```

### Source Installation

To run Zenpad directly from the source code:

```bash
# Implement standard setuptools installation or run directly
python3 setup.py install --user
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
