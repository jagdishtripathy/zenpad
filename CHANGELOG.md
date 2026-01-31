# Changelog

All notable changes to Zenpad will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-01-19

### Added
- Binary file detection with hex view for non-text files
- File encoding detection (BOM, UTF-8, Windows-1252, ISO-8859-1)
- Encoding selection submenu with radio buttons
- Line ending selection submenu (Unix LF, Windows CRLF, Mac CR)
- Empty untitled tab replacement when opening files via GUI
- Session management skips empty untitled tabs
- Contributing guide (CONTRIBUTING.md)
- Code of Conduct
- Comprehensive issue templates

### Changed
- Improved setup.py description
- Enhanced README with Quick Start and contributing sections

### Fixed
- Encoding radio button synchronization on tab switch
- GUI file open now replaces empty untitled tabs

## [1.4.0] - 2026-01-15

### Added
- Print functionality with GtkSourceView PrintCompositor
- Ruby language detection patterns
- Expanded language icon mapping (25+ languages)
- GitHub issue templates (bug, feature, enhancement, etc.)
- Pull request template

### Fixed
- Action parameter handling for duplicate/delete line
- Lambda wrapper for menu action callbacks

## [1.3.0] - 2026-01-10

### Added
- Markdown preview panel
- Diff viewer for file comparison
- Auto-pair for brackets and quotes
- Session persistence across restarts

### Changed
- Improved syntax highlighting themes
- Better tab management

## [1.2.0] - 2025-12-20

### Added
- Preferences dialog
- Customizable themes
- Word wrap toggle
- Auto-indent support

## [1.1.0] - 2025-12-01

### Added
- Multi-tab interface
- Search and replace with occurrence counting
- Recent files menu
- Keyboard shortcuts

## [1.0.0] - 2025-11-15

### Added
- Initial release
- GtkSourceView-based text editor
- Syntax highlighting for 100+ languages
- Basic file operations (New, Open, Save, Save As)
- Line numbers and current line highlighting
