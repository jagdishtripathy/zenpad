import sys
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '4')

from gi.repository import Gtk, Gio
from .window import ZenpadWindow

class ZenpadApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.zenpad.editor",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        Gtk.Window.set_default_icon_name("accessories-text-editor")

    def do_activate(self):
        if not self.window:
            self.window = ZenpadWindow(application=self)
        self.window.present()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        
        # Check for quit flag
        if len(args) > 1 and args[1] in ["--quit", "-q"]:
            self.quit()
            return 0

        # Check for version flag
        if len(args) > 1 and args[1] in ["--version", "-v"]:
            print("Zenpad v1.0.0")
            return 0

        self.activate()
        
        # Args[0] is usually the program name, files follow~
        if len(args) > 1:
            for filename in args[1:]:
                # We need to tell the window to open this file
                # Since window logic for opening is inside ZenpadWindow, we'll expose a method or reuse on_open_file logic
                # But on_open_file is UI driven. 
                # Ideally ZenpadWindow has an open_file(path) method.
                # Let's check window.py again, add_tab exists.
                self.window.open_file_from_path(filename)
                
        return 0

def main():
    app = ZenpadApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    sys.exit(main())
