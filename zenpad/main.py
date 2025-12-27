import sys
import argparse
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
        # args[0] is program name
        
        parser = argparse.ArgumentParser(prog="zenpad", description="Zenpad Text Editor")
        parser.add_argument("files", nargs="*", help="Files to open")
        parser.add_argument("-v", "--version", action="store_true", help="Print version information and exit")
        parser.add_argument("-q", "--quit", action="store_true", help="Quit the running instance")
        parser.add_argument("-l", "--line", type=int, help="Jump to specific line number")
        parser.add_argument("-c", "--column", type=int, help="Jump to specific column number")
        
        # Parse arguments (skip program name)
        try:
            parsed_args = parser.parse_args(args[1:])
        except SystemExit:
            # argparse calls sys.exit() on error or help, we just want to return
            return 0
            
        if parsed_args.version:
            print("Zenpad v1.0.0")
            return 0
            
        if parsed_args.quit:
            self.quit()
            return 0

        self.activate()
        

        # Open Files
        if parsed_args.files:
            for filename in parsed_args.files:
                self.window.open_file_from_path(filename, line=parsed_args.line, column=parsed_args.column)

        return 0

def main():
    app = ZenpadApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    sys.exit(main())
