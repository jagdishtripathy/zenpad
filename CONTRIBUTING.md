# Contributing to Zenpad

Thank you for your interest in contributing to Zenpad! This guide will walk you through the entire process from setting up your development environment to submitting a pull request.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Commit Guidelines](#commit-guidelines)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Building the Package](#building-the-package)
- [Resolving Issues](#resolving-issues)
- [Code Style](#code-style)

---

## Getting Started

### 1. Fork the Repository

1. Go to [https://github.com/YOUR_USERNAME/zenpad](https://github.com/jagdishtripathy/zenpad)
2. Click the **Fork** button in the top-right corner
3. This creates a copy of the repository in your GitHub account

### 2. Clone Your Fork

```bash
git clone https://github.com/jagdishtripathy/zenpad.git
cd zenpad
```

### 3. Add Upstream Remote

```bash
git remote add upstream https://github.com/jagdishtripathy/zenpad.git
```

This allows you to sync with the main repository later.

---

## Development Setup

### System Requirements

- **OS**: Linux (Ubuntu/Debian recommended)
- **Python**: 3.6 or higher
- **GTK**: 3.22+
- **GtkSourceView**: 4.x

### Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-gi python3-gi-cairo \
                 gir1.2-gtk-3.0 gir1.2-gtksource-4 \
                 libgtksourceview-4-dev
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip python3-gobject gtk3 \
                 gtksourceview4 gtksourceview4-devel
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip python-gobject gtk3 gtksourceview4
```

### Install Python Dependencies

```bash
pip install PyGObject
```

### Run Zenpad from Source

```bash
python3 -m zenpad.main
```

Or with specific files:
```bash
python3 -m zenpad.main file1.txt file2.py
```

---

## Making Changes

### 1. Create a Feature Branch

Always create a new branch for your changes:

```bash
# Sync with upstream first
git fetch upstream
git checkout main
git merge upstream/main

# Create your feature branch
git checkout -b feature/your-feature-name
```

**Branch naming conventions:**
- `feature/` - New features (e.g., `feature/vim-mode`)
- `fix/` - Bug fixes (e.g., `fix/cursor-position`)
- `docs/` - Documentation updates (e.g., `docs/update-readme`)
- `refactor/` - Code refactoring (e.g., `refactor/editor-cleanup`)

### 2. Make Your Changes

Edit the relevant files in the `zenpad/` directory:

| File | Purpose |
|------|---------|
| `main.py` | Application entry point, CLI parsing |
| `window.py` | Main window, menus, toolbar, actions |
| `editor.py` | Editor tab, text buffer, key handling |
| `preferences.py` | Settings dialog and configuration |
| `session.py` | Session save/restore functionality |
| `analysis.py` | Language detection and analysis |
| `file_utils.py` | File operations, encoding detection |

### 3. Test Your Changes

Run Zenpad and manually test your changes:

```bash
python3 -m zenpad.main
```

Test edge cases:
- Opening various file types
- Keyboard shortcuts
- New/Save/Close operations
- Multiple tabs

---

## Commit Guidelines

### Commit Message Format

Use conventional commit messages:

```
<type>: <short description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - A new feature
- `fix:` - A bug fix
- `docs:` - Documentation changes
- `style:` - Formatting, no code change
- `refactor:` - Code restructuring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

**Examples:**
```bash
git commit -m "feat: add word count display in status bar"
git commit -m "fix: correct cursor position after paste"
git commit -m "docs: update installation instructions"
```

### Linking Issues

If your commit fixes an issue, reference it:

```bash
git commit -m "fix: resolve auto-pair for brackets

Fixes #64"
```

---

## Submitting a Pull Request

### 1. Push Your Branch

```bash
git push origin feature/your-feature-name
```

### 2. Create Pull Request

1. Go to your fork on GitHub
2. Click **"Compare & pull request"**
3. Fill in the PR template:
   - **Title**: Clear, descriptive title
   - **Description**: What changes and why
   - **Related Issue**: Link with `Fixes #XX` or `Closes #XX`

### 3. PR Checklist

Before submitting, ensure:

- [ ] Code runs without errors
- [ ] Changes tested manually
- [ ] Commit messages follow guidelines
- [ ] PR description is complete
- [ ] No merge conflicts with `main`

### 4. Respond to Review

Maintainers may request changes. Update your PR:

```bash
# Make requested changes
git add .
git commit -m "fix: address review feedback"
git push origin feature/your-feature-name
```

---

## Building the Package

### Prerequisites

Install build tools:

```bash
sudo apt install build-essential fakeroot debhelper dh-python \
                 python3-all python3-setuptools
```

### Build Debian Package

**Important**: Build from within a native Linux filesystem, not Windows (NTFS) mounted directories.

```bash
# Clone to Linux filesystem (if on WSL)
cd ~
git clone https://github.com/YOUR_USERNAME/zenpad.git
cd zenpad

# Build the package
dpkg-buildpackage -us -uc
```

The `.deb` file will be created in the parent directory:
```bash
ls ../*.deb
# Output: ../zenpad_1.5.0_all.deb
```

### Install Locally

```bash
sudo dpkg -i ../zenpad_1.5.0_all.deb
sudo apt-get install -f  # Fix any dependency issues
```

### Source Installation

For development:
```bash
pip install -e .
```

---

## Resolving Issues

### Step-by-Step Guide

1. **Find an Issue**
   - Browse [open issues](https://github.com/jagdishtripathy/zenpad/issues)
   - Look for `good first issue` or `help wanted` labels
   - Comment to claim it: "I'll work on this!"

2. **Understand the Problem**
   - Read the issue description carefully
   - Reproduce the bug locally
   - Identify the relevant code files

3. **Plan Your Fix**
   - Think about the root cause, not just symptoms
   - Consider edge cases
   - Discuss approach in the issue if unsure

4. **Implement the Fix**
   ```bash
   git checkout -b fix/issue-XX-description
   # Make changes
   python3 -m zenpad.main  # Test
   ```

5. **Submit PR**
   - Reference the issue in your PR
   - Explain what you changed and why

### Issue Labels

| Label | Meaning |
|-------|---------|
| `bug` | Something isn't working |
| `enhancement` | New feature request |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `question` | Further information requested |

---

## Code Style

### Python Guidelines

- **Indentation**: 4 spaces (no tabs)
- **Line length**: 100 characters max
- **Naming**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`

### Example

```python
class EditorTab(Gtk.ScrolledWindow):
    """A single editor tab with text view and buffer."""
    
    def __init__(self):
        super().__init__()
        self.file_path = None
        self.file_encoding = "UTF-8"
    
    def on_key_press(self, widget, event):
        """Handle key press events."""
        keyval = event.keyval
        
        # Auto-close brackets
        if keyval == Gdk.KEY_parenleft:
            self._insert_pair("(", ")")
            return True
        
        return False
```

### Comments

- Use docstrings for classes and functions
- Add inline comments for complex logic
- Remove debug print statements before committing

---

## Questions?

- Open a [Discussion](https://github.com/jagdishtripathy/zenpad/discussions)
- Check existing [Issues](https://github.com/jagdishtripathy/zenpad/issues)

**Happy Contributing! 🚀**
