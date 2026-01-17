from gi.repository import Gtk, Gdk, Gio, GLib, Pango
import hashlib
import os
import json
from .editor import EditorTab
from zenpad import analysis  # New Analysis Module
try:
    from zenpad import markdown_preview
except (ImportError, ValueError):
    markdown_preview = None
from zenpad import diff_viewer # Diff Module
from zenpad.preferences import PreferencesDialog, Settings
from zenpad.session import SessionManager
from zenpad import file_utils  # Binary detection and encoding
from gi.repository import GtkSource
from gi.repository import Pango

class ZenpadWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Zenpad")
        self.set_default_size(800, 600)
        self.connect("delete-event", self.save_session)
        
        # Accelerator Group
        self.accel_group = Gtk.AccelGroup()
        self.add_accel_group(self.accel_group)
        
        # 0. Header Bar (For Window Controls Only - CSD)
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = "Zenpad"
        header.props.decoration_layout = ":minimize,maximize,close"
        self.set_titlebar(header)
        
        # Main Layout Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)

        # Core Components
        self.settings = Settings()
        
        # State
        self.search_settings = GtkSource.SearchSettings()
        self.search_context = None
        self.incremental_search = True
        self.highlight_all = True
        
        # History
        self.closed_tabs = []
        
        # View State (Loaded from Settings)
        self.show_line_numbers = self.settings.get("show_line_numbers")
        self.show_menubar = True
        self.show_toolbar = True
        self.show_statusbar = True
        self.is_fullscreen = False
        
        # Document State (Loaded from Settings)
        self.doc_word_wrap = self.settings.get("word_wrap")
        self.doc_auto_indent = self.settings.get("auto_indent")
        self.doc_tab_size = self.settings.get("tab_width")
        self.doc_use_spaces = self.settings.get("use_spaces")
        self.doc_write_bom = False
        self.doc_viewer_mode = False
        self.doc_line_ending = "Current"
        
        # 1. Menu Bar

        # 1. Menu Bar
        self.menubar = self.create_menubar()
        main_box.pack_start(self.menubar, False, False, 0)
        
        # 2. Toolbar
        self.toolbar = self.create_toolbar()
        main_box.pack_start(self.toolbar, False, False, 0)

        # 3. Notebook (content)
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect("switch-page", self.on_tab_switched)
        main_box.pack_start(self.notebook, True, True, 0)
        
        self.search_settings = GtkSource.SearchSettings()
        self.search_bar_revealer = Gtk.Revealer()
        self.search_bar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.create_search_bar()
        main_box.pack_start(self.search_bar_revealer, False, False, 0)

        # 4. Status Bar
        self.statusbar = Gtk.Statusbar()
        # Add Language Indicator Label
        self.language_label = Gtk.Label(label="Plain Text")
        self.language_label.set_margin_end(10)
        # Pack at END of the box (GtkStatusbar is a GtkBox)
        # Note: Gtk.Statusbar structure usually has a message_area (first child).
        # We can pack_end to push it to the right corner.
        self.statusbar.pack_end(self.language_label, False, False, 0)
        main_box.pack_end(self.statusbar, False, True, 0)
        
        # Shortcuts
        self.create_actions()
        
        # Track current signal handler to disconnect later
        self.current_cursor_handler = None
        self.md_window = None
        
        # Session Manager
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "zenpad")
        self.session_manager = SessionManager(config_dir)
        
        # Load Session or Add initial empty tab
        # Skip if files are being opened via command line
        has_pending_files = hasattr(self.get_application(), 'pending_files') and self.get_application().pending_files
        
        if not has_pending_files:
            if self.settings.get("restore_session"):
                if not self.session_manager.restore(self):
                    self.add_tab()  # Fallback to empty tab
            else:
                self.add_tab()
        
        self.show_all()

    def create_menubar(self):
        menubar = Gtk.MenuBar()
        
        # File Menu
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="File")
        file_item.set_submenu(file_menu)
        
        new_item = Gtk.ImageMenuItem(label="New")
        new_item.set_image(Gtk.Image.new_from_icon_name("document-new", Gtk.IconSize.MENU))
        new_item.set_always_show_image(True)
        new_item.connect("activate", self.on_new_tab)
        new_item.add_accelerator("activate", self.accel_group, Gdk.KEY_n, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(new_item)

        new_window_item = Gtk.ImageMenuItem(label="New Window")
        new_window_item.set_image(Gtk.Image.new_from_icon_name("window-new", Gtk.IconSize.MENU))
        new_window_item.set_always_show_image(True)
        new_window_item.connect("activate", self.on_new_window)
        new_window_item.add_accelerator("activate", self.accel_group, Gdk.KEY_n, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(new_window_item)
        
        # Open
        open_item = Gtk.ImageMenuItem(label="Open...")
        open_item.set_image(Gtk.Image.new_from_icon_name("document-open", Gtk.IconSize.MENU))
        open_item.set_always_show_image(True)
        open_item.connect("activate", self.on_open_file)
        open_item.add_accelerator("activate", self.accel_group, Gdk.KEY_o, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(open_item)
        
        # Recent Files (limited to 4 for cleaner menu)
        recent_item = Gtk.MenuItem(label="Open Recent")
        recent_menu = Gtk.RecentChooserMenu()
        recent_menu.set_limit(4)
        recent_menu.set_show_not_found(False)
        recent_menu.set_sort_type(Gtk.RecentSortType.MRU)  # Most Recently Used first
        recent_menu.connect("item-activated", self.on_open_recent)
        recent_item.set_submenu(recent_menu)
        file_menu.append(recent_item)
        
        file_menu.append(Gtk.SeparatorMenuItem())
        
        # Save
        save_item = Gtk.ImageMenuItem(label="Save")
        save_item.set_image(Gtk.Image.new_from_icon_name("document-save", Gtk.IconSize.MENU))
        save_item.set_always_show_image(True)
        save_item.connect("activate", self.on_save_file)
        save_item.add_accelerator("activate", self.accel_group, Gdk.KEY_s, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(save_item)
        
        save_as_item = Gtk.ImageMenuItem(label="Save As...")
        save_as_item.set_image(Gtk.Image.new_from_icon_name("document-save-as", Gtk.IconSize.MENU))
        save_as_item.set_always_show_image(True)
        save_as_item.connect("activate", self.on_save_as)
        save_as_item.add_accelerator("activate", self.accel_group, Gdk.KEY_s, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(save_as_item)

        save_all_item = Gtk.ImageMenuItem(label="Save All")
        save_all_item.set_image(Gtk.Image.new_from_icon_name("document-save-all", Gtk.IconSize.MENU))
        save_all_item.set_always_show_image(True)
        save_all_item.connect("activate", self.on_save_all)
        save_all_item.add_accelerator("activate", self.accel_group, Gdk.KEY_s, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(save_all_item)
        
        file_menu.append(Gtk.SeparatorMenuItem())
        
        # Reload
        reload_item = Gtk.ImageMenuItem(label="Reload")
        reload_item.set_image(Gtk.Image.new_from_icon_name("view-refresh", Gtk.IconSize.MENU))
        reload_item.set_always_show_image(True)
        reload_item.connect("activate", self.on_reload)
        reload_item.add_accelerator("activate", self.accel_group, Gdk.KEY_r, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(reload_item)
        
        file_menu.append(Gtk.SeparatorMenuItem())

        # Print
        print_item = Gtk.ImageMenuItem(label="Print...")
        print_item.set_image(Gtk.Image.new_from_icon_name("document-print", Gtk.IconSize.MENU))
        print_item.set_always_show_image(True)
        print_item.connect("activate", self.on_print)
        print_item.add_accelerator("activate", self.accel_group, Gdk.KEY_p, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(print_item)
        
        file_menu.append(Gtk.SeparatorMenuItem())

        # Detach Tab
        detach_item = Gtk.MenuItem(label="Detach Tab")
        detach_item.connect("activate", self.on_detach_tab)
        file_menu.append(detach_item)
        
        # Reopen Closed Tab
        reopen_item = Gtk.MenuItem(label="Reopen Closed Tab")
        reopen_item.connect("activate", self.on_reopen_tab)
        reopen_item.add_accelerator("activate", self.accel_group, Gdk.KEY_t, Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(reopen_item)
        
        # Close Tab
        close_tab_item = Gtk.ImageMenuItem(label="Close Tab")
        close_tab_item.set_image(Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.MENU))
        close_tab_item.set_always_show_image(True)
        close_tab_item.connect("activate", self.on_close_current_tab)
        close_tab_item.add_accelerator("activate", self.accel_group, Gdk.KEY_w, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(close_tab_item)
        
        # Close Window
        close_win_item = Gtk.MenuItem(label="Close Window")
        close_win_item.connect("activate", lambda w: self.close())
        file_menu.append(close_win_item)
        
        quit_item = Gtk.ImageMenuItem(label="Quit")
        quit_item.set_image(Gtk.Image.new_from_icon_name("application-exit", Gtk.IconSize.MENU))
        quit_item.set_always_show_image(True)
        quit_item.connect("activate", lambda w: self.close()) # Quit app?
        quit_item.add_accelerator("activate", self.accel_group, Gdk.KEY_q, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        file_menu.append(quit_item)
        
        menubar.append(file_item)
        
        # Edit Menu
        edit_menu = Gtk.Menu()
        edit_item = Gtk.MenuItem(label="Edit")
        edit_item.set_submenu(edit_menu)

        # Undo/Redo
        undo_item = Gtk.ImageMenuItem(label="Undo")
        undo_item.set_image(Gtk.Image.new_from_icon_name("edit-undo", Gtk.IconSize.MENU))
        undo_item.set_always_show_image(True)
        undo_item.connect("activate", self.on_undo)
        undo_item.add_accelerator("activate", self.accel_group, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(undo_item)

        redo_item = Gtk.ImageMenuItem(label="Redo")
        redo_item.set_image(Gtk.Image.new_from_icon_name("edit-redo", Gtk.IconSize.MENU))
        redo_item.set_always_show_image(True)
        redo_item.connect("activate", self.on_redo)
        redo_item.add_accelerator("activate", self.accel_group, Gdk.KEY_y, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(redo_item)

        edit_menu.append(Gtk.SeparatorMenuItem())

        # Cut/Copy/Paste
        cut_item = Gtk.ImageMenuItem(label="Cut")
        cut_item.set_image(Gtk.Image.new_from_icon_name("edit-cut", Gtk.IconSize.MENU))
        cut_item.set_always_show_image(True)
        cut_item.connect("activate", self.on_cut)
        cut_item.add_accelerator("activate", self.accel_group, Gdk.KEY_x, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(cut_item)

        copy_item = Gtk.ImageMenuItem(label="Copy")
        copy_item.set_image(Gtk.Image.new_from_icon_name("edit-copy", Gtk.IconSize.MENU))
        copy_item.set_always_show_image(True)
        copy_item.connect("activate", self.on_copy)
        copy_item.add_accelerator("activate", self.accel_group, Gdk.KEY_c, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(copy_item)
        
        paste_item = Gtk.ImageMenuItem(label="Paste")
        paste_item.set_image(Gtk.Image.new_from_icon_name("edit-paste", Gtk.IconSize.MENU))
        paste_item.set_always_show_image(True)
        paste_item.connect("activate", self.on_paste)
        paste_item.add_accelerator("activate", self.accel_group, Gdk.KEY_v, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(paste_item)

        # Delete Selection/Line
        del_item = Gtk.MenuItem(label="Delete Selection")
        del_item.connect("activate", self.on_delete_selection)
        del_item.add_accelerator("activate", self.accel_group, Gdk.KEY_Delete, 0, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(del_item)

        del_line_item = Gtk.MenuItem(label="Delete Line")
        del_line_item.connect("activate", self.on_delete_line)
        del_line_item.add_accelerator("activate", self.accel_group, Gdk.KEY_k, Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(del_line_item)

        edit_menu.append(Gtk.SeparatorMenuItem())

        # Select All
        sel_all_item = Gtk.ImageMenuItem(label="Select All")
        sel_all_item.set_image(Gtk.Image.new_from_icon_name("edit-select-all", Gtk.IconSize.MENU))
        sel_all_item.set_always_show_image(True)
        sel_all_item.connect("activate", self.on_select_all)
        sel_all_item.add_accelerator("activate", self.accel_group, Gdk.KEY_a, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(sel_all_item)

        # Convert
        convert_item = Gtk.MenuItem(label="Convert")
        convert_menu = Gtk.Menu()
        convert_item.set_submenu(convert_menu)
        
        to_upper = Gtk.MenuItem(label="To Uppercase")
        to_upper.connect("activate", lambda w: self.on_change_case("upper"))
        to_upper.add_accelerator("activate", self.accel_group, Gdk.KEY_u, Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        convert_menu.append(to_upper)
        
        to_lower = Gtk.MenuItem(label="To Lowercase")
        to_lower.connect("activate", lambda w: self.on_change_case("lower"))
        to_lower.add_accelerator("activate", self.accel_group, Gdk.KEY_l, Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        convert_menu.append(to_lower)
        
        to_title = Gtk.MenuItem(label="To Title Case")
        to_title.connect("activate", lambda w: self.on_change_case("title"))
        convert_menu.append(to_title)

        edit_menu.append(convert_item)

        # Move
        move_item = Gtk.MenuItem(label="Move")
        move_menu = Gtk.Menu()
        move_item.set_submenu(move_menu)

        move_up = Gtk.MenuItem(label="Line Up")
        move_up.connect("activate", lambda w: self.on_move_line("up"))
        move_up.add_accelerator("activate", self.accel_group, Gdk.KEY_Up, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE) 
        move_menu.append(move_up)

        move_down = Gtk.MenuItem(label="Line Down")
        move_down.connect("activate", lambda w: self.on_move_line("down"))
        move_down.add_accelerator("activate", self.accel_group, Gdk.KEY_Down, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE) 
        move_menu.append(move_down)
        
        edit_menu.append(move_item)

        # Duplicate
        dup_item = Gtk.MenuItem(label="Duplicate Line / Selection")
        dup_item.connect("activate", self.on_duplicate)
        dup_item.add_accelerator("activate", self.accel_group, Gdk.KEY_d, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(dup_item)

        # Indent
        indent_inc = Gtk.MenuItem(label="Increase Indent")
        indent_inc.connect("activate", lambda w: self.on_indent(True))
        indent_inc.add_accelerator("activate", self.accel_group, Gdk.KEY_i, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(indent_inc)

        indent_dec = Gtk.MenuItem(label="Decrease Indent")
        indent_dec.connect("activate", lambda w: self.on_indent(False))
        indent_dec.add_accelerator("activate", self.accel_group, Gdk.KEY_u, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(indent_dec)
        
        edit_menu.append(Gtk.SeparatorMenuItem())
        
        # Sort Lines
        sort_item = Gtk.MenuItem(label="Sort Lines")
        sort_item.connect("activate", self.on_sort_lines)
        edit_menu.append(sort_item)
        
        # Join Lines
        join_item = Gtk.MenuItem(label="Join Lines")
        join_item.connect("activate", self.on_join_lines)
        join_item.add_accelerator("activate", self.accel_group, Gdk.KEY_j, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(join_item)
        
        # Toggle Comment
        comment_item = Gtk.MenuItem(label="Toggle Comment")
        comment_item.connect("activate", self.on_toggle_comment)
        comment_item.add_accelerator("activate", self.accel_group, Gdk.KEY_slash, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(comment_item)
        
        # Trim Trailing Whitespace
        trim_item = Gtk.MenuItem(label="Trim Trailing Whitespace")
        trim_item.connect("activate", self.on_trim_whitespace)
        edit_menu.append(trim_item)
        
        edit_menu.append(Gtk.SeparatorMenuItem())
        
        # Insert Date/Time
        date_item = Gtk.MenuItem(label="Insert Date/Time")
        date_item.connect("activate", self.on_insert_date)
        date_item.add_accelerator("activate", self.accel_group, Gdk.KEY_F5, 0, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(date_item)

        edit_menu.append(Gtk.SeparatorMenuItem())
        
        pref_item = Gtk.ImageMenuItem(label="Preferences...")
        pref_item.set_image(Gtk.Image.new_from_icon_name("preferences-system", Gtk.IconSize.MENU))
        pref_item.set_always_show_image(True)
        pref_item = Gtk.ImageMenuItem(label="Preferences...")
        pref_item.set_image(Gtk.Image.new_from_icon_name("preferences-system", Gtk.IconSize.MENU))
        pref_item.set_always_show_image(True)
        pref_item.connect("activate", self.on_preferences_clicked)
        pref_item.add_accelerator("activate", self.accel_group, Gdk.KEY_comma, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        edit_menu.append(pref_item)
        
        menubar.append(edit_item)
        
        # Search Menu
        search_menu = Gtk.Menu()
        search_item = Gtk.MenuItem(label="Search")
        search_item.set_submenu(search_menu)
        
        # Find
        find_item = Gtk.ImageMenuItem(label="Find")
        find_item.set_image(Gtk.Image.new_from_icon_name("edit-find", Gtk.IconSize.MENU))
        find_item.set_always_show_image(True)
        find_item.connect("activate", lambda w: self.on_find_clicked("find"))
        find_item.add_accelerator("activate", self.accel_group, Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        search_menu.append(find_item)

        # Find Next
        find_next_item = Gtk.MenuItem(label="Find Next")
        find_next_item.connect("activate", self.on_search_next)
        find_next_item.add_accelerator("activate", self.accel_group, Gdk.KEY_g, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        search_menu.append(find_next_item)

        # Find Previous
        find_prev_item = Gtk.MenuItem(label="Find Previous")
        find_prev_item.connect("activate", self.on_search_prev)
        find_prev_item.add_accelerator("activate", self.accel_group, Gdk.KEY_g, Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        search_menu.append(find_prev_item)

        # Find and Replace
        replace_item = Gtk.ImageMenuItem(label="Find and Replace...")
        replace_item.set_image(Gtk.Image.new_from_icon_name("edit-find-replace", Gtk.IconSize.MENU))
        replace_item.set_always_show_image(True)
        replace_item.connect("activate", lambda w: self.on_find_clicked("replace"))
        replace_item.add_accelerator("activate", self.accel_group, Gdk.KEY_r, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        search_menu.append(replace_item)
        
        search_menu.append(Gtk.SeparatorMenuItem())
        
        # Incremental Search
        self.inc_search_item = Gtk.CheckMenuItem(label="Incremental Search")
        self.inc_search_item.set_active(self.incremental_search)
        self.inc_search_item.connect("toggled", self.on_toggle_incremental)
        search_menu.append(self.inc_search_item)
        
        # Highlight All
        self.highlight_item = Gtk.CheckMenuItem(label="Highlight All")
        self.highlight_item.set_active(self.highlight_all)
        self.highlight_item.connect("toggled", self.on_toggle_highlight)
        search_menu.append(self.highlight_item)
        
        search_menu.append(Gtk.SeparatorMenuItem())
        
        # Go to
        goto_item = Gtk.MenuItem(label="Go to...")
        goto_item.connect("activate", self.on_goto_line)
        goto_item.add_accelerator("activate", self.accel_group, Gdk.KEY_l, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        search_menu.append(goto_item)
        
        menubar.append(search_item)
        
        # View Menu
        view_menu = Gtk.Menu()
        view_item = Gtk.MenuItem(label="View")
        view_item.set_submenu(view_menu)
        
        # Select Font
        font_item = Gtk.ImageMenuItem(label="Select Font...")
        font_item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-font", Gtk.IconSize.MENU))
        font_item.set_always_show_image(True)
        font_item.connect("activate", self.on_select_font)
        view_menu.append(font_item)
        
        # Color Scheme Submenu
        scheme_item = Gtk.MenuItem(label="Color Scheme")
        scheme_menu = Gtk.Menu()
        scheme_item.set_submenu(scheme_menu)
        
        # Populate schemes
        manager = GtkSource.StyleSchemeManager.get_default()
        schemes = manager.get_scheme_ids()
        # Sort for niceness, maybe prioritize Tango/Classic?
        # Just listing them
        group = None
        for scheme_id in sorted(schemes):
            if group is None:
                item = Gtk.RadioMenuItem(label=scheme_id)
                group = item
            else:
                item = Gtk.RadioMenuItem(label=scheme_id, group=group)

            if self.settings.get("theme") == item.get_label():
                item.set_active(True)
            
            item.connect("activate", self.on_change_scheme, scheme_id)
            scheme_menu.append(item)
            
        view_menu.append(scheme_item)
        
        view_menu.append(Gtk.SeparatorMenuItem())
        
        # Line Numbers
        line_num_item = Gtk.CheckMenuItem(label="Line Numbers")
        line_num_item.set_active(self.show_line_numbers)
        line_num_item.connect("toggled", self.on_toggle_line_numbers)
        view_menu.append(line_num_item)
        
        # Menubar
        self.menubar_chk = Gtk.CheckMenuItem(label="Menubar")
        self.menubar_chk.set_action_name("win.toggle_menubar")
        view_menu.append(self.menubar_chk)
        
        # Toolbar
        self.toolbar_chk = Gtk.CheckMenuItem(label="Toolbar")
        self.toolbar_chk.set_action_name("win.toggle_toolbar")
        view_menu.append(self.toolbar_chk)
        
        # Statusbar
        self.statusbar_chk = Gtk.CheckMenuItem(label="Statusbar")
        self.statusbar_chk.set_action_name("win.toggle_statusbar")
        view_menu.append(self.statusbar_chk)
        
        view_menu.append(Gtk.SeparatorMenuItem())
        
        # Fullscreen
        fs_item = Gtk.CheckMenuItem(label="Fullscreen")
        fs_item.set_action_name("win.toggle_fullscreen")
        view_menu.append(fs_item)
        
        view_menu.append(Gtk.SeparatorMenuItem())

        zoom_in_item = Gtk.ImageMenuItem(label="Zoom In")
        zoom_in_item.set_image(Gtk.Image.new_from_icon_name("zoom-in", Gtk.IconSize.MENU))
        zoom_in_item.set_always_show_image(True)
        zoom_in_item.connect("activate", self.on_zoom_in)
        zoom_in_item.add_accelerator("activate", self.accel_group, Gdk.KEY_plus, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        view_menu.append(zoom_in_item)

        zoom_out_item = Gtk.ImageMenuItem(label="Zoom Out")
        zoom_out_item.set_image(Gtk.Image.new_from_icon_name("zoom-out", Gtk.IconSize.MENU))
        zoom_out_item.set_always_show_image(True)
        zoom_out_item.connect("activate", self.on_zoom_out)
        zoom_out_item.add_accelerator("activate", self.accel_group, Gdk.KEY_minus, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        view_menu.append(zoom_out_item)
        
        zoom_reset_item = Gtk.ImageMenuItem(label="Reset Zoom")
        zoom_reset_item.set_image(Gtk.Image.new_from_icon_name("zoom-original", Gtk.IconSize.MENU))
        zoom_reset_item.set_always_show_image(True)
        zoom_reset_item.connect("activate", self.on_zoom_reset)
        zoom_reset_item.add_accelerator("activate", self.accel_group, Gdk.KEY_0, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        view_menu.append(zoom_reset_item)
        
        menubar.append(view_item)

        # Document Menu
        doc_menu = Gtk.Menu()
        doc_item = Gtk.MenuItem(label="Document")
        doc_item.set_submenu(doc_menu)
        
        # Word Wrap
        self.wrap_chk = Gtk.CheckMenuItem(label="Word Wrap")
        self.wrap_chk.set_active(self.doc_word_wrap)
        self.wrap_chk.connect("toggled", self.on_toggle_word_wrap)
        doc_menu.append(self.wrap_chk)
        
        # Auto Indent
        self.indent_chk = Gtk.CheckMenuItem(label="Auto Indent")
        self.indent_chk.set_active(self.doc_auto_indent)
        self.indent_chk.connect("toggled", self.on_toggle_auto_indent)
        doc_menu.append(self.indent_chk)
        
        # Tab Size Submenu
        tab_size_item = Gtk.MenuItem(label="Tab Size")
        tab_size_menu = Gtk.Menu()
        tab_size_item.set_submenu(tab_size_menu)
        
        group = None
        for size in [2, 4, 8]:
             if group is None:
                 item = Gtk.RadioMenuItem(label=str(size))
                 group = item
             else:
                 item = Gtk.RadioMenuItem(label=str(size), group=group)

             if size == self.doc_tab_size:
                 item.set_active(True)
             item.connect("activate", self.on_change_tab_size, size)
             tab_size_menu.append(item)
        doc_menu.append(tab_size_item)
        
        # Filetype Submenu (Simplified)
        filetype_item = Gtk.MenuItem(label="Filetype")
        filetype_menu = Gtk.Menu()
        filetype_item.set_submenu(filetype_menu)
        
        # Common languages
        common_langs = ["Plain Text", "Python", "C", "C++", "Java", "JavaScript", "HTML", "CSS", "Markdown"]
        for lang in common_langs:
             item = Gtk.MenuItem(label=lang)
             item.connect("activate", self.on_change_filetype, lang)
             filetype_menu.append(item)
        doc_menu.append(filetype_item)

        # Line Ending Submenu
        le_item = Gtk.MenuItem(label="Line Ending")
        le_menu = Gtk.Menu()
        le_item.set_submenu(le_menu)
        
        for le, label in [("\n", "Unix (LF)"), ("\r\n", "Windows (CRLF)"), ("\r", "Mac (CR)")]:
             item = Gtk.MenuItem(label=label)
             item.connect("activate", self.on_change_line_ending, le)
             le_menu.append(item)
        doc_menu.append(le_item)
        
        # Encoding Submenu
        enc_item = Gtk.MenuItem(label="Encoding")
        enc_menu = Gtk.Menu()
        enc_item.set_submenu(enc_menu)
        
        self.encoding_items = {}  # Store radio items for updating
        encodings = [
            ("UTF-8", "UTF-8 (Default)"),
            ("ISO-8859-1", "ISO-8859-1 (Latin-1)"),
            ("ISO-8859-15", "ISO-8859-15 (Latin-9)"),
            ("Windows-1252", "Windows-1252 (Western)"),
            ("UTF-16", "UTF-16"),
            ("ASCII", "ASCII"),
        ]
        group = None
        self._updating_encoding_radio = True  # Block handler during creation
        for enc, label in encodings:
            if group is None:
                item = Gtk.RadioMenuItem(label=label)
                group = item
            else:
                item = Gtk.RadioMenuItem(label=label, group=group)
            item.connect("activate", self.on_change_encoding, enc)
            enc_menu.append(item)
            self.encoding_items[enc] = item
        # Set UTF-8 as default after all items created
        self.encoding_items["UTF-8"].set_active(True)
        self._updating_encoding_radio = False
        
        # Update radio selection when menu is shown
        enc_menu.connect("show", self.on_encoding_menu_show)
        doc_menu.append(enc_item)
        
        # Unicode BOM
        self.bom_chk = Gtk.CheckMenuItem(label="Write Unicode BOM")
        self.bom_chk.set_active(self.doc_write_bom)
        self.bom_chk.connect("toggled", self.on_toggle_bom)
        doc_menu.append(self.bom_chk)
        
        # Viewer Mode
        self.viewmode_chk = Gtk.CheckMenuItem(label="Viewer Mode")
        self.viewmode_chk.set_active(self.doc_viewer_mode)
        self.viewmode_chk.connect("toggled", self.on_toggle_viewer_mode)
        doc_menu.append(self.viewmode_chk)
        
        doc_menu.append(Gtk.SeparatorMenuItem())
        
        # Navigation
        prev_tab = Gtk.MenuItem(label="Previous Tab")
        prev_tab.connect("activate", self.on_prev_tab)
        prev_tab.add_accelerator("activate", self.accel_group, Gdk.KEY_Page_Up, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        doc_menu.append(prev_tab)

        next_tab = Gtk.MenuItem(label="Next Tab")
        next_tab.connect("activate", self.on_next_tab)
        next_tab.add_accelerator("activate", self.accel_group, Gdk.KEY_Page_Down, Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        doc_menu.append(next_tab)
        
        doc_menu.append(Gtk.SeparatorMenuItem())
        
        # Dynamic Tab List (Placeholder / Simple)
        # We'll rely on on_tab_switched to update this if we wanted full dynamic
        
        menubar.append(doc_item)
        
        # Tools Menu
        tools_menu = Gtk.Menu()
        tools_item = Gtk.MenuItem(label="Tools")
        tools_item.set_submenu(tools_menu)
        
        # Formatters
        fmt_json = Gtk.MenuItem(label="Format JSON")
        fmt_json.set_action_name("win.format_json")
        fmt_json.add_accelerator("activate", self.accel_group, Gdk.KEY_J, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(fmt_json)
        
        fmt_xml = Gtk.MenuItem(label="Format XML")
        fmt_xml.set_action_name("win.format_xml")
        fmt_xml.add_accelerator("activate", self.accel_group, Gdk.KEY_X, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(fmt_xml)

        convert_item = Gtk.MenuItem(label="Convert Log to JSON")
        convert_item.set_action_name("win.convert_json")
        convert_item.add_accelerator("activate", self.accel_group, Gdk.KEY_E, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(convert_item)
        
        tools_menu.append(Gtk.SeparatorMenuItem())
        
        # Hex View
        hex_item = Gtk.MenuItem(label="Hex View")
        hex_item.set_action_name("win.hex_view")
        hex_item.add_accelerator("activate", self.accel_group, Gdk.KEY_B, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(hex_item)

        hash_item = Gtk.MenuItem(label="Calculate Hash")
        hash_item.set_action_name("win.calculate_hash")
        hash_item.add_accelerator("activate", self.accel_group, Gdk.KEY_H, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(hash_item)
        
        tools_menu.append(Gtk.SeparatorMenuItem())
        
        # Encodings Submenu
        enc_menu = Gtk.Menu()
        enc_item = Gtk.MenuItem(label="Encryption / Encoding")
        enc_item.set_submenu(enc_menu)
        
        b64_enc = Gtk.MenuItem(label="Base64 Encode")
        b64_enc.set_action_name("win.base64_enc")
        enc_menu.append(b64_enc)
        
        b64_dec = Gtk.MenuItem(label="Base64 Decode")
        b64_dec.set_action_name("win.base64_dec")
        enc_menu.append(b64_dec)
        
        enc_menu.append(Gtk.SeparatorMenuItem())
        
        url_enc = Gtk.MenuItem(label="URL Encode")
        url_enc.set_action_name("win.url_enc")
        enc_menu.append(url_enc)
        
        url_dec = Gtk.MenuItem(label="URL Decode")
        url_dec.set_action_name("win.url_dec")
        enc_menu.append(url_dec)
        
        tools_menu.append(enc_item)

        tools_menu.append(Gtk.SeparatorMenuItem())

        md_item = Gtk.MenuItem(label="Markdown Preview")
        md_item.set_action_name("win.markdown_preview")
        md_item.add_accelerator("activate", self.accel_group, Gdk.KEY_M, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(md_item)
        
        cmp_item = Gtk.MenuItem(label="Compare with Tab...")
        cmp_item.set_action_name("win.compare_tabs")
        cmp_item.add_accelerator("activate", self.accel_group, Gdk.KEY_D, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        tools_menu.append(cmp_item)
        
        menubar.append(tools_item)
        
        # Help Menu (moved to end)
        help_menu = Gtk.Menu()

        help_item = Gtk.MenuItem(label="Help")
        help_item.set_submenu(help_menu)
        
        about_item = Gtk.ImageMenuItem(label="About")
        about_item.set_image(Gtk.Image.new_from_icon_name("help-about", Gtk.IconSize.MENU))
        about_item.set_always_show_image(True)
        about_item.connect("activate", self.on_about)
        help_menu.append(about_item)
        
        menubar.append(help_item)
        
        return menubar

    def create_toolbar(self):
        toolbar = Gtk.Toolbar()
        toolbar.set_style(Gtk.ToolbarStyle.ICONS)
        toolbar.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
        
        # New
        new_btn = Gtk.ToolButton()
        new_btn.set_icon_name("document-new")
        new_btn.set_tooltip_text("New File")
        new_btn.connect("clicked", self.on_new_tab)
        toolbar.insert(new_btn, -1)
        
        # Open
        open_btn = Gtk.ToolButton()
        open_btn.set_icon_name("document-open")
        open_btn.set_tooltip_text("Open File")
        open_btn.connect("clicked", self.on_open_file)
        toolbar.insert(open_btn, -1)
        
        # Save
        save_btn = Gtk.ToolButton()
        save_btn.set_icon_name("document-save")
        save_btn.set_tooltip_text("Save File")
        save_btn.connect("clicked", self.on_save_file)
        toolbar.insert(save_btn, -1)
        
        toolbar.insert(Gtk.SeparatorToolItem(), -1)
        
        # Undo/Redo (Placeholder icons for visual parity)
        undo_btn = Gtk.ToolButton()
        undo_btn.set_icon_name("edit-undo")
        undo_btn.set_tooltip_text("Undo")
        undo_btn.connect("clicked", self.on_undo)
        toolbar.insert(undo_btn, -1)
        
        redo_btn = Gtk.ToolButton()
        redo_btn.set_icon_name("edit-redo")
        redo_btn.set_tooltip_text("Redo")
        redo_btn.connect("clicked", self.on_redo)
        toolbar.insert(redo_btn, -1)
        
        toolbar.insert(Gtk.SeparatorToolItem(), -1)
        
        # Cut/Copy/Paste
        cut_btn = Gtk.ToolButton()
        cut_btn.set_icon_name("edit-cut")
        cut_btn.set_tooltip_text("Cut")
        cut_btn.connect("clicked", self.on_cut)
        toolbar.insert(cut_btn, -1)
        
        copy_btn = Gtk.ToolButton()
        copy_btn.set_icon_name("edit-copy")
        copy_btn.set_tooltip_text("Copy")
        copy_btn.connect("clicked", self.on_copy)
        toolbar.insert(copy_btn, -1)
        
        paste_btn = Gtk.ToolButton()
        paste_btn.set_icon_name("edit-paste")
        paste_btn.set_tooltip_text("Paste")
        paste_btn.connect("clicked", self.on_paste)
        toolbar.insert(paste_btn, -1)
        
        toolbar.insert(Gtk.SeparatorToolItem(), -1)

        # Find
        find_btn = Gtk.ToolButton()
        find_btn.set_icon_name("edit-find")
        find_btn.set_tooltip_text("Find")
        find_btn.connect("clicked", lambda w: self.on_find_clicked("find"))
        toolbar.insert(find_btn, -1)
        
        return toolbar

    def create_search_bar(self):
        self.search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_box.set_spacing(0)
        
        # Row 1: Find
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.set_spacing(5)
        row1.set_border_width(5)
        
        # Close Button
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.connect("clicked", lambda w: self.search_bar_revealer.set_reveal_child(False))
        row1.pack_start(close_btn, False, False, 0)
        
        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_width_chars(30)
        self.search_entry.set_size_request(200, -1)  # Fix GTK warning about negative dimensions
        self.search_entry.connect("search-changed", self.on_search_text_changed)
        self.search_entry.connect("activate", lambda w: self.on_search_next(w))
        row1.pack_start(self.search_entry, False, False, 0)
        
        # Match Count Label
        self.match_count_label = Gtk.Label()
        self.match_count_label.set_margin_start(5)
        self.match_count_label.set_margin_end(5)
        row1.pack_start(self.match_count_label, False, False, 0)
        
        # Navigation
        prev_btn = Gtk.Button.new_from_icon_name("go-up-symbolic", Gtk.IconSize.MENU)
        prev_btn.set_tooltip_text("Find Previous (Shift+F3)")
        prev_btn.connect("clicked", self.on_search_prev)
        row1.pack_start(prev_btn, False, False, 0)
        
        next_btn = Gtk.Button.new_from_icon_name("go-down-symbolic", Gtk.IconSize.MENU)
        next_btn.set_tooltip_text("Find Next (F3)")
        next_btn.connect("clicked", self.on_search_next)
        row1.pack_start(next_btn, False, False, 0)
        
        # Options
        self.match_case_check = Gtk.CheckButton(label="Match case")
        self.match_case_check.connect("toggled", self.on_search_settings_changed)
        row1.pack_start(self.match_case_check, False, False, 5)
        
        self.whole_word_check = Gtk.CheckButton(label="Match whole word")
        self.whole_word_check.connect("toggled", self.on_search_settings_changed)
        row1.pack_start(self.whole_word_check, False, False, 5)
        
        self.regex_check = Gtk.CheckButton(label="Regular expression")
        self.regex_check.connect("toggled", self.on_search_settings_changed)
        row1.pack_start(self.regex_check, False, False, 5)
        
        self.search_box.pack_start(row1, True, True, 0)
        
        # Row 2: Replace (Initially hidden or handled via mode)
        self.replace_revealer = Gtk.Revealer()
        self.replace_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row2.set_spacing(5)
        row2.set_border_width(5)
        
        # Spacer to align with entry
        # A simple label "Replace with:" or similar
        row2.pack_start(Gtk.Label(label="Replace with:"), False, False, 5)
        
        self.replace_entry = Gtk.Entry()
        self.replace_entry.set_width_chars(30)
        self.replace_entry.connect("activate", self.on_replace_one)
        row2.pack_start(self.replace_entry, False, False, 0)
        
        replace_btn = Gtk.Button(label="Replace")
        replace_btn.connect("clicked", self.on_replace_one)
        row2.pack_start(replace_btn, False, False, 0)
        
        replace_all_btn = Gtk.Button(label="Replace All")
        replace_all_btn.connect("clicked", self.on_replace_all)
        row2.pack_start(replace_all_btn, False, False, 0)
        
        self.replace_revealer.add(row2)
        self.search_box.pack_start(self.replace_revealer, False, False, 0)
        
        self.search_bar_revealer.add(self.search_box)
    
    def on_toggle_incremental(self, widget):
        self.incremental_search = widget.get_active()
        # If turned ON, maybe trigger search now?
        if self.incremental_search:
            text = self.search_entry.get_text()
            if text:
                self.search_settings.set_search_text(text)

    def on_toggle_highlight(self, widget):
        self.highlight_all = widget.get_active()
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            if editor.search_context:
                editor.search_context.set_highlight(self.highlight_all)

    def on_goto_line(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        dialog = Gtk.Dialog(title="Go to Line", parent=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_JUMP_TO, Gtk.ResponseType.OK)
        
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(10)
        
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        hbox.pack_start(Gtk.Label(label="Line Number:"), False, False, 0)
        
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        hbox.pack_start(entry, True, True, 0)
        box.add(hbox)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            text = entry.get_text()
            if text.isdigit():
                line = int(text) - 1 # 0-indexed
                buff = editor.buffer
                if line < 0: line = 0
                total = buff.get_line_count()
                if line >= total: line = total - 1
                
                iter_jump = buff.get_iter_at_line(line)
                editor.view.scroll_to_iter(iter_jump, 0.0, True, 0.0, 0.5)
                buff.place_cursor(iter_jump)
        
        dialog.destroy()

    def on_search_text_changed(self, entry):
        text = entry.get_text()
        if self.incremental_search:
            self.search_settings.set_search_text(text)
        else:
             # If incremental is off, we clear the search settings logic?
             # No, simply don't update it yet. The user sees "text" in entry but "highlight" matches old text?
             # Ideally "Incremental Off" means "don't search yet".
             # If I don't update settings, highlighting remains on OLD text.
             # Maybe I should clear settings text if I want "no search"?
             # But usually it just means "don't update".
             pass
        
    def on_search_settings_changed(self, widget):
        self.search_settings.set_case_sensitive(self.match_case_check.get_active())
        self.search_settings.set_at_word_boundaries(self.whole_word_check.get_active())
        self.search_settings.set_regex_enabled(self.regex_check.get_active())
        
    def on_search_next(self, widget, param=None):
        # Update text if incremental is off
        if not self.incremental_search:
             text = self.search_entry.get_text()
             self.search_settings.set_search_text(text)

        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        if editor.search_context:
            buff = editor.buffer
            insert = buff.get_insert()
            iter_start = buff.get_iter_at_mark(insert)
            
            # Helper to unpack results safely
            def unpack_search_result(result):
                if len(result) == 4:
                    return result # success, start, end, wrapped
                elif len(result) == 3:
                    return result[0], result[1], result[2], False
                return False, None, None, False

            # Forward search
            try:
                ret = editor.search_context.forward2(iter_start)
            except AttributeError:
                ret = editor.search_context.forward(iter_start)
            
            success, match_start, match_end, wrapped = unpack_search_result(ret)

            if success:
                # Place cursor at END of match so next search finds next match
                buff.select_range(match_end, match_start)
                editor.view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.5)
            else:
                # Wrap
                start = buff.get_start_iter()
                try:
                    ret = editor.search_context.forward2(start)
                except AttributeError:
                    ret = editor.search_context.forward(start)
                
                success, match_start, match_end, wrapped = unpack_search_result(ret)
                
                if success:
                    buff.select_range(match_end, match_start)
                    editor.view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.5)

    def on_search_prev(self, widget, param=None):
        # Update text if incremental is off
        if not self.incremental_search:
             text = self.search_entry.get_text()
             self.search_settings.set_search_text(text)

        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        if editor.search_context:
            buff = editor.buffer
            insert = buff.get_insert()
            iter_start = buff.get_iter_at_mark(insert)
            
            # Helper to unpack results safely
            def unpack_search_result(result):
                if len(result) == 4:
                    return result # success, start, end, wrapped
                elif len(result) == 3:
                    return result[0], result[1], result[2], False
                return False, None, None, False

            try:
                ret = editor.search_context.backward2(iter_start)
            except AttributeError:
                ret = editor.search_context.backward(iter_start)
                
            success, match_start, match_end, wrapped = unpack_search_result(ret)

            if success:
                # Place cursor at START of match so prev search finds prev match
                buff.select_range(match_start, match_end)
                editor.view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.5)
            else:
                # Wrap to end
                end = buff.get_end_iter()
                try:
                    ret = editor.search_context.backward2(end)
                except AttributeError:
                    ret = editor.search_context.backward(end)
                
                success, match_start, match_end, wrapped = unpack_search_result(ret)

                if success:
                    buff.select_range(match_start, match_end)
                    editor.view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.5)

    def on_cut(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            editor.buffer.cut_clipboard(clipboard, True)

    def on_copy(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            editor.buffer.copy_clipboard(clipboard)

    def on_paste(self, widget):
        # Check if an Entry widget (like search bar) has focus
        focused = self.get_focus()
        if isinstance(focused, Gtk.Entry):
            # Let the Entry handle paste natively
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            text = clipboard.wait_for_text()
            if text:
                focused.paste_clipboard()
            return
        
        # Default: paste to editor
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            editor.buffer.paste_clipboard(clipboard, None, True)

    def on_undo(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            if editor.buffer.can_undo():
                editor.buffer.undo()

    def on_redo(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            if editor.buffer.can_redo():
                editor.buffer.redo()

    def on_zoom_in(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            editor.zoom_in()

    def on_zoom_out(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            editor.zoom_out()

    def on_zoom_reset(self, widget=None, param=None):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            editor.zoom_reset()

    def on_select_font(self, widget):
        dialog = Gtk.FontChooserDialog(title="Select Font", parent=self)
        if self.notebook.get_n_pages() > 0:
             # Set current font of first tab as initial
             first = self.notebook.get_nth_page(0)
             dialog.set_font_desc(first.font_desc)
             
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            font_desc = dialog.get_font_desc()
            n_pages = self.notebook.get_n_pages()
            for i in range(n_pages):
                editor = self.notebook.get_nth_page(i)
                editor.font_desc = font_desc
                editor.view.modify_font(font_desc)
        dialog.destroy()

    def on_change_scheme(self, widget, scheme_id):
        if widget.get_active():
            n_pages = self.notebook.get_n_pages()
            for i in range(n_pages):
                editor = self.notebook.get_nth_page(i)
                editor.set_scheme(scheme_id)

            self.settings.set("theme", scheme_id)
            self.apply_setting("theme", scheme_id)

    def on_toggle_line_numbers(self, widget):
        self.show_line_numbers = widget.get_active()
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            editor.view.set_show_line_numbers(self.show_line_numbers)

    def on_toggle_menubar_state(self, action, value):
        action.set_state(value)
        self.show_menubar = value.get_boolean()
        self.menubar.set_visible(self.show_menubar)

    def on_toggle_toolbar_state(self, action, value):
        action.set_state(value)
        self.show_toolbar = value.get_boolean()
        self.toolbar.set_visible(self.show_toolbar)

    def on_toggle_statusbar_state(self, action, value):
        action.set_state(value)
        self.show_statusbar = value.get_boolean()
        self.statusbar.set_visible(self.show_statusbar)

    def on_toggle_fullscreen_state(self, action, value):
        action.set_state(value)
        self.is_fullscreen = value.get_boolean()
        if self.is_fullscreen:
            self.fullscreen()
        else:
            self.unfullscreen()

    def on_toggle_word_wrap(self, widget):
        self.doc_word_wrap = widget.get_active()
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            editor.view.set_wrap_mode(Gtk.WrapMode.WORD if self.doc_word_wrap else Gtk.WrapMode.NONE)

    def on_toggle_auto_indent(self, widget):
        self.doc_auto_indent = widget.get_active()
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            editor.view.set_auto_indent(self.doc_auto_indent)

    def on_change_tab_size(self, widget, size):
        if widget.get_active():
            self.doc_tab_size = size
            n_pages = self.notebook.get_n_pages()
            for i in range(n_pages):
                editor = self.notebook.get_nth_page(i)
                editor.view.set_tab_width(size)

    def on_change_filetype(self, widget, lang_name):
        # Simple mapping or lookup
        manager = GtkSource.LanguageManager.get_default()
        lang_id = lang_name.lower().replace(" ", "-").replace("++", "pp")
        if lang_name == "Plain Text": lang_id = None
        
        # Try to find it
        language = manager.get_language(lang_id) if lang_id else None
        
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            editor.buffer.set_language(language)

    def on_change_line_ending(self, widget, le):
        self.doc_line_ending = le
        # In reality, this would require converting buffer text
        pass
    def on_encoding_menu_show(self, menu):
        """Update encoding radio selection when menu is shown"""
        page_num = self.notebook.get_current_page()
        if page_num == -1:
            return
        editor = self.notebook.get_nth_page(page_num)
        enc = getattr(editor, 'file_encoding', 'UTF-8')
        
        self._updating_encoding_radio = True
        if enc in self.encoding_items:
            self.encoding_items[enc].set_active(True)
        else:
            # Default to UTF-8 if encoding not in list
            self.encoding_items["UTF-8"].set_active(True)
        self._updating_encoding_radio = False

    def on_change_encoding(self, widget, encoding):
        """Change encoding and reload file with new encoding"""
        # Skip if we're just updating the radio during tab switch
        if getattr(self, '_updating_encoding_radio', False):
            return
            
        # Only act if this radio item is now active (ignore deactivation events)
        if not widget.get_active():
            return
            
        page_num = self.notebook.get_current_page()
        if page_num == -1:
            return
        editor = self.notebook.get_nth_page(page_num)
        
        # Skip if encoding is already the same
        current_enc = getattr(editor, 'file_encoding', 'UTF-8')
        if current_enc == encoding:
            return
        
        # Update encoding
        editor.file_encoding = encoding
        
        # If file exists, re-read with new encoding
        if editor.file_path and os.path.exists(editor.file_path):
            try:
                with open(editor.file_path, "r", encoding=encoding) as f:
                    content = f.read()
                
                # Update buffer with new content
                editor.buffer.begin_user_action()
                editor.buffer.set_text(content)
                editor.buffer.end_user_action()
                
                # Update hash for modified tracking
                editor.last_buffer = hashlib.md5(content.encode(encoding)).hexdigest()
                editor.buffer.set_modified(False)
                
            except Exception as e:
                self.show_error(f"Could not re-read file with {encoding} encoding: {e}")

    def on_toggle_bom(self, widget):
        self.doc_write_bom = widget.get_active()

    def on_toggle_viewer_mode(self, widget):
        self.doc_viewer_mode = widget.get_active()
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            # Read only = not editable
            editor.view.set_editable(not self.doc_viewer_mode)

    def on_prev_tab(self, widget):
        curr = self.notebook.get_current_page()
        if curr > 0:
            self.notebook.set_current_page(curr - 1)
        elif curr == 0 and self.notebook.get_n_pages() > 1:
            self.notebook.set_current_page(self.notebook.get_n_pages() - 1) # Wrap

    def on_next_tab(self, widget):
        curr = self.notebook.get_current_page()
        if curr < self.notebook.get_n_pages() - 1:
            self.notebook.set_current_page(curr + 1)
        elif curr == self.notebook.get_n_pages() -1:
             self.notebook.set_current_page(0) # Wrap

    def on_delete_selection(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            editor.buffer.delete_selection(True, True)

    def on_delete_line(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            insert = buff.get_insert()
            iter_curr = buff.get_iter_at_mark(insert)
            
            # Start of line
            iter_start = iter_curr.copy()
            iter_start.set_line_offset(0)
            
            # End of line (including newline)
            iter_end = iter_start.copy()
            if not iter_end.ends_line():
                 iter_end.forward_to_line_end()
            iter_end.forward_char() # include newline
            
            buff.delete(iter_start, iter_end)

    def on_select_all(self, widget):
        # Check if an Entry widget (like search bar) has focus
        focused = self.get_focus()
        if isinstance(focused, Gtk.Entry):
            # Select all text in the Entry
            focused.select_region(0, -1)
            return
        
        # Default: select all in editor
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            start, end = editor.buffer.get_bounds()
            editor.buffer.select_range(start, end)

    def on_change_case(self, case_type):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            bounds = buff.get_selection_bounds()
            # get_selection_bounds() returns (start_iter, end_iter) or empty tuple
            if bounds:
                start, end = bounds
                text = buff.get_text(start, end, True)
                
                new_text = text
                if case_type == "upper":
                    new_text = text.upper()
                elif case_type == "lower":
                    new_text = text.lower()
                elif case_type == "title":
                    new_text = text.title()
                
                if new_text != text:
                    buff.begin_user_action()
                    buff.delete(start, end)
                    buff.insert(start, new_text)
                    buff.end_user_action()

    def on_duplicate(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            bounds = buff.get_selection_bounds()
            
            if bounds and len(bounds) == 3 and bounds[0]:
                # Duplicate Selection
                start, end = bounds[1], bounds[2]
                text = buff.get_text(start, end, True)
                buff.insert(end, text)
            else:
                # Duplicate Line
                insert = buff.get_insert()
                iter_curr = buff.get_iter_at_mark(insert)
                line = iter_curr.get_line()
                
                iter_start = buff.get_iter_at_line(line)
                iter_end = iter_start.copy()
                if not iter_end.ends_line():
                    iter_end.forward_to_line_end()
                iter_end.forward_char() # include newline if exists
                
                text = buff.get_text(iter_start, iter_end, True)
                # Ensure we have a newline if duplicating last line without one
                if not text.endswith('\n'):
                     text = "\n" + text
                     
                buff.insert(iter_end, text)

    def on_move_line(self, direction):
        # This is complex to implement robustly without native support.
        # Simple hack: delete line, insert at prev/next line.
        # Skipping for now to avoid messiness unless GtkSourceView has helper.
        pass 

    def on_indent(self, increase):
         # Simple Tab insertion/deletion
         page_num = self.notebook.get_current_page()
         if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            
            # For simplicity, operate on current line or selection
            # TODO: Full block indent support
            if increase:
                insert = buff.get_insert()
                iter_curr = buff.get_iter_at_mark(insert)
                line_start = iter_curr.copy()
                line_start.set_line_offset(0)
                buff.insert(line_start, "\t")
            else:
                # Check for tab at start
                insert = buff.get_insert()
                iter_curr = buff.get_iter_at_mark(insert)
                line_start = iter_curr.copy()
                line_start.set_line_offset(0)
                next_char = line_start.copy()
                next_char.forward_char()
                
                char = buff.get_text(line_start, next_char, False)
                if char == "\t" or char == " ":
                     buff.delete(line_start, next_char)

    def on_replace_one(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        if editor.search_context:
            buff = editor.buffer
            # Check if selection matches search
            bounds = buff.get_selection_bounds()
            if bounds and len(bounds) == 3 and bounds[0]:
                start, end = bounds[1], bounds[2]
                # Verify match
                # GtkSourceView 4: default replace uses the search text.
                # replace(match_start, match_end, replace_text, replace_length) -> bool
                try:
                    editor.search_context.replace(start, end, self.replace_entry.get_text(), -1)
                except Exception as e:
                    print(f"Replace error: {e}")
                
            self.on_search_next(None)

    def on_replace_all(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        if editor.search_context:
            editor.search_context.replace_all(self.replace_entry.get_text(), -1)

    def on_find_clicked(self, mode="find"):
        from gi.repository import GLib
        
        # Toggle reveal
        reveal = self.search_bar_revealer.get_reveal_child()
        
        # If hidden, show and focus after reveal completes
        if not reveal:
            self.search_bar_revealer.set_reveal_child(True)
            # Defer focus to ensure widget is mapped and visible
            GLib.idle_add(self._focus_search_entry)
        else:
            # Already shown, just focus
            GLib.idle_add(self._focus_search_entry)
            
        if mode == "replace":
            self.replace_revealer.set_reveal_child(True)
        else:
            self.replace_revealer.set_reveal_child(False)
    
    def _focus_search_entry(self):
        """Helper to focus search entry after GTK event loop processes"""
        self.search_entry.grab_focus()
        return False  # Don't repeat

    def create_actions(self):
        # Action Map
        action_group = Gio.SimpleActionGroup()
        self.insert_action_group("win", action_group)

        # Actions
        actions = [
            ("new_tab", self.on_new_tab),
            ("new_window", self.on_new_window),
            ("open", self.on_open_file),
            ("save", self.on_save_file),
            ("save_as", self.on_save_as),
            ("save_all", self.on_save_all),
            ("reload", self.on_reload),
            ("print", self.on_print),
            ("detach_tab", self.on_detach_tab),
            ("find", lambda *args: self.on_find_clicked("find")),
            ("replace", lambda *args: self.on_find_clicked("replace")),
            ("find_next", self.on_search_next),
            ("find_prev", self.on_search_prev),
            ("find_prev", self.on_search_prev),
            ("indent", lambda *args: self.on_indent(True)),
            ("unindent", lambda *args: self.on_indent(False)),
            ("undo", lambda *args: self.on_undo(None)),
            ("redo", lambda *args: self.on_redo(None)),
            ("zoom_in", self.on_zoom_in),
            ("zoom_out", self.on_zoom_out),
            ("close_tab", self.on_close_current_tab),
            ("close_window", lambda *args: self.close()),
            ("quit", lambda *args: self.get_application().quit())
        ]

        # Helper Actions for shortcuts
        actions.extend([
            ("zoom_reset", self.on_zoom_reset),
            ("toc_upper", lambda *args: self.on_change_case("upper")),
            ("toc_lower", lambda *args: self.on_change_case("lower")),
            ("duplicate", lambda *args: self.on_duplicate(None)),
            ("delete_line", lambda *args: self.on_delete_line(None)),
            ("move_up", lambda *args: self.on_move_line("up")),
            ("move_down", lambda *args: self.on_move_line("down")),
            ("preferences", lambda *args: self.on_preferences_clicked(None)),
            # Analysis Actions
            ("format_json", self.on_format_json),
            ("format_xml", self.on_format_xml),
            ("convert_json", self.on_convert_json),
            ("hex_view", self.on_hex_view),
            ("calculate_hash", self.on_calculate_hash),
            # Encodings
            ("base64_enc", lambda *args: self.on_transform_text("base64_enc")),
            ("base64_dec", lambda *args: self.on_transform_text("base64_dec")),
            ("url_enc", lambda *args: self.on_transform_text("url_enc")),
            ("url_dec", lambda *args: self.on_transform_text("url_dec")),
            ("markdown_preview", self.on_markdown_preview),
            ("compare_tabs", self.on_compare_tabs),
            ("quick_open", self.on_quick_open_action),
            # Tab Navigation
            ("next_tab", self.on_next_tab),
            ("prev_tab", self.on_prev_tab),
        ])

        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            action_group.add_action(action)
        
        # Stateful Actions (View Toggles)
        toggles = [
            ("toggle_menubar", self.show_menubar, self.on_toggle_menubar_state),
            ("toggle_toolbar", self.show_toolbar, self.on_toggle_toolbar_state),
            ("toggle_statusbar", self.show_statusbar, self.on_toggle_statusbar_state),
            ("toggle_fullscreen", self.is_fullscreen, self.on_toggle_fullscreen_state)
        ]
        
        for name, state, callback in toggles:
            action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant.new_boolean(state))
            action.connect("change-state", callback)
            action_group.add_action(action)

        self.insert_action_group("win", action_group)
        
        # Accelerators
        app = self.get_application()
        app.set_accels_for_action("win.quick_open", ["<Primary>p"])
        app.set_accels_for_action("win.new_tab", ["<Primary>n"])
        app.set_accels_for_action("win.new_window", ["<Primary><Shift>n"])
        app.set_accels_for_action("win.open", ["<Primary>o"])
        app.set_accels_for_action("win.save", ["<Primary>s"])
        app.set_accels_for_action("win.save_as", ["<Primary><Shift>s"])
        app.set_accels_for_action("win.reload", ["F5"])
        app.set_accels_for_action("win.print", ["<Primary>p"])
        app.set_accels_for_action("win.detach_tab", ["<Primary>d"])
        app.set_accels_for_action("win.reopen_tab", ["<Primary><Shift>t"])
        app.set_accels_for_action("win.find", ["<Primary>f"])
        app.set_accels_for_action("win.replace", ["<Primary>h"])
        app.set_accels_for_action("win.find_replace", ["<Primary>r"])
        app.set_accels_for_action("win.find_next", ["<Primary>g", "F3"])
        app.set_accels_for_action("win.find_prev", ["<Primary><Shift>g", "<Shift>F3"])
        app.set_accels_for_action("win.goto_line", ["<Primary>l"])
        app.set_accels_for_action("win.indent", ["<Primary>i"])
        app.set_accels_for_action("win.unindent", ["<Primary>u"])
        app.set_accels_for_action("win.undo", ["<Primary>z"])
        app.set_accels_for_action("win.redo", ["<Primary>y", "<Primary><Shift>z"])
        app.set_accels_for_action("win.zoom_in", ["<Primary>plus", "<Primary>equal"])
        app.set_accels_for_action("win.zoom_out", ["<Primary>minus"])
        app.set_accels_for_action("win.zoom_reset", ["<Primary>0"])
        app.set_accels_for_action("win.toggle_menubar", ["<Primary>m"])
        app.set_accels_for_action("win.toggle_fullscreen", ["F11"])
        app.set_accels_for_action("win.close_tab", ["<Primary>w"])
        app.set_accels_for_action("win.close_window", ["<Primary><Shift>w"])
        app.set_accels_for_action("win.quit", ["<Primary>q"])
        app.set_accels_for_action("win.toc_upper", ["<Primary><Shift>u"])
        app.set_accels_for_action("win.toc_lower", ["<Primary><Shift>l"])
        app.set_accels_for_action("win.duplicate", ["<Primary>d"])
        app.set_accels_for_action("win.delete_line", ["<Primary><Shift>k"])
        app.set_accels_for_action("win.move_up", ["<Primary>Up"])
        app.set_accels_for_action("win.move_down", ["<Primary>Down"])
        app.set_accels_for_action("win.preferences", ["<Primary>comma"])
        app.set_accels_for_action("win.format_json", ["<Primary><Shift>j"])
        app.set_accels_for_action("win.format_xml", ["<Primary><Shift>x"])
        app.set_accels_for_action("win.convert_json", ["<Primary><Alt>l"])
        app.set_accels_for_action("win.hex_view", ["<Primary><Shift>h"])
        # Tab Navigation
        app.set_accels_for_action("win.next_tab", ["<Primary>Tab", "<Primary>Page_Down"])
        app.set_accels_for_action("win.prev_tab", ["<Primary><Shift>Tab", "<Primary>Page_Up"])

    def on_new_window(self, widget, param=None):
        app = self.get_application()
        win = ZenpadWindow(app)
        win.present()

    def on_next_tab(self, action=None, param=None):
        """Switch to next tab (Ctrl+Tab)"""
        n_pages = self.notebook.get_n_pages()
        if n_pages > 1:
            current = self.notebook.get_current_page()
            next_page = (current + 1) % n_pages
            self.notebook.set_current_page(next_page)

    def on_prev_tab(self, action=None, param=None):
        """Switch to previous tab (Ctrl+Shift+Tab)"""
        n_pages = self.notebook.get_n_pages()
        if n_pages > 1:
            current = self.notebook.get_current_page()
            prev_page = (current - 1) % n_pages
            self.notebook.set_current_page(prev_page)

    def on_open_recent(self, recent_chooser):
        item = recent_chooser.get_current_item()
        if item:
            uri = item.get_uri()
            # Convert file:// uri to path
            if uri.startswith("file://"):
                path = uri[7:]
                # decode %20 etc if needed, but keeping simple
                import urllib.parse
                path = urllib.parse.unquote(path)
                # Use the centralized open method to handle errors/warnings consistently
                # Don't create new tabs for missing recent files
                self.open_file_from_path(path, create_if_missing=False)

    def on_save_as(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        self.save_file_as(editor)

    def on_save_all(self, widget, param=None):
        n = self.notebook.get_n_pages()
        for i in range(n):
            editor = self.notebook.get_nth_page(i)
            if editor.file_path:
                self.save_to_path(editor, editor.file_path)
            # Alternatively prompt for save as, but usually save all just saves known files

    def on_reload(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        if not editor.file_path or not os.path.exists(editor.file_path):
            return
        
        # Warn if there are unsaved changes
        if editor.buffer.get_modified():
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Unsaved changes will be lost"
            )
            dialog.format_secondary_text(
                "This file has unsaved changes. Reload from disk anyway?"
            )
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.YES:
                return
        
        try:
            with open(editor.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            editor.set_text(content)
            editor.buffer.set_modified(False)
        except Exception as e:
            self.show_error(f"Error reloading: {e}")

    def on_print(self, widget, param=None):
        """Print the current document using GtkSourceView PrintCompositor"""
        page_num = self.notebook.get_current_page()
        if page_num == -1:
            return
        editor = self.notebook.get_nth_page(page_num)
        
        # Create print compositor for syntax-highlighted printing
        compositor = GtkSource.PrintCompositor.new_from_view(editor.view)
        
        # Configure print settings
        compositor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        compositor.set_highlight_syntax(True)
        compositor.set_print_line_numbers(5)  # Print line numbers every 5 lines
        
        # Set header and footer
        file_name = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
        compositor.set_header_format(True, None, file_name, None)
        compositor.set_footer_format(True, None, "Page %N of %Q", None)
        compositor.set_print_header(True)
        compositor.set_print_footer(True)
        
        # Create print operation
        print_op = Gtk.PrintOperation()
        print_op.set_n_pages(1)  # Will be updated in begin-print
        
        def begin_print(operation, context):
            # Paginate the document
            while not compositor.paginate(context):
                pass
            n_pages = compositor.get_n_pages()
            operation.set_n_pages(n_pages)
        
        def draw_page(operation, context, page_nr):
            compositor.draw_page(context, page_nr)
        
        print_op.connect("begin-print", begin_print)
        print_op.connect("draw-page", draw_page)
        
        # Run print dialog
        result = print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)
        
        if result == Gtk.PrintOperationResult.ERROR:
            error = print_op.get_error()
            dlg = Gtk.MessageDialog(parent=self, modal=True, 
                                    message_type=Gtk.MessageType.ERROR,
                                    buttons=Gtk.ButtonsType.OK, 
                                    text="Print Error")
            dlg.format_secondary_text(str(error))
            dlg.run()
            dlg.destroy()


    def on_detach_tab(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        
        # Get content and path
        editor = self.notebook.get_nth_page(page_num)
        text = editor.get_text()
        path = editor.file_path
        title = os.path.basename(path) if path else "Untitled"
        
        # Remove from current
        self.close_tab(page_num)
        
        # Create new window with this tab
        app = self.get_application()
        win = ZenpadWindow(app)
        win.add_tab(text, title, path)
        # Remove the initial empty tab of new window if it exists
        if win.notebook.get_n_pages() > 1:
            win.notebook.remove_page(0)
        win.present()

    def on_new_tab(self, widget, param=None):
        self.add_tab()
        
    def on_close_current_tab(self, widget=None, param=None):
        n_pages = self.notebook.get_n_pages()
        if n_pages == 1:
            self.close()
            return
        
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            if self.check_unsaved_changes(editor):
                self.close_tab(page_num)

    def close_tab(self, page_num):
        self.notebook.remove_page(page_num)

    def add_tab(self, content=None, title="Untitled", path=None):
        editor = EditorTab(self.search_settings)
        if content is not None:
            editor.set_text(content)
        
        if path:
            editor.file_path = path
            editor.detect_language(path)
        else:
            editor.file_path = None
        
        # Inherit Viewer Mode
        editor.view.set_editable(not self.doc_viewer_mode)
        
        # Tab Label (with close button)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.set_spacing(5)
        
        # Icon (Default hidden for untitled/new)
        icon = Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.MENU)
        # Only show if we have a path (opened file) initially
        if not path:
             icon.set_visible(False)
             icon.set_no_show_all(True) # Prevent show_all() from forcing it visible
        hbox.pack_start(icon, False, False, 0)
        
        label = Gtk.Label(label=title)
        hbox.pack_start(label, True, True, 0)
        
        close_btn = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.MENU)
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.connect("clicked", lambda btn: self.on_close_clicked(editor))
        hbox.pack_start(close_btn, False, False, 0)
        hbox.show_all()
        
        # EventBox for Right Click
        event_box = Gtk.EventBox()
        event_box.set_visible_window(False) # Let clicks pass through to button if not handled
        event_box.add(hbox)
        event_box.connect("button-press-event", self.on_tab_button_press, editor)
        event_box.show_all()
        
        index = self.notebook.append_page(editor, event_box)
        self.notebook.show_all()
        
        # Connect signals
        editor.buffer.connect("modified-changed", lambda w: self.update_tab_label(editor))
        editor.buffer.connect("changed", lambda w: self.update_tab_label(editor))
        editor.buffer.connect("changed", lambda w: self.update_title(editor))
        editor.buffer.connect("mark-set", lambda w, loc, mark: self.update_match_count(editor))
        # Language changed signal
        editor.buffer.connect("notify::language", lambda w, p: self.update_tab_label(editor))
        # Content changed signal (for Markdown Preview)
        editor.buffer.connect("changed", lambda w: self.on_buffer_changed(editor))
        # Search signals
        if editor.search_context:
             editor.search_context.connect("notify::occurrences-count", lambda w, p: self.update_match_count(editor))

        # Apply Global Settings to New Tab
        editor.view.set_show_line_numbers(self.show_line_numbers)
        editor.view.set_highlight_current_line(self.settings.get("highlight_current_line"))
        editor.view.set_wrap_mode(Gtk.WrapMode.WORD if self.doc_word_wrap else Gtk.WrapMode.NONE)
        editor.view.set_auto_indent(self.doc_auto_indent)
        editor.view.set_tab_width(self.doc_tab_size)
        editor.view.set_insert_spaces_instead_of_tabs(self.doc_use_spaces)
        
        # Apply Font
        font_name = self.settings.get("font")
        if font_name:
             font_desc = Pango.FontDescription(font_name)
             editor.view.modify_font(font_desc)
             editor.font_desc = font_desc
        
        # Apply Theme
        editor.set_scheme(self.settings.get("theme"))

        # Apply Padding
        pad_map = {"small": 2, "normal": 6, "large": 12}
        margin = pad_map.get(self.settings.get("editor_padding"), 6)
        editor.view.set_left_margin(margin)
        editor.view.set_right_margin(margin)
        
        # Apply new editor settings
        editor.view.set_show_right_margin(self.settings.get("show_right_margin"))
        editor.view.set_right_margin_position(self.settings.get("right_margin_column"))
        editor.buffer.set_highlight_matching_brackets(self.settings.get("highlight_matching_brackets"))
        # Show whitespace using SpaceDrawer (GtkSourceView 4 API)
        space_drawer = editor.view.get_space_drawer()
        space_drawer.set_enable_matrix(self.settings.get("show_whitespace"))
        if self.settings.get("show_whitespace"):
            space_drawer.set_types_for_locations(GtkSource.SpaceLocationFlags.ALL, GtkSource.SpaceTypeFlags.ALL)
        editor.view.set_smart_backspace(self.settings.get("smart_backspace"))

        # Reset modified flag (ensure opening file/new tab is clean)
        editor.buffer.set_modified(False)

        # Initialize last_buffer for new tabs
        content = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)
        editor.last_buffer = hashlib.md5(content.encode("UTF-8")).hexdigest()

        # Switch to the new tab
        # Reset modified flag (ensure opening file/new tab is clean)
        editor.buffer.set_modified(False)
        
        # Switch to the new tab
        self.notebook.set_current_page(index)
        self.update_tab_label(editor)
        return editor

    def update_tab_label(self, editor):
        page_num = self.notebook.page_num(editor)
        if page_num == -1: return
        
        tab_widget = self.notebook.get_tab_label(editor)
        
        # Determine if it's the EventBox wrapper or the Box directly
        if isinstance(tab_widget, Gtk.EventBox):
            hbox = tab_widget.get_child()
        else:
            hbox = tab_widget
            
        children = hbox.get_children()
        # Expecting [icon, label] or just [label] if previously created without icon
        
        # Helper to get exact widget
        icon_widget = None
        label_widget = None
        
        for child in children:
            if isinstance(child, Gtk.Image):
                icon_widget = child
            elif isinstance(child, Gtk.Label):
                label_widget = child
        
        if label_widget:
             name = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
             
             # Check for unsaved changes
             content = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)
             saved = hashlib.md5(content.encode("UTF-8")).hexdigest() == editor.last_buffer
             
             if editor.buffer.get_modified() and not saved:
                 name += " ●"
                 
             label_widget.set_text(name)
             if editor.file_path:
                 tab_widget.set_tooltip_text(editor.file_path)

        # Update Language Indicators
        lang = editor.buffer.get_language()
        lang_name = lang.get_name() if lang else "Plain Text"
        lang_id = lang.get_id() if lang else None
        
        # 1. Update Status Bar (Only if current tab)
        if page_num == self.notebook.get_current_page():
            self.update_language_label(editor)
            
        # 2. Update Tab Icon
        if icon_widget:
            # Logic: Show icon if language is detected OR file has a path.
            # Hide if plain text AND untitled (clean slate).
            
            is_plain = (lang_id is None or lang_id == "text")
            is_untitled = (editor.file_path is None)
            
            if is_plain and is_untitled:
                icon_widget.set_visible(False)
            else:
                icon_widget.set_visible(True)
                icon_name = self.get_icon_name_for_language(lang_id)
                icon_widget.set_from_icon_name(icon_name, Gtk.IconSize.MENU)

        
        # Update Window Title if this is the current tab
        if page_num == self.notebook.get_current_page():
            self.update_title(editor)

    def update_language_label(self, editor):
        """Dedicated method to update status bar language label"""
        lang = editor.buffer.get_language()
        lang_name = lang.get_name() if lang else "Plain Text"
        self.language_label.set_text(lang_name)

    def update_match_count(self, editor):
        # Only update if it's the current tab
        current_page = self.notebook.get_current_page()
        if current_page != -1 and self.notebook.get_nth_page(current_page) == editor:
            if editor.search_context:
                count = editor.search_context.get_occurrences_count()
                
                # Get current match index
                current = 0
                buff = editor.buffer
                bounds = buff.get_selection_bounds()
                if bounds and len(bounds) == 3 and bounds[0]:
                    start, end = bounds[1], bounds[2]
                    target_offset = start.get_offset()

                    try:
                        current = editor.search_context.get_occurrence_position(start, end)
                    except AttributeError:
                        # Fallback: Count manually by collecting offsets
                        # Robust but potentially slow for huge files
                        current = 0
                        iter_curr = editor.buffer.get_start_iter()
                        match_offsets = []
                        
                        while True:
                            try:
                                ret = editor.search_context.forward2(iter_curr)
                            except AttributeError:
                                ret = editor.search_context.forward(iter_curr)
                            
                            # unpack
                            if len(ret) == 4:
                                s, m_start, m_end, wrapped = ret
                            elif len(ret) == 3:
                                s, m_start, m_end = ret[0], ret[1], ret[2]
                            else:
                                break
                            
                            if not s:
                                break
                                
                            match_offsets.append(m_start.get_offset())
                            iter_curr = m_end
                        
                        # Find our place
                        if target_offset in match_offsets:
                            current = match_offsets.index(target_offset) + 1
                        else:
                             # Try approximate match (cursor inside match?)
                             # If selection is somehow different
                           pass


                if count == -1:
                    self.match_count_label.set_text("")
                elif current > 0:
                    self.match_count_label.set_text(f"{current} of {count} matches")
                else:
                    self.match_count_label.set_text(f"{count} matches")
            else:
                self.match_count_label.set_text("")

    def on_close_clicked(self, editor):
        page_num = self.notebook.page_num(editor)
        if page_num == -1: return

        # Check for unsaved changes first
        if not self.check_unsaved_changes(editor):
            return

        # If it's the last tab, close the window
        if self.notebook.get_n_pages() == 1:
            self.close()
        else:
            self.close_tab(page_num)

    def on_open_file(self, widget, param=None):
        dialog = Gtk.FileChooserDialog(
            title="Open File", parent=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            self.open_file_from_path(file_path)
        
        dialog.destroy()

    def _close_empty_untitled_tab(self):
        """
        Close the current tab if it's an empty, unmodified Untitled tab.
        This prevents tab clutter when opening files via GUI.
        """
        page_num = self.notebook.get_current_page()
        if page_num == -1:
            return
        
        editor = self.notebook.get_nth_page(page_num)
        
        # Check: is this an untitled tab? (no file path)
        if editor.file_path:
            return
        
        # Check: is the buffer empty?
        start, end = editor.buffer.get_bounds()
        content = editor.buffer.get_text(start, end, True)
        if content.strip():  # Has content
            return
        
        # Check: is it unmodified?
        if editor.buffer.get_modified():
            return
        
        # All conditions met - close this empty untitled tab
        self.notebook.remove_page(page_num)

    def open_file_from_path(self, file_path, line=None, column=None, encoding=None, create_if_missing=True):
        # Check if current tab is empty untitled - if so, close it first
        self._close_empty_untitled_tab()
        
        if not os.path.exists(file_path):
             # Warn user first
             dialog = Gtk.MessageDialog(
                 transient_for=self,
                 flags=0,
                 message_type=Gtk.MessageType.WARNING,
                 buttons=Gtk.ButtonsType.OK,
                 text="File Not Found",
             )
             dialog.format_secondary_text(
                 f"The file '{os.path.basename(file_path)}' was not found."
             )
             dialog.run()
             dialog.destroy()

             if not create_if_missing:
                 return

             # Create new tab with this filename/path, ready to save
             self.add_tab("", os.path.basename(file_path), os.path.abspath(file_path))
             return

        # Check if file is binary
        is_binary = file_utils.is_binary_file(file_path)
        
        if is_binary:
            # Show binary file dialog
            result = self.show_binary_file_dialog(os.path.basename(file_path))
            if result == "cancel":
                return
            
            # Open as read-only with raw content display
            try:
                with open(file_path, 'rb') as f:
                    raw_bytes = f.read()
                
                # Convert to hex representation for display
                # Show first 1KB in hex view format
                hex_lines = []
                hex_lines.append(f"# Binary file: {os.path.basename(file_path)}")
                hex_lines.append(f"# Size: {len(raw_bytes)} bytes")
                hex_lines.append(f"# This file is opened in read-only mode.")
                hex_lines.append("")
                
                # Show hex dump of first 1KB
                for i in range(0, min(len(raw_bytes), 1024), 16):
                    chunk = raw_bytes[i:i+16]
                    hex_part = ' '.join(f'{b:02x}' for b in chunk)
                    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                    hex_lines.append(f"{i:08x}  {hex_part:<48}  |{ascii_part}|")
                
                if len(raw_bytes) > 1024:
                    hex_lines.append(f"\n... ({len(raw_bytes) - 1024} more bytes not shown)")
                
                content = '\n'.join(hex_lines)
                
                editor = self.add_tab(content, os.path.basename(file_path), file_path)
                editor.is_binary = True
                editor.is_readonly = True
                editor.view.set_editable(False)  # Disable editing
                editor.file_encoding = "Binary"
                
                if line is not None:
                    self.goto_line(editor, line, column)
                    
            except Exception as e:
                self.show_error(f"Error opening binary file: {e}")
            return

        # Text file - use safe file reading
        try:
            if encoding:
                # User specified encoding
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                detected_encoding = encoding
            else:
                # Auto-detect encoding
                detected_encoding, content, error = file_utils.detect_encoding(file_path)
                if error:
                    self.show_error(f"Error reading file: {error}")
                    return
            
            editor = self.add_tab(content, os.path.basename(file_path), file_path)
            editor.file_encoding = detected_encoding
            last_text = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)

            try:
                editor.last_buffer = hashlib.md5(last_text.encode(detected_encoding)).hexdigest()
            except (UnicodeEncodeError, LookupError):
                editor.last_buffer = hashlib.md5(last_text.encode('utf-8', errors='replace')).hexdigest()
            
            if line is not None:
                self.goto_line(editor, line, column)
            
            # Add to Recent
            manager = Gtk.RecentManager.get_default()
            manager.add_item("file://" + file_path)
            
        except Exception as e:
            self.show_error(f"Error opening file: {e}")

    def show_error(self, message):
        dlg = Gtk.MessageDialog(parent=self, modal=True, message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.OK, text="Error")
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()

    def show_binary_file_dialog(self, filename):
        """
        Show dialog for binary file detection.
        Returns: "readonly" to open read-only, "cancel" to abort
        """
        dlg = Gtk.MessageDialog(
            parent=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Binary File Detected"
        )
        dlg.format_secondary_text(
            f"The file '{filename}' appears to be a binary or non-text file.\n\n"
            "Opening it in text mode may display incorrectly and saving could corrupt the file."
        )
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Open Read-Only", Gtk.ResponseType.OK)
        
        response = dlg.run()
        dlg.destroy()
        
        if response == Gtk.ResponseType.OK:
            return "readonly"
        return "cancel"

    def on_save_file(self, widget, param=None):
        page_num = self.notebook.get_current_page()
        if page_num == -1:
            return
        
        editor = self.notebook.get_nth_page(page_num)
        
        # Prevent saving binary files (would corrupt them)
        if getattr(editor, 'is_binary', False):
            dlg = Gtk.MessageDialog(
                parent=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Cannot Save Binary File"
            )
            dlg.format_secondary_text(
                "This binary file is opened in read-only mode.\n"
                "Saving would corrupt the file data."
            )
            dlg.run()
            dlg.destroy()
            return
        
        last_text = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)

        editor.last_buffer = hashlib.md5(last_text.encode("UTF-8")).hexdigest()
        if editor.file_path:
            self.save_to_path(editor, editor.file_path)
        else:
            self.save_file_as(editor)

    def save_file_as(self, editor):
        dialog = Gtk.FileChooserDialog(
            title="Save File", parent=self, action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        mapping = {
            "python": ".py",
            "perl": ".pl",
            "ruby": ".rb",
            "c": ".c",
            "c++": ".cpp",
            "java": ".java",
            "javascript": ".js",
            "json": ".json",
            "xml": ".xml",
            "html": ".html",
            "css": ".css",
            "sh": ".sh",
            "bash": ".bash",
            "markdown": ".md"
        }
        try:
            lang = editor.buffer.get_language().get_name().lower()
            if lang == "python 2" or lang == "python 3": lang = "python" # same extension used by both python 2 and 3

            suggested_ext = mapping.get(lang, ".txt")
            dialog.set_current_name("Untitled"+suggested_ext)
        except Exception as e:
            dialog.set_current_name("Untitled.txt") # Failed to get language so just suggest .txt

        dialog.set_do_overwrite_confirmation(True)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            self.save_to_path(editor, file_path)
            
            # Add to Recent
            manager = Gtk.RecentManager.get_default()
            manager.add_item("file://" + file_path)
            
        dialog.destroy()

    def save_to_path(self, editor, path):
        try:
            content = editor.get_text()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            editor.file_path = path
            editor.buffer.set_modified(False) # Mark as saved
            editor.detect_language(path)
            self.update_tab_label(editor)
        except PermissionError:
            self.show_error(f"Permission denied: Cannot write to '{path}'.\nCheck file permissions or run as administrator.")
        except Exception as e:
            self.show_error(f"Error saving file: {e}")

    def check_unsaved_changes(self, editor):
        if editor.buffer.get_modified():
            content = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)

            # Changed but content is same, return true
            if hashlib.md5(content.encode("UTF-8")).hexdigest() == editor.last_buffer:
                return True

            filename = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.NONE,
                text=f"Save changes to document \"{filename}\" before closing?",
            )
            dialog.add_buttons(
                "Close without Saving", Gtk.ResponseType.REJECT,
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE, Gtk.ResponseType.YES,
            )
            dialog.format_secondary_text("If you don't save, changes will be permanently lost.")
            
            response = dialog.run()
            dialog.destroy()
            
            if response == Gtk.ResponseType.YES:
                self.on_save_file(None)
                # Check if save was successful (buffer not modified)
                if editor.buffer.get_modified():
                    return False # Save failed or cancelled
                return True
            elif response == Gtk.ResponseType.REJECT:
                # User explicitly discarded changes - clear modified flag
                # so session manager doesn't save this content
                editor.buffer.set_modified(False)
                return True # Close without saving
            else:
                return False # Cancel
        return True

    def on_close_current_tab(self, widget=None, param=None):
        n_pages = self.notebook.get_n_pages()
        if n_pages == 1:
            self.close()
            return
        
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            if self.check_unsaved_changes(editor):
                self.close_tab(page_num)

    def close_tab(self, page_num):
        editor = self.notebook.get_nth_page(page_num)
        if editor.file_path:
             self.closed_tabs.append((editor.file_path, editor.get_cursor_position()))
        self.notebook.remove_page(page_num)
        # If no pages, maybe new tab? or empty?
        if self.notebook.get_n_pages() == 0:
            self.on_new_tab(None)

    def on_tab_switched(self, notebook, page, page_num):
        editor = self.notebook.get_nth_page(page_num)
        self.update_statusbar(editor)
        self.update_language_label(editor) # Force update usage
        self.update_match_count(editor) # Update search count for this tab
        
        # Update encoding radio button (block handler to prevent reload)
        self._updating_encoding_radio = True
        enc = getattr(editor, 'file_encoding', 'UTF-8')
        if enc in self.encoding_items:
            self.encoding_items[enc].set_active(True)
        self._updating_encoding_radio = False
        
        # Disconnect previous
        if getattr(self, "current_cursor_handler", None) and getattr(self, "current_buffer", None):
             try:
                 self.current_buffer.disconnect(self.current_cursor_handler)
             except:
                 pass

        self.current_buffer = editor.buffer
        self.current_cursor_handler = editor.buffer.connect("notify::cursor-position", lambda w, p: self.update_statusbar(editor))
        
        # Update window title
        self.update_title(editor)
        
        # Update Markdown Preview if open
        if self.md_window and self.md_window.is_visible():
            self.md_window.update_content(editor.get_text())

    def update_title(self, editor):
        filename = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
        content = editor.buffer.get_text(editor.buffer.get_start_iter(), editor.buffer.get_end_iter(), True)
        saved = hashlib.md5(content.encode("UTF-8")).hexdigest() == editor.last_buffer

        if editor.buffer.get_modified() and not saved:
            self.set_title(f"*{filename} - Zenpad")
        else:
            self.set_title(f"{filename} - Zenpad")


    def update_statusbar(self, editor):
        line, col = editor.get_cursor_position()
        
        # Info
        encoding = "UTF-8" # Default for now
        le_label = {
            "\n": "Unix (LF)",
            "\r\n": "Windows (CRLF)",
            "\r": "Mac (CR)",
            "Current": "Unix (LF)" # Default assumption
        }.get(self.doc_line_ending, "Unix (LF)")
        
        self.statusbar.pop(0) # Remove old
        self.statusbar.push(0, f"Line {line}, Column {col}  |  {encoding}  |  {le_label}")

    def on_preferences_clicked(self, widget):
        dialog = PreferencesDialog(self)
        dialog.run()
        dialog.destroy()

    def apply_setting(self, key, value):
        # Update local state if variable exists
        if key == "show_line_numbers": self.show_line_numbers = value
        elif key == "word_wrap": self.doc_word_wrap = value
        elif key == "auto_indent": self.doc_auto_indent = value
        elif key == "tab_width": self.doc_tab_size = int(value)
        elif key == "use_spaces": self.doc_use_spaces = value
        
        # Iterate over all tabs and apply setting
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            view = editor.view
            
            if key == "line_numbers" or key == "show_line_numbers":
                view.set_show_line_numbers(value)
            elif key == "word_wrap":
                view.set_wrap_mode(Gtk.WrapMode.WORD if value else Gtk.WrapMode.NONE)
            elif key == "highlight_current_line":
                view.set_highlight_current_line(value)
            elif key == "auto_indent":
                view.set_auto_indent(value)
            elif key == "tab_width":
                view.set_tab_width(int(value))
            elif key == "use_spaces":
                view.set_insert_spaces_instead_of_tabs(value)
            elif key == "theme":
                editor.set_scheme(value)
            elif key == "font":
                font_desc = Pango.FontDescription(value)
                editor.view.modify_font(font_desc)
                editor.font_desc = font_desc # Update editor's stored desc
            elif key == "editor_padding":
                pad_map = {"small": 2, "normal": 6, "large": 12}
                margin = pad_map.get(value, 6)
                view.set_left_margin(margin)
                view.set_right_margin(margin)
            elif key == "show_right_margin":
                view.set_show_right_margin(value)
            elif key == "right_margin_column":
                view.set_right_margin_position(int(value))
            elif key == "highlight_matching_brackets":
                editor.buffer.set_highlight_matching_brackets(value)
            elif key == "show_whitespace":
                space_drawer = view.get_space_drawer()
                space_drawer.set_enable_matrix(value)
                if value:
                    space_drawer.set_types_for_locations(GtkSource.SpaceLocationFlags.ALL, GtkSource.SpaceTypeFlags.ALL)
            elif key == "smart_backspace":
                view.set_smart_backspace(value)

        # Also store these settings to persistence if needed (not implemented yet)

    def save_session(self, widget, event):
        # 1. Check for unsaved changes in ALL tabs
        n_pages = self.notebook.get_n_pages()
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            if not self.check_unsaved_changes(editor):
                return True  # Cancel close

        # 2. Save Session using SessionManager
        if self.settings.get("restore_session"):
            # Check if there's any unsaved data worth saving
            has_unsaved_data = False
            for i in range(n_pages):
                editor = self.notebook.get_nth_page(i)
                # Only consider tabs that are still marked as modified
                # (User might have clicked "Close without Saving" which clears modified flag)
                if editor.buffer.get_modified():
                    has_unsaved_data = True
                    break
            
            if has_unsaved_data:
                self.session_manager.save(self)
            else:
                # Clear session file - nothing to restore
                self.session_manager.clear()
            
        return False  # Allow closing

    def load_session(self):
        config_path = os.path.join(os.path.expanduser("~"), ".config", "zenpad", "session.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    paths = json.load(f)
                    for path in paths:
                        if os.path.exists(path):
                            with open(path, "r", encoding="utf-8") as f_content:
                                self.add_tab(f_content.read(), os.path.basename(path), path)
            except Exception as e:
                print(f"Error loading session: {e}")
                
        # If no tabs loaded (list empty or file not found), add default
        if self.notebook.get_n_pages() == 0:
            self.add_tab()

        if self.notebook.get_n_pages() == 0:
            self.add_tab()


    def on_about(self, widget, param=None):
        about = Gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_modal(True)
        
        about.set_program_name("Zenpad")
        about.set_version("1.5.0")
        about.set_copyright("Copyright © 2025 - Zenpad Developers")
        about.set_comments("Zenpad is a modern, lightweight, and efficient text editor for Linux.\nDesigned for speed and simplicity.\n\n")
        about.set_website("https://zenpad-dev.github.io")
        # about.set_website_label("Website") # Show full URL as requested
        
        about.set_authors(["Zenpad Developer Team"])
        about.set_documenters(["Zenpad Documentation Team"])
        about.set_artists(["Zenpad Design Team"])
        
        about.set_license_type(Gtk.License.GPL_2_0)
        
        about.set_logo_icon_name("accessories-text-editor")

        # Fix for WSL/Environments where gtk_show_uri fails
        def on_activate_link(dialog, uri):
            import webbrowser
            import platform
            import subprocess
            
            # WSL Detection
            is_wsl = "microsoft" in platform.uname().release.lower()
            
            try:
                if is_wsl:
                    # Force opening in Windows default browser
                    # converting URI to avoid shell injection if possible, but start expects a string
                    subprocess.run(["cmd.exe", "/c", "start", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                else:
                    webbrowser.open(uri)
                    return True
            except Exception as e:
                print(f"Failed to open link: {e}")
                return False
        
        about.connect("activate-link", on_activate_link)
        
        about.run()
        about.destroy()

    def on_toggle_comment(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
             editor = self.notebook.get_nth_page(page_num)
             editor.toggle_comment()

    def on_reopen_tab(self, widget):
        if self.closed_tabs:
            path, cursor = self.closed_tabs.pop()
            if os.path.exists(path):
                # Check if already open
                n_pages = self.notebook.get_n_pages()
                for i in range(n_pages):
                    editor = self.notebook.get_nth_page(i)
                    if editor.file_path == path:
                        self.notebook.set_current_page(i)
                        return
                
                # Open it
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.add_tab(content, os.path.basename(path), path)
            else:
                print(f"File not found: {path}")

    def on_insert_date(self, widget):
        import datetime
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            editor.buffer.insert_at_cursor(text)

    def on_join_lines(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
             editor = self.notebook.get_nth_page(page_num)
             buff = editor.buffer
             if buff.get_has_selection():
                 start, end = buff.get_selection_bounds()
                 text = buff.get_text(start, end, True)
                 new_text = " ".join([line.strip() for line in text.splitlines()])
                 buff.begin_user_action()
                 buff.delete(start, end)
                 buff.insert(start, new_text)
                 buff.end_user_action()

    def on_sort_lines(self, widget):
        self._modify_selected_lines(lambda lines: sorted(lines))

    def on_quick_open_action(self, action, param):
        dialog = QuickOpenDialog(self)
        dialog.run()


    def on_trim_whitespace(self, widget):
         self._modify_all_lines(lambda line: line.rstrip())

    # --- Analysis / Tools Handlers ---
    def on_format_json(self, action, parameter):
        self._run_formatter(analysis.format_json, "JSON")

    def on_format_xml(self, action, parameter):
        self._run_formatter(analysis.format_xml, "XML")

    def on_convert_json(self, action, parameter):
        """Standard converter that makes a NEW TAB with the JSON"""
        import threading
        from gi.repository import GLib

        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        text = editor.get_text()
        
        # 1. JSON Detection with Override Option
        lang = editor.buffer.get_language()
        is_json_lang = (lang and "json" in lang.get_id())
        
        clean_text = text.strip()
        
        # Check if it looks like JSON
        is_actually_json = False
        if clean_text.startswith("{") or clean_text.startswith("["):
            try:
                json.loads(clean_text)
                is_actually_json = True
            except json.JSONDecodeError:
                is_actually_json = False
        
        # If JSON detected, ask user if they want to convert anyway
        if is_actually_json:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Source appears to be valid JSON"
            )
            dialog.format_secondary_text(
                "This content is already valid JSON. Do you want to re-parse it as logs anyway?"
            )
            response = dialog.run()
            dialog.destroy()
            
            if response != Gtk.ResponseType.YES:
                return

        text = editor.get_text()
        
        # Show busy state (simple indicator)
        # self.header.get_custom_title().set_subtitle("Converting...") # If we had one
        
        def run_conversion():
            success, result, error = analysis.convert_to_json(text)
            GLib.idle_add(complete_conversion, success, result, error)

        def complete_conversion(success, result, error):
            if success:
                 # Open in new tab
                 src_name = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
                 new_editor = self.add_tab(result, f"JSON: {src_name}")
                 
                 # Force language to JSON immediately to prevent race conditions
                 # This ensures the recursion guard works instantly for the next click
                 manager = GtkSource.LanguageManager.get_default()
                 json_lang = manager.get_language("json")
                 if json_lang and new_editor:
                     new_editor.buffer.set_language(json_lang)
                     
            else:
                 self.show_error(f"Failed to convert: {error}")
        
        # Run in thread
        thread = threading.Thread(target=run_conversion)
        thread.daemon = True
        thread.start()

    def _run_formatter(self, func, name):
        """Helper to run a formatter on selection or whole file"""
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        buff = editor.buffer
        
        # Check selection
        has_sel = buff.get_has_selection()
        if has_sel:
            start, end = buff.get_selection_bounds()
            text = buff.get_text(start, end, True)
        else:
            start, end = buff.get_start_iter(), buff.get_end_iter()
            text = buff.get_text(start, end, True)
            
        success, result, error = func(text)
        
        if success:
            buff.begin_user_action()
            buff.delete(start, end)
            buff.insert(start, result)
            buff.end_user_action()
        else:
            self.show_error(f"Failed to format {name}: {error}")

    def on_hex_view(self, action, parameter):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        
        # Get content (might be binary-ish text)
        text = editor.get_text()
        
        # Generate Dump
        hex_dump = analysis.generate_hex_dump(text)
        
        # Create Title
        src_name = os.path.basename(editor.file_path) if editor.file_path else "Untitled"
        title = f"Hex: {src_name}"
        
        # Open in New Tab
        new_editor = self.add_tab(hex_dump, title)
        
        # Set Read-Only and Monospace
        new_editor.view.set_editable(False)
        # Maybe set a simpler highlighting or none
        new_editor.buffer.set_language(None)
    def on_calculate_hash(self, action, parameter):
        page_num = self.notebook.get_current_page()
        if page_num == -1: return
        editor = self.notebook.get_nth_page(page_num)
        buff = editor.buffer
        
        # Get content (Selection or Whole Doc)
        if buff.get_has_selection():
            start, end = buff.get_selection_bounds()
            text = buff.get_text(start, end, True)
            target_desc = "Selected Text"
        else:
            text = editor.get_text()
            target_desc = "Document"
            
        hashes = analysis.calculate_hashes(text)
        
        # Build Dialog
        dialog = Gtk.Dialog(title="Hash Calculator", transient_for=self, flags=0)
        dialog.add_buttons("Close", Gtk.ResponseType.CLOSE)
        
        content_area = dialog.get_content_area()
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        
        row = 0
        
        # Header
        lbl_info = Gtk.Label(label=f"<b>Hashes for {target_desc}</b>")
        lbl_info.set_use_markup(True)
        lbl_info.set_halign(Gtk.Align.START)
        grid.attach(lbl_info, 0, row, 2, 1)
        row += 1
        
        # Algo Rows
        for algo, val in hashes.items():
            lbl_algo = Gtk.Label(label=f"<b>{algo}:</b>")
            lbl_algo.set_use_markup(True)
            lbl_algo.set_halign(Gtk.Align.END)
            
            entry = Gtk.Entry()
            entry.set_text(val)
            entry.set_editable(False)
            entry.set_width_chars(64) # Enough for SHA256 hex
            
            grid.attach(lbl_algo, 0, row, 1, 1)
            grid.attach(entry, 1, row, 1, 1)
            row += 1
            
        content_area.add(grid)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def on_transform_text(self, mode):
        """Helper to run text transformation"""
        self._run_formatter(lambda text: analysis.transform_text(text, mode), mode)

    def on_markdown_preview(self, action, parameter):
        if not markdown_preview:
            cmd = "sudo apt install gir1.2-webkit2-4.1 python3-markdown"
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Markdown Preview Dependency Missing"
            )
            dialog.format_secondary_text(f"Please install dependencies.\n\nCommand:\n{cmd}")
            
            # Add Copy Button
            dialog.add_button("Copy Command", 101)
            
            response = dialog.run()
            if response == 101:
                clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                clipboard.set_text(cmd, -1)
                
            dialog.destroy()
            return

        if self.md_window and self.md_window.is_visible():
            self.md_window.present()
        else:
            self.md_window = markdown_preview.MarkdownPreviewWindow(self)
            self.md_window.show_all()
            # Initial Update
            page_num = self.notebook.get_current_page()
            if page_num != -1:
                editor = self.notebook.get_nth_page(page_num)
                self.md_window.update_content(editor.get_text())

    def on_buffer_changed(self, editor):
        """Called when any buffer changes content"""
        # Only update if preview is open AND the changed buffer is the ACTIVE one
        if self.md_window and self.md_window.is_visible():
            page_num = self.notebook.get_current_page()
            if page_num != -1:
                active_editor = self.notebook.get_nth_page(page_num)
                if active_editor == editor:
                    self.md_window.update_content(editor.get_text())

    def on_compare_tabs(self, action, parameter):
        current_page = self.notebook.get_current_page()
        if current_page == -1: return
        
        # Gather Tab Titles
        n_pages = self.notebook.get_n_pages()
        titles = []
        for i in range(n_pages):
            editor = self.notebook.get_nth_page(i)
            name = os.path.basename(editor.file_path) if editor.file_path else f"Untitled {i+1}"
            titles.append(name)
            
        dialog = diff_viewer.DiffDialog(self, current_page, titles)
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            other_idx = dialog.get_selected_page_index()
            if other_idx != -1:
                # Get Content
                curr_editor = self.notebook.get_nth_page(current_page)
                other_editor = self.notebook.get_nth_page(other_idx)
                
                text_a = other_editor.get_text()
                name_a = titles[other_idx]
                
                text_b = curr_editor.get_text()
                name_b = titles[current_page]
                
                # Generate Diff (Other -> Current)
                diff_text = diff_viewer.generate_diff(text_a, text_b, name_a, name_b)
                
                if not diff_text:
                    diff_text = f"Files {name_a} and {name_b} are identical."
                
                # Open Result
                new_editor = self.add_tab(diff_text, f"Diff: {name_a} vs {name_b}")
                new_editor.view.set_editable(False)
                
                # Try setting 'diff' language
                lang = GtkSource.LanguageManager.get_default().get_language("diff")
                if lang:
                    new_editor.buffer.set_language(lang)
                    
        dialog.destroy()

    def on_toggle_comment(self, widget):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            
            # Simple Comment Map
            lang = editor.buffer.get_language()
            comment_char = "#"
            if lang:
                lid = lang.get_id()
                if lid in ["c", "cpp", "java", "javascript", "css", "c-sharp"]:
                    comment_char = "//"
                elif lid in ["html", "xml"]:
                    comment_char = "<!--" # Partial support...
                elif lid == "sql":
                    comment_char = "--"
            
            self._modify_selected_lines(lambda lines: self._toggle_comment_lines(lines, comment_char))

    def _toggle_comment_lines(self, lines, char):
        new_lines = []
        for line in lines:
            if line.strip().startswith(char):
                # Uncomment - Naive
                new_lines.append(line.replace(char, "", 1))
            else:
                new_lines.append(char + " " + line)
        return new_lines

    def _modify_selected_lines(self, func):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            
            start, end = buff.get_selection_bounds() if buff.get_has_selection() else (buff.get_start_iter(), buff.get_end_iter()) 
            
            # If no selection, select current line
            if not buff.get_has_selection():
                 insert = buff.get_insert()
                 iter_curr = buff.get_iter_at_mark(insert)
                 start = buff.get_iter_at_line(iter_curr.get_line())
                 end = start.copy()
                 end.forward_to_line_end()
            
            # Extend to line starts/ends
            if not start.starts_line():
                start.set_line(start.get_line())
            if not end.ends_line():
                end.forward_to_line_end()
                
            text = buff.get_text(start, end, True)
            lines = text.splitlines(keepends=True)
            
            lines_stripped = text.splitlines()
            processed = func(lines_stripped)
            new_text = "\n".join(processed)
            if text.endswith("\n") and not new_text.endswith("\n"):
                 new_text += "\n"
            
            buff.begin_user_action()
            buff.delete(start, end)
            buff.insert(start, new_text)
            buff.end_user_action()

    def _modify_all_lines(self, func):
        page_num = self.notebook.get_current_page()
        if page_num != -1:
            editor = self.notebook.get_nth_page(page_num)
            buff = editor.buffer
            text = buff.get_text(buff.get_start_iter(), buff.get_end_iter(), True)
            lines = text.splitlines()
            processed = [func(l) for l in lines]
            new_text = "\n".join(processed)
            if text.endswith("\n"): new_text += "\n"
            
            buff.begin_user_action()
            buff.set_text(new_text)
            buff.end_user_action()

    def on_tab_button_press(self, widget, event, editor):
        if event.button == 3: # Right Click
            menu = Gtk.Menu()
            
            # Rename (Save As)
            rename_item = Gtk.MenuItem(label="Rename File...")
            rename_item.connect("activate", lambda w: self.save_file_as(editor))
            menu.append(rename_item)
            
            menu.append(Gtk.SeparatorMenuItem())
            
            # Close
            close_item = Gtk.MenuItem(label="Close Tab")
            close_item.connect("activate", lambda w: self.on_close_clicked(editor))
            menu.append(close_item)
            
            # Close Others
            close_others = Gtk.MenuItem(label="Close Other Tabs")
            close_others.connect("activate", lambda w: self.on_close_others(editor))
            menu.append(close_others)
            
            menu.append(Gtk.SeparatorMenuItem())
            
            # Copy Path
            copy_path = Gtk.MenuItem(label="Copy File Path")
            copy_path.connect("activate", lambda w: self.on_copy_path(editor))
            menu.append(copy_path)
            
            # Open Containing Folder
            open_folder = Gtk.MenuItem(label="Open Containing Folder")
            open_folder.connect("activate", lambda w: self.on_open_folder(editor))
            menu.append(open_folder)
            
            menu.show_all()
            menu.attach_to_widget(widget, None) # Associate with the EventBox
            
            # Use popup_at_pointer for better Wayland/GTK3.22+ support
            # Fallback to old popup if not available (rare in modern envs)
            if hasattr(menu, "popup_at_pointer"):
                menu.popup_at_pointer(event)
            else:
                menu.popup(None, None, None, None, event.button, event.time)
            
            return True
        return False

    def on_close_others(self, target_editor):
        n_pages = self.notebook.get_n_pages()
        # Iterate backwards to avoid index shifting issues
        for i in range(n_pages - 1, -1, -1):
            editor = self.notebook.get_nth_page(i)
            if editor != target_editor:
                if self.check_unsaved_changes(editor):
                    self.close_tab(i)

    def on_copy_path(self, editor):
        if editor.file_path:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(editor.file_path, -1)
        else:
            print("No file path to copy")

    def on_open_folder(self, editor):
        if editor.file_path:
            folder = os.path.dirname(editor.file_path)
            if os.path.exists(folder):
                try:
                    # Generic open for Linux/Windows/Mac
                    if os.name == 'nt':
                        os.startfile(folder)
                    else:
                        subprocess = __import__('subprocess')
                        opener = 'xdg-open'
                        subprocess.call([opener, folder])
                except Exception as e:
                     print(f"Error opening folder: {e}")

    def goto_line(self, editor, line, column=0):
        try:
            buff = editor.buffer
            if line < 1: line = 1
            iter_ = buff.get_iter_at_line(line - 1)
            if column:
                iter_.forward_chars(int(column))
            buff.place_cursor(iter_)
            editor.view.scroll_to_iter(iter_, 0.0, True, 0.5, 0.5)
            editor.view.grab_focus()
        except Exception as e:
            print(f"Error going to line: {e}")

    def get_icon_name_for_language(self, lang_id):
        """Maps GtkSourceView language ID to standard icon name."""
        if not lang_id: return "text-x-generic"
        
        # Map common IDs to icon names (Adwaita/Tango/Standard)
        # Using mimetypes and standard freedesktop icon names
        mapping = {
            # Common Languages
            "python": "text-x-python",
            "c": "text-x-csrc",
            "cpp": "text-x-c++src", 
            "chdr": "text-x-chdr",
            "java": "text-x-java",
            "js": "text-x-javascript",
            "javascript": "text-x-javascript",
            "json": "application-json",
            "xml": "text-xml",
            "html": "text-html",
            "css": "text-css",
            "sh": "text-x-script",
            "bash": "application-x-shellscript",
            "markdown": "text-markdown",
            # Additional Languages
            "ruby": "application-x-ruby",
            "go": "text-x-go",
            "rust": "text-x-rust",
            "haskell": "text-x-haskell",
            "commonlisp": "text-x-lisp",
            "scheme": "text-x-scheme",
            "lisp": "text-x-lisp",
            "nasm": "text-x-asm",
            "asm": "text-x-asm",
            "gas": "text-x-asm",
            "php": "application-x-php",
            "typescript": "text-x-typescript",
            "tsx": "text-x-typescript",
            "jsx": "text-x-javascript",
            "sql": "text-x-sql",
            "lua": "text-x-lua",
            "perl": "application-x-perl",
            "r": "text-x-r",
            "swift": "text-x-swift",
            "kotlin": "text-x-kotlin",
            "scala": "text-x-scala",
            "yaml": "text-x-yaml",
            "toml": "text-x-toml",
            "dockerfile": "text-x-dockerfile",
            "makefile": "text-x-makefile",
            "cmake": "text-x-cmake",
        }
        
        return mapping.get(lang_id, "text-x-generic")


class QuickOpenDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Quick Open", transient_for=parent, flags=0)
        self.set_default_size(500, 300)
        self.set_modal(True)
        
        self.parent_window = parent
        self.all_files = []
        
        # UI Setup
        box = self.get_content_area()
        box.set_spacing(5)
        
        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Type to search files...")
        self.search_entry.set_size_request(300, -1)  # Fix GTK warning about negative dimensions
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_activated) # Enter key
        box.pack_start(self.search_entry, False, False, 0)
        
        # Scrolled List
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(250)
        
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self.on_row_activated)
        scrolled.add(self.listbox)
        
        box.pack_start(scrolled, True, True, 0)
        
        self.show_all()
        
        # Populate Async-ish (on init)
        self.populate_files()
        
    def populate_files(self):
        # Recursively find files in CWD
        cwd = os.getcwd()
        exclude_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.gemini'}
        
        # This could be slow for huge repos, but fine for now
        # Ideally should be done in a thread, but keep it simple for v1.3.0
        for root, dirs, files in os.walk(cwd):
            # Prune exclusions
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, cwd)
                self.all_files.append((rel_path, full_path))
        
        # Initial populate (limit to 50?)
        self.refresh_list("")

    def refresh_list(self, query):
        # Clear existing
        for child in self.listbox.get_children():
            self.listbox.remove(child)
            
        query = query.lower()
        count = 0
        limit = 30
        
        for rel_path, full_path in self.all_files:
            if count >= limit: break
            
            if not query or query in rel_path.lower():
                row = Gtk.ListBoxRow()
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                box.set_spacing(10)
                
                label = Gtk.Label(label=rel_path)
                label.set_xalign(0)
                box.pack_start(label, True, True, 0)
                
                # Dim label for full path? No, simple is better.
                
                row.add(box)
                row.file_path = full_path # Store specific data on row
                self.listbox.add(row)
                count += 1
                
        self.listbox.show_all()
        # Select first result if any
        if self.listbox.get_children():
            self.listbox.select_row(self.listbox.get_children()[0])

    def on_search_changed(self, entry):
        self.refresh_list(entry.get_text())

    def on_activated(self, entry):
        row = self.listbox.get_selected_row()
        if row:
            self.open_file(row.file_path)

    def on_row_activated(self, listbox, row):
        self.open_file(row.file_path)

    def open_file(self, path):
        self.parent_window.open_file_from_path(path)
        self.destroy()
