import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import difflib
import os

class DiffDialog(Gtk.Dialog):
    def __init__(self, parent, current_page_num, tabs_list):
        super().__init__(title="Compare Documents", transient_for=parent, flags=0)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            "Compare", Gtk.ResponseType.OK
        )
        
        self.set_default_size(400, 150)
        self.set_border_width(10)
        
        box = self.get_content_area()
        box.set_spacing(10)
        
        # Label
        lbl = Gtk.Label(label="Select document to compare with current tab:")
        lbl.set_halign(Gtk.Align.START)
        box.add(lbl)
        
        # Combo Box
        self.combo = Gtk.ComboBoxText()
        self.tabs_list = tabs_list
        self.current_idx = current_page_num
        
        active_idx = 0
        valid_count = 0
        
        for idx, title in enumerate(tabs_list):
            if idx == current_page_num:
                continue # Skip self
            
            self.combo.append(str(idx), title)
            valid_count += 1
            
        if valid_count > 0:
            self.combo.set_active(0)
            self.has_options = True
        else:
            self.combo.append("-1", "No other tabs open")
            self.combo.set_active(0)
            self.combo.set_sensitive(False)
            self.has_options = False
            
        box.add(self.combo)
        self.show_all()

    def get_selected_page_index(self):
        if not self.has_options:
            return -1
        active_id = self.combo.get_active_id()
        if active_id:
            return int(active_id)
        return -1

def generate_diff(text_a, text_b, name_a, name_b):
    """
    Generates a unified diff string.
    """
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        lines_a, lines_b,
        fromfile=name_a,
        tofile=name_b,
        lineterm=""
    )
    
    return "".join(diff)
