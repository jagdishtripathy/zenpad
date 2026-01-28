"""
Zenpack API - Sandboxed Interface for Zenpacks

This module provides the ZenpackAPI class which is the ONLY interface
Zenpacks have to interact with Zenpad. Direct access to window internals
is not allowed for security and stability.
"""

import os
import json
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class ZenpackAPI:
    """
    Sandboxed API exposed to Zenpacks.
    
    This class provides controlled access to Zenpad functionality.
    Zenpacks cannot access the window or editor directly - they must
    use this API which enforces permissions and prevents crashes.
    """
    
    def __init__(self, window, zenpack_id: str, permissions: list):
        """
        Initialize the API for a specific Zenpack.
        
        Args:
            window: ZenpadWindow instance (kept private)
            zenpack_id: Unique identifier of the Zenpack
            permissions: List of granted permissions from manifest
        """
        self._window = window
        self._zenpack_id = zenpack_id
        self._permissions = permissions or []
        self._hooks = {}  # hook_name -> [callbacks]
        self._registered_shortcuts = []  # Track for cleanup
    
    # ═══════════════════════════════════════════════════════════════
    # EDITOR OPERATIONS (requires "editor" permission)
    # ═══════════════════════════════════════════════════════════════
    
    def get_current_text(self) -> str:
        """
        Get all text from the current buffer.
        
        Returns:
            str: Complete text content, or empty string if no editor.
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor:
            buf = editor.buffer
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return ""
    
    def insert_text(self, text: str):
        """
        Insert text at the current cursor position.
        
        Args:
            text: Text to insert
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor:
            editor.buffer.insert_at_cursor(text)
    
    def get_selection(self) -> str:
        """
        Get the currently selected text.
        
        Returns:
            str: Selected text, or empty string if no selection.
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor and editor.buffer.get_has_selection():
            start, end = editor.buffer.get_selection_bounds()
            return editor.buffer.get_text(start, end, False)
        return ""
    
    def get_cursor_position(self) -> tuple:
        """
        Get the current cursor position.
        
        Returns:
            tuple: (line, column) - 1-indexed
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor:
            insert = editor.buffer.get_insert()
            iter_pos = editor.buffer.get_iter_at_mark(insert)
            return (iter_pos.get_line() + 1, iter_pos.get_line_offset() + 1)
        return (1, 1)
    
    def get_current_file_path(self) -> str:
        """
        Get the file path of the current tab.
        
        Returns:
            str: File path, or None if untitled.
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        return editor.file_path if editor else None
    
    def get_current_language(self) -> str:
        """
        Get the language ID of the current buffer.
        
        Returns:
            str: Language ID (e.g., "python", "javascript"), or "text".
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor:
            lang = editor.buffer.get_language()
            return lang.get_id() if lang else "text"
        return "text"
    
    def get_line_count(self) -> int:
        """
        Get the number of lines in the current buffer.
        
        Returns:
            int: Line count
        """
        self._require_permission("editor")
        editor = self._get_current_editor()
        if editor:
            return editor.buffer.get_line_count()
        return 0
    
    # ═══════════════════════════════════════════════════════════════
    # UI OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    def show_status(self, message: str):
        """
        Show a message in the status bar (zenpack section).
        
        Args:
            message: Text to display
        
        Requires: "statusbar" permission
        """
        self._require_permission("statusbar")
        # Use dedicated zenpack_label instead of statusbar.push
        # This prevents being overwritten by update_statusbar
        if hasattr(self._window, 'zenpack_label'):
            self._window.zenpack_label.set_text(message)
    
    def clear_status(self):
        """
        Clear the status bar message.
        
        Requires: "statusbar" permission
        """
        self._require_permission("statusbar")
        if hasattr(self._window, 'zenpack_label'):
            self._window.zenpack_label.set_text("")
    
    def show_notification(self, title: str, message: str):
        """
        Show a notification dialog.
        
        Args:
            title: Dialog title
            message: Dialog message
        
        Requires: "notifications" permission
        """
        self._require_permission("notifications")
        dialog = Gtk.MessageDialog(
            transient_for=self._window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def show_error(self, title: str, message: str):
        """
        Show an error dialog.
        
        Requires: "notifications" permission
        """
        self._require_permission("notifications")
        dialog = Gtk.MessageDialog(
            transient_for=self._window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    # ═══════════════════════════════════════════════════════════════
    # HOOK REGISTRATION
    # ═══════════════════════════════════════════════════════════════
    
    def register_hook(self, hook_name: str, callback):
        """
        Register a callback for a Zenpad event.
        
        Available hooks:
            - on_startup: Zenpad starts
            - on_shutdown: Zenpad closes
            - on_file_open: File opened (filepath)
            - on_file_save: File saved (filepath)
            - on_tab_switch: Tab changed (tab_index)
            - on_text_changed: Buffer modified
            - on_cursor_move: Cursor moved (line, col)
        
        Args:
            hook_name: Name of the hook
            callback: Function to call when hook fires
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
    
    def unregister_hook(self, hook_name: str, callback):
        """
        Unregister a previously registered callback.
        """
        if hook_name in self._hooks and callback in self._hooks[hook_name]:
            self._hooks[hook_name].remove(callback)
    
    def get_registered_hooks(self) -> dict:
        """
        Get all hooks registered by this Zenpack.
        
        Returns:
            dict: hook_name -> [callbacks]
        """
        return self._hooks.copy()
    
    # ═══════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    def get_config(self, key: str, default=None):
        """
        Get a configuration value for this Zenpack.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
        
        Returns:
            The configuration value or default
        """
        config_path = os.path.join(self._get_zenpack_dir(), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get(key, default)
            except (json.JSONDecodeError, IOError):
                pass
        return default
    
    def set_config(self, key: str, value):
        """
        Set a configuration value for this Zenpack.
        
        Args:
            key: Configuration key
            value: Value to store (must be JSON-serializable)
        
        Requires: "filesystem_write" permission
        """
        self._require_permission("filesystem_write")
        config_path = os.path.join(self._get_zenpack_dir(), "config.json")
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        config[key] = value
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    # ═══════════════════════════════════════════════════════════════
    # INTERNAL HELPERS (not exposed to Zenpacks)
    # ═══════════════════════════════════════════════════════════════
    
    def _require_permission(self, permission: str):
        """
        Check if the Zenpack has the required permission.
        
        Raises:
            PermissionError: If permission is not granted
        """
        if permission not in self._permissions:
            raise PermissionError(
                f"Zenpack '{self._zenpack_id}' requires '{permission}' permission. "
                f"Add it to manifest.json permissions array."
            )
    
    def _get_current_editor(self):
        """
        Get the currently active EditorTab.
        
        Returns:
            EditorTab or None
        """
        page_num = self._window.notebook.get_current_page()
        if page_num >= 0:
            return self._window.notebook.get_nth_page(page_num)
        return None
    
    def _get_zenpack_dir(self) -> str:
        """
        Get the directory path for this Zenpack.
        
        Returns:
            str: Path to ~/.config/zenpad/zenpacks/<zenpack_id>/
        """
        return os.path.join(
            os.path.expanduser("~/.config/zenpad/zenpacks"),
            self._zenpack_id
        )
    
    def _call_hooks(self, hook_name: str, *args):
        """
        Call all registered callbacks for a hook.
        
        This is called by ZenpackManager, not by Zenpacks themselves.
        """
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    callback(*args)
                except Exception as e:
                    print(f"[Zenpack:{self._zenpack_id}] Hook '{hook_name}' error: {e}")
