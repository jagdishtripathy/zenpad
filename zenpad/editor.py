import gi
import hashlib
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('GtkSource', '4')
except ValueError:
    gi.require_version('GtkSource', '3.0')
from gi.repository import Gtk, GtkSource, Pango, Gdk
from zenpad import analysis

class EditorTab(Gtk.ScrolledWindow):
    def __init__(self, search_settings=None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.buffer = GtkSource.Buffer()
        self.last_buffer = None
        self.view = GtkSource.View.new_with_buffer(self.buffer)
        
        self.file_path = None
        
        # Connect to changed signal for auto-detection
        self.buffer.connect("changed", self.on_buffer_changed)
        
        # Search Context
        self.search_context = None
        if search_settings:
            self.search_context = GtkSource.SearchContext.new(self.buffer, search_settings)
            self.search_context.set_highlight(True)
        
        # Default Settings
        self.view.set_show_line_numbers(True)
        self.view.set_auto_indent(True)
        self.view.set_indent_on_tab(True) # Indent on Tab key
        if hasattr(self.view, "set_smart_backspace"):
            self.view.set_smart_backspace(True) # Unindent on Backspace
        self.view.set_indent_width(-1) # Use tab width for indent width
        
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
        
        # Handle smart indentation on Enter
        self.view.connect("key-press-event", self.on_key_press)

        self.add(self.view)
        self.show_all()

    def on_buffer_changed(self, buffer):
        """Triggers reliable auto-detection on content change"""
        # We only auto-detect if we don't have a rigid file path override
        # Or should we always? User said "Decouple from save state".
        # Let's run it.
        self.auto_detect_language()

    def auto_detect_language(self):
        # Limit to detecting from the first 1000 chars for speed
        start = self.buffer.get_start_iter()
        end = self.buffer.get_start_iter()
        end.forward_chars(1000)
        text = self.buffer.get_text(start, end, True)
        
        detected_id = analysis.detect_language_by_content(text)
        
        if detected_id:
            manager = GtkSource.LanguageManager.get_default()
            language = manager.get_language(detected_id)
            current_lang = self.buffer.get_language()
            
            # Only switch if different, to avoid thrashing
            if language and current_lang != language:
                self.buffer.set_language(language)

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
        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
            return False

        good, dx, dy = event.get_scroll_deltas()

        if (dy < 0.0):
            self.zoom_in()
        elif (dy > 0.0):
            self.zoom_out()

        return True

    def on_key_press(self, widget, event):
        """
        Handles smart indentation on Enter key.
        Global logic:
        - Check previous line indentation.
        - Check for openers: {, [, (, :
        - Increase indent if opener found.
        """
        # Respect Read-Only
        if not self.view.get_editable():
            return False

        keyval = event.keyval
        if keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            if (event.state & Gdk.ModifierType.SHIFT_MASK) or (event.state & Gdk.ModifierType.CONTROL_MASK):
                if event.state & Gdk.ModifierType.SHIFT_MASK and keyval == Gdk.KEY_Return:
                    pass # Allow Shift+Enter
                elif keyval not in [Gdk.KEY_quotedbl, Gdk.KEY_apostrophe]:
                     return False # Allow other modified keys

        # Auto-Close Quotes
        if keyval in [Gdk.KEY_quotedbl, Gdk.KEY_apostrophe]:
             # Only strictly auto-close if no selection? For now simple implementation.
             buff = self.buffer
             quote_char = '"' if keyval == Gdk.KEY_quotedbl else "'"
             
             # Insert the pair
             buff.insert_at_cursor(quote_char + quote_char)
             
             # Move cursor back by 1
             insert = buff.get_insert()
             iter_cur = buff.get_iter_at_mark(insert)
             iter_cur.backward_char()
             buff.place_cursor(iter_cur)
             
             return True # Stop default handler (which would insert single char)

        if keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            if (event.state & Gdk.ModifierType.SHIFT_MASK) or (event.state & Gdk.ModifierType.CONTROL_MASK):
                return False
                
            buff = self.buffer
            lang = buff.get_language()
            lang_id = lang.get_id() if lang else None
            
            # User Requirement: No language = no smart indentation?
            # actually, users want smart features even in Untitled buffers if they type code.
            # So we allow None to fall through to structural checks.
            # if not lang_id: return False <- REMOVED
            
            insert = buff.get_insert()
            iter_cur = buff.get_iter_at_mark(insert)
            
            # Get current line text up to cursor
            line_num = iter_cur.get_line()
            iter_start = buff.get_iter_at_line(line_num)
            line_text = buff.get_text(iter_start, iter_cur, False)
            
            # Calculate current indentation
            indentation = ""
            for char in line_text:
                if char in [' ', '\t']:
                    indentation += char
                else:
                    break
            
            # Check for structural openers at the end of the text (ignoring trailing whitespace)
            stripped = line_text.strip()
            should_indent = False
            
            # Check for Enter between braces: {|} -> Expand
            # Need to peek at the character *after* the cursor
            char_after = ""
            if not iter_cur.is_end():
                iter_next = iter_cur.copy()
                iter_next.forward_char()
                char_after = buff.get_text(iter_cur, iter_next, False)
            
            is_expansion = False
            
            # Language-Aware Logic
            if stripped:
                # Group 1: BRACE/BLOCK Languages (C-like, Python, JSON, JS, AND Untitled/None)
                # We assume generic brace behavior for Plain Text (None)
                brace_langs = ["python", "c", "cpp", "chdr", "java", "js", "javascript", "json", "css", "rust", "go", "text"]
                
                is_brace_lang = (lang_id is None) or (lang_id in brace_langs) or ("json" in lang_id) or ("python" in lang_id) or (lang_id == "text")
                
                if is_brace_lang:
                    last_char = stripped[-1]
                    if last_char in ['{', '[', '(', ':']:
                        should_indent = True
                        
                        # Check for expansion: {|} or [|]
                        if last_char == '{' and char_after == '}': is_expansion = True
                        if last_char == '[' and char_after == ']': is_expansion = True
                        if last_char == '(' and char_after == ')': is_expansion = True
                
                # Group 2: SHELL (Bash) - Strict Check
                if lang_id in ["sh", "bash", "zsh", "application-x-shellscript"]:
                    tokens = stripped.split()
                    if tokens:
                        last = tokens[-1]
                        if last in ["then", "do", "else", "elif"]:
                            should_indent = True
                            
                # Group 3: TAG Languages (HTML, XML)
                tag_langs = ["xml", "html", "markdown", "php"]
                if lang_id in tag_langs:
                    if stripped.endswith(">") and not stripped.endswith("/>") and not stripped.endswith("?>") and not stripped.endswith("-->"):
                        # Check against closing tag
                        r_index = stripped.rfind("<")
                        if r_index != -1:
                            tag_content = stripped[r_index:]
                            if not tag_content.startswith("</"):
                                should_indent = True
                                # XML expansion <t>|</t> ?
                                # Complex to check char_after for </tag> without parsing.
                                # Leaving XML expansion simple for now.

            # Construct insertion
            to_insert = "\n" + indentation
            
            indent_str = ""
            tab_width = self.view.get_tab_width()
            if self.view.get_insert_spaces_instead_of_tabs():
                 indent_str = " " * tab_width
            else:
                 indent_str = "\t"

            if should_indent:
                 to_insert += indent_str
            
            if is_expansion:
                # We are expanding {|} to:
                # {
                #     |
                # }
                # indentation holds the BASE indent (of the { line)
                # to_insert holds \n + BASE + INDENT
                
                # We need to append: \n + BASE + (closing brace)
                # But wait, we are inserting AT cursor.
                # So we insert: \n + BASE + INDENT + \n + BASE
                # And assume the } is already there (char_after).
                # Wait, if we insert text, the } moves.
                
                second_line = "\n" + indentation
                to_insert += second_line
                
                # Insert
                buff.begin_user_action()
                buff.insert(iter_cur, to_insert)
                buff.end_user_action()
                
                # Now we need to move cursor UP one line and to the end of that line
                # (which is the indented position)
                
                # Current pos is after the inserted text (before the })
                insert_mark = buff.get_insert()
                iter_final = buff.get_iter_at_mark(insert_mark)
                iter_final.backward_chars(len(second_line)) # Go back before the closing indentation
                
                buff.place_cursor(iter_final)
                
            else:
                # Standard Indent
                buff.begin_user_action()
                buff.insert(iter_cur, to_insert)
                buff.end_user_action()
                self.view.scroll_to_mark(insert, 0.0, True, 0.0, 0.5)

            return True

        # Electric Brace Dedentation & Type-Over ( } ] ) )
        if keyval in [Gdk.KEY_braceright, Gdk.KEY_bracketright, Gdk.KEY_parenright]:
            buff = self.buffer
            insert = buff.get_insert()
            iter_cur = buff.get_iter_at_mark(insert)
            
            # Type-Over Logic: If next char is the one we are typing, just move cursor
            # Get char at cursor
            char_at_cursor = buff.get_text(iter_cur, buff.get_iter_at_offset(iter_cur.get_offset() + 1), False)
            typed_char = chr(Gdk.keyval_to_unicode(keyval))
            
            if char_at_cursor == typed_char:
                # Move cursor forward instead of typing
                iter_cur.forward_char()
                buff.place_cursor(iter_cur)
                return True

            # Dedentation Logic
            # Enable for Brace Langs AND Untitled (None)
            lang = buff.get_language()
            lang_id = lang.get_id() if lang else None
            
            is_brace_lang = (lang_id is None) or (lang_id in ["python", "c", "cpp", "chdr", "java", "js", "javascript", "json", "css", "rust", "go", "text"]) or ("json" in str(lang_id)) or ("python" in str(lang_id)) 
                     
            if is_brace_lang:
                line_num = iter_cur.get_line()
                iter_start = buff.get_iter_at_line(line_num)
                line_text = buff.get_text(iter_start, iter_cur, False)
                
                # Only dedent if line is currently pure whitespace (we are closing a block)
                if len(line_text.strip()) == 0 and len(line_text) > 0:
                     tab_width = self.view.get_tab_width()
                     if len(line_text) >= tab_width:
                         start_del = iter_cur.copy()
                         start_del.backward_chars(tab_width)
                         buff.begin_user_action()
                         buff.delete(start_del, iter_cur)
                         buff.end_user_action()
            return False

        # Auto-Pairing for Openers ( { [ ( )
        if keyval in [Gdk.KEY_braceleft, Gdk.KEY_bracketleft, Gdk.KEY_parenleft]:
            buff = self.buffer
            lang = buff.get_language()
            lang_id = lang.get_id() if lang else None
            
            # Apply generically for Code AND Untitled
            # Avoid smart pairing only if user explicitly wants plain text behavior? 
            # Zenpad seems to aim for "Smart Text Editor", so enabling by default for Untitled is safer for UX.
            
            should_pair = (lang_id is None) or (lang_id != "markdown") # Maybe exclude prose heavy? 
            # Actually, standard VSCode pairs in markdown too usually.
            
            insert = buff.get_insert()
            iter_cur = buff.get_iter_at_mark(insert)
            
            mapping = {
                Gdk.KEY_braceleft: "{}",
                Gdk.KEY_bracketleft: "[]",
                Gdk.KEY_parenleft: "()"
            }
            
            pair = mapping.get(keyval)
            if pair:
                buff.begin_user_action()
                buff.insert_at_cursor(pair)
                buff.end_user_action()
                
                # Move cursor back one step
                insert = buff.get_insert()
                iter_back = buff.get_iter_at_mark(insert)
                iter_back.backward_char()
                buff.place_cursor(iter_back)
                return True
            
        return False
