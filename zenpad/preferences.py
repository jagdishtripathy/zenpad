import gi
import os
import json
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '4')
from gi.repository import Gtk, GtkSource, Pango, GLib

DEFAULT_SETTINGS = {
    # Editor
    "font": "Monospace 12",
    "word_wrap": True,
    "show_line_numbers": True,
    "highlight_current_line": True,
    
    # Indentation
    "tab_width": 4,
    "use_spaces": True,
    "auto_indent": True,
    
    # Files
    "auto_save": False,
    "auto_save_interval": 5, # minutes
    "restore_session": True,
    "encoding": "UTF-8",
    
    # Appearance
    "theme": "tango",
    "editor_padding": "normal" # small, normal, large
}

class Settings:
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), ".config", "zenpad")
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.data = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

class PreferencesDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Preferences", transient_for=parent, flags=0)
        self.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.parent_window = parent
        self.settings = parent.settings
        
        self.set_default_size(500, 400)
        
        box = self.get_content_area()
        # box.set_spacing(10)
        # box.set_border_width(10)
        
        notebook = Gtk.Notebook()
        box.pack_start(notebook, True, True, 0)
        
        # Editor Tab
        notebook.append_page(self.create_editor_page(), Gtk.Label(label="Editor"))
        
        # Indentation Tab
        notebook.append_page(self.create_indentation_page(), Gtk.Label(label="Indentation"))
        
        # Files Tab
        notebook.append_page(self.create_files_page(), Gtk.Label(label="Files"))
        
        # Appearance Tab
        notebook.append_page(self.create_appearance_page(), Gtk.Label(label="Appearance"))
        
        self.show_all()

    def create_grid(self):
        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(10)
        grid.set_border_width(20)
        return grid

    def create_editor_page(self):
        grid = self.create_grid()
        row = 0
        
        # Font
        grid.attach(Gtk.Label(label="Font:", xalign=0), 0, row, 1, 1)
        font_btn = Gtk.FontButton()
        font_btn.set_font(self.settings.get("font"))
        font_btn.connect("font-set", self.on_font_set)
        grid.attach(font_btn, 1, row, 1, 1)
        row += 1
        
        # Word Wrap
        wrap_chk = Gtk.CheckButton(label="Word Wrap")
        wrap_chk.set_active(self.settings.get("word_wrap"))
        wrap_chk.connect("toggled", self.on_toggle, "word_wrap")
        grid.attach(wrap_chk, 0, row, 2, 1)
        row += 1
        
        # Line Numbers
        ln_chk = Gtk.CheckButton(label="Show Line Numbers")
        ln_chk.set_active(self.settings.get("show_line_numbers"))
        ln_chk.connect("toggled", self.on_toggle, "show_line_numbers")
        grid.attach(ln_chk, 0, row, 2, 1)
        row += 1
        
        # Highlight Current Line
        hl_chk = Gtk.CheckButton(label="Highlight Current Line")
        hl_chk.set_active(self.settings.get("highlight_current_line"))
        hl_chk.connect("toggled", self.on_toggle, "highlight_current_line")
        grid.attach(hl_chk, 0, row, 2, 1)
        row += 1
        
        return grid

    def create_indentation_page(self):
        grid = self.create_grid()
        row = 0
        
        # Tab Width
        grid.attach(Gtk.Label(label="Tab Width:", xalign=0), 0, row, 1, 1)
        tab_combo = Gtk.ComboBoxText()
        for width in ["2", "4", "8"]:
            tab_combo.append(width, width)
        tab_combo.set_active_id(str(self.settings.get("tab_width")))
        tab_combo.connect("changed", self.on_combo_changed, "tab_width")
        grid.attach(tab_combo, 1, row, 1, 1)
        row += 1
        
        # Use Spaces
        spaces_chk = Gtk.CheckButton(label="Insert spaces instead of tabs")
        spaces_chk.set_active(self.settings.get("use_spaces"))
        spaces_chk.connect("toggled", self.on_toggle, "use_spaces")
        grid.attach(spaces_chk, 0, row, 2, 1)
        row += 1
        
        # Auto Indent
        indent_chk = Gtk.CheckButton(label="Enable automatic indentation")
        indent_chk.set_active(self.settings.get("auto_indent"))
        indent_chk.connect("toggled", self.on_toggle, "auto_indent")
        grid.attach(indent_chk, 0, row, 2, 1)
        row += 1
        
        return grid

    def create_files_page(self):
        grid = self.create_grid()
        row = 0
        
        # Auto Save
        auto_save_chk = Gtk.CheckButton(label="Enable Auto-Save")
        auto_save_chk.set_active(self.settings.get("auto_save"))
        auto_save_chk.connect("toggled", self.on_toggle, "auto_save")
        grid.attach(auto_save_chk, 0, row, 2, 1)
        row += 1
        
        # Restore Session
        restore_chk = Gtk.CheckButton(label="Restore last opened files on startup")
        restore_chk.set_active(self.settings.get("restore_session"))
        restore_chk.connect("toggled", self.on_toggle, "restore_session")
        grid.attach(restore_chk, 0, row, 2, 1)
        row += 1
        
        # Encoding
        grid.attach(Gtk.Label(label="Default Encoding:", xalign=0), 0, row, 1, 1)
        enc_combo = Gtk.ComboBoxText()
        for enc in ["UTF-8", "ISO-8859-1", "ASCII"]:
            enc_combo.append(enc, enc)
        enc_combo.set_active_id(self.settings.get("encoding"))
        enc_combo.connect("changed", self.on_combo_changed, "encoding")
        grid.attach(enc_combo, 1, row, 1, 1)
        row += 1
        
        return grid

    def create_appearance_page(self):
        grid = self.create_grid()
        row = 0
        
        # Theme
        grid.attach(Gtk.Label(label="Color Scheme:", xalign=0), 0, row, 1, 1)
        theme_combo = Gtk.ComboBoxText()
        manager = GtkSource.StyleSchemeManager.get_default()
        for scheme_id in sorted(manager.get_scheme_ids()):
            theme_combo.append(scheme_id, scheme_id)
        theme_combo.set_active_id(self.settings.get("theme"))
        theme_combo.connect("changed", self.on_combo_changed, "theme")
        grid.attach(theme_combo, 1, row, 1, 1)
        row += 1
        
        # Editor Padding
        grid.attach(Gtk.Label(label="Editor Padding:", xalign=0), 0, row, 1, 1)
        pad_combo = Gtk.ComboBoxText()
        pad_combo.append("small", "Small (2px)")
        pad_combo.append("normal", "Normal (6px)")
        pad_combo.append("large", "Large (12px)")
        pad_combo.set_active_id(self.settings.get("editor_padding"))
        pad_combo.connect("changed", self.on_combo_changed, "editor_padding")
        grid.attach(pad_combo, 1, row, 1, 1)
        row += 1
        
        return grid

    # -- Signal Handlers --

    def on_toggle(self, widget, key):
        value = widget.get_active()
        self.settings.set(key, value)
        self.parent_window.apply_setting(key, value)

    def on_combo_changed(self, widget, key):
        value = widget.get_active_id()
        if key == "tab_width":
             value = int(value)
        self.settings.set(key, value)
        self.parent_window.apply_setting(key, value)

    def on_font_set(self, widget):
        value = widget.get_font_name()
        self.settings.set("font", value)
        self.parent_window.apply_setting("font", value)
