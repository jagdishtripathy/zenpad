"""
Session Manager for Zenpad.
Handles saving and restoring editor sessions across application restarts.
"""
import os
import json
from typing import Optional, Dict, Any, List


class SessionManager:
    """Manages session persistence for Zenpad."""
    
    def __init__(self, config_dir: str):
        """
        Initialize SessionManager.
        
        Args:
            config_dir: Path to Zenpad config directory (~/.config/zenpad)
        """
        self.config_dir = config_dir
        self.session_file = os.path.join(config_dir, "session.json")
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
    
    def save(self, window) -> bool:
        """
        Save current session state to disk.
        
        Args:
            window: ZenpadWindow instance
            
        Returns:
            True if session was saved successfully
        """
        try:
            session_data = {
                "window": {
                    "width": window.get_size()[0],
                    "height": window.get_size()[1],
                    "maximized": window.is_maximized()
                },
                "active_tab": window.notebook.get_current_page(),
                "tabs": []
            }
            
            # Collect tab data
            n_pages = window.notebook.get_n_pages()
            for i in range(n_pages):
                editor = window.notebook.get_nth_page(i)
                tab_data = self._get_tab_data(editor)
                session_data["tabs"].append(tab_data)
            
            # Write to file
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"[Session] Error saving session: {e}")
            return False
    
    def _get_tab_data(self, editor) -> Dict[str, Any]:
        """Extract session data from an editor tab."""
        buff = editor.buffer
        
        # Get cursor position
        cursor_iter = buff.get_iter_at_mark(buff.get_insert())
        cursor_line = cursor_iter.get_line()
        cursor_column = cursor_iter.get_line_offset()
        
        # Get scroll position (approximate via cursor visibility)
        # GtkSourceView doesn't expose scroll position directly
        
        tab_data = {
            "file_path": editor.file_path,
            "modified": buff.get_modified(),
            "cursor_line": cursor_line,
            "cursor_column": cursor_column
        }
        
        # For unsaved/modified tabs, store content
        if not editor.file_path or buff.get_modified():
            start, end = buff.get_bounds()
            tab_data["content"] = buff.get_text(start, end, True)
        
        return tab_data
    
    def has_unsaved_data(self) -> bool:
        """Check if session file contains any unsaved/modified data."""
        if not os.path.exists(self.session_file):
            return False
        
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            tabs = session_data.get("tabs", [])
            for tab in tabs:
                # Unsaved tab (no file path) with content
                if not tab.get("file_path") and tab.get("content"):
                    return True
                # Modified tab with content
                if tab.get("modified") and tab.get("content"):
                    return True
            return False
        except:
            return False
    
    def restore(self, window, ask_user: bool = True) -> bool:
        """
        Restore session from disk.
        
        Args:
            window: ZenpadWindow instance
            ask_user: If True and session has unsaved data, ask user before restoring
            
        Returns:
            True if session was restored successfully
        """
        if not os.path.exists(self.session_file):
            return False
        
        try:
            # Check if we need to ask user
            if ask_user and self.has_unsaved_data():
                from gi.repository import Gtk
                
                dialog = Gtk.MessageDialog(
                    transient_for=window,
                    modal=True,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text="Restore previous session?"
                )
                dialog.format_secondary_text(
                    "It seems that the previous session did not end normally. "
                    "Do you want to restore the available data?\n\n"
                    "If not, all unsaved data will be lost."
                )
                response = dialog.run()
                dialog.destroy()
                
                if response != Gtk.ResponseType.YES:
                    # User declined, clear session file
                    self.clear()
                    return False
            
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            # Restore window size
            if "window" in session_data:
                win_data = session_data["window"]
                window.set_default_size(
                    win_data.get("width", 800),
                    win_data.get("height", 600)
                )
                if win_data.get("maximized", False):
                    window.maximize()
            
            # Restore tabs
            tabs = session_data.get("tabs", [])
            if not tabs:
                return False
            
            # Close the default empty tab if we're restoring
            if window.notebook.get_n_pages() == 1:
                first_editor = window.notebook.get_nth_page(0)
                if not first_editor.file_path and not first_editor.buffer.get_modified():
                    window.notebook.remove_page(0)
            
            for tab_data in tabs:
                self._restore_tab(window, tab_data)
            
            # Restore active tab
            active_tab = session_data.get("active_tab", 0)
            if 0 <= active_tab < window.notebook.get_n_pages():
                window.notebook.set_current_page(active_tab)
            
            return True
            
        except Exception as e:
            print(f"[Session] Error restoring session: {e}")
            return False
    
    def _restore_tab(self, window, tab_data: Dict[str, Any]) -> None:
        """Restore a single tab from session data."""
        file_path = tab_data.get("file_path")
        
        if file_path and os.path.exists(file_path):
            # Restore saved file
            window.open_file(file_path)
        else:
            # Restore unsaved/new tab
            window.on_new_tab(None)
            
            # Get the newly created tab
            page_num = window.notebook.get_n_pages() - 1
            editor = window.notebook.get_nth_page(page_num)
            
            # Set content if available
            if "content" in tab_data:
                editor.set_text(tab_data["content"])
                editor.buffer.set_modified(tab_data.get("modified", True))
        
        # Restore cursor position
        page_num = window.notebook.get_n_pages() - 1
        editor = window.notebook.get_nth_page(page_num)
        
        cursor_line = tab_data.get("cursor_line", 0)
        cursor_column = tab_data.get("cursor_column", 0)
        
        # Move cursor to saved position
        buff = editor.buffer
        try:
            target_iter = buff.get_iter_at_line_offset(cursor_line, cursor_column)
            buff.place_cursor(target_iter)
            # Scroll to cursor
            editor.view.scroll_to_mark(buff.get_insert(), 0.2, False, 0, 0)
        except:
            pass  # Ignore if position is invalid
    
    def clear(self) -> None:
        """Remove session file."""
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except:
                pass
