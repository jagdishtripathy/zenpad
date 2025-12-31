import gi
import hashlib
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('GtkSource', '4')
except ValueError:
    gi.require_version('GtkSource', '3.0')
from gi.repository import Gtk, GtkSource, Pango, Gdk

class EditorTab(Gtk.ScrolledWindow):
    def __init__(self, search_settings=None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.buffer = GtkSource.Buffer()
        self.last_buffer = None
        self.view = GtkSource.View.new_with_buffer(self.buffer)
        
        self.file_path = None
        
        # Search Context
        self.search_context = None
        if search_settings:
            self.search_context = GtkSource.SearchContext.new(self.buffer, search_settings)
            self.search_context.set_highlight(True)
        
        # Default Settings
        self.view.set_show_line_numbers(True)
        self.view.set_auto_indent(True)
        self.view.set_highlight_current_line(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.set_left_margin(6)
        self.view.set_right_margin(6)
        
        # Load Default Theme
        self.set_scheme("tango")

        # Font (Default Monospace)
        self.font_desc = Pango.FontDescription("Monospace 12")
        self.view.modify_font(self.font_desc)
        
        # Handle scrolling (for zoom-in-out)
        self.view.connect('scroll-event', self.on_scroll)

        self.add(self.view)
        self.show_all()

    def zoom_in(self):
        size = self.font_desc.get_size()
        # Pango size is in pango units (scaled by PANGO_SCALE usually, but string init might be different)
        # If initialized from string "12", get_size() returns 12 * PANGO_SCALE.
        
        # However, checking behavior:
        # If I set Absolute size, it might be different.
        # Let's assume standard Pango unit handling.
        
        new_size = size + (2 * Pango.SCALE)
        self.font_desc.set_size(new_size)
        self.view.modify_font(self.font_desc)

    def zoom_out(self):
        size = self.font_desc.get_size()
        new_size = size - (2 * Pango.SCALE)
        if new_size >= (6 * Pango.SCALE): # Minimum size 6
            self.font_desc.set_size(new_size)
            self.view.modify_font(self.font_desc)

    def zoom_reset(self):
        self.font_desc.set_size(12 * Pango.SCALE)
        self.view.modify_font(self.font_desc)

    def get_text(self):
        start_iter = self.buffer.get_start_iter()
        end_iter = self.buffer.get_end_iter()
        return self.buffer.get_text(start_iter, end_iter, True)

    def set_text(self, text):
        self.buffer.set_text(text)

    def set_scheme(self, scheme_id):
        manager = GtkSource.StyleSchemeManager.get_default()
        scheme = manager.get_scheme(scheme_id)
        if scheme:
            self.buffer.set_style_scheme(scheme)

    def get_cursor_position(self):
        insert = self.buffer.get_insert()
        iter = self.buffer.get_iter_at_mark(insert)
        line = iter.get_line() + 1
        col = iter.get_line_offset() + 1
        return line, col

    def detect_language(self, filename):
        manager = GtkSource.LanguageManager.get_default()
        language = manager.guess_language(filename, None)
        if language:
            self.buffer.set_language(language)

    def on_scroll(self, gpointer, event):
        if (not event.state == Gdk.ModifierType.CONTROL_MASK):
            return False

        good, dx, dy = event.get_scroll_deltas()

        if (dy < 0.0):
            self.zoom_in()
        elif (dy > 0.0):
            self.zoom_out()

        return True
