import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('WebKit2', '4.1')
except ValueError:
    try:
        gi.require_version('WebKit2', '4.0')
    except ValueError:
        raise ImportError("WebKit2 (gir1.2-webkit2-4.1 or 4.0) not found")

from gi.repository import Gtk, Gdk, WebKit2, GLib
import markdown

class MarkdownPreviewWindow(Gtk.Window):
    def __init__(self, parent=None):
        super().__init__(title="Markdown Preview")
        self.set_default_size(800, 600)
        self.set_transient_for(parent)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY) if parent else None
        
        # WebView Settings (Disable JS for security)
        self.webview = WebKit2.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_javascript(False)
        settings.set_enable_write_console_messages_to_stdout(False)
        
        # Scrolled Window
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.webview)
        self.add(scrolled)
        
        self.show_all()
        
        # CSS Style (GitHub-like)
        self.css = """
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            padding: 32px; 
            line-height: 1.6; 
            color: #24292e; 
            max-width: 900px;
            margin: 0 auto;
        }
        pre { 
            background: #f6f8fa; 
            padding: 16px; 
            border-radius: 6px; 
            overflow-x: auto; 
            line-height: 1.45;
        }
        code { 
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; 
            background: rgba(27,31,35,0.05); 
            padding: 0.2em 0.4em; 
            border-radius: 3px; 
            font-size: 85%;
        }
        pre code { background: transparent; padding: 0; font-size: 100%; }
        h1, h2, h3, h4, h5, h6 { 
            color: #24292e; 
            margin-top: 24px; 
            margin-bottom: 16px; 
            font-weight: 600; 
            line-height: 1.25; 
        }
        h1, h2 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        blockquote { 
            border-left: 4px solid #dfe2e5; 
            padding: 0 1em; 
            color: #6a737d; 
            margin: 0;
        }
        ul, ol { 
            padding-left: 2em; 
            margin-top: 0; 
            margin-bottom: 16px; 
        }
        ul { list-style-type: disc; }
        ol { list-style-type: decimal; }
        li { margin-bottom: 4px; }
        li > p { margin-top: 16px; }
        
        strong { font-weight: 600; color: #24292e; }
        em { font-style: italic; }
        
        table { border-collapse: collapse; width: 100%; margin-top: 1em; margin-bottom: 1em; }
        th, td { border: 1px solid #dfe2e5; padding: 6px 13px; }
        th { background-color: #f6f8fa; font-weight: 600; }
        tr:nth-child(2n) { background-color: #f8f8f8; }
        img { max-width: 100%; box-sizing: content-box; background-color: #fff; }
        hr { border: 0; border-top: 1px solid #dfe2e5; margin: 24px 0; }
        
        /* Dark Mode Support */
        @media (prefers-color-scheme: dark) {
            body { background-color: #0d1117; color: #c9d1d9; }
            h1, h2, h3, h4, h5, h6 { color: #c9d1d9; border-color: #30363d; }
            strong { color: #c9d1d9; }
            a { color: #58a6ff; }
            pre { background-color: #161b22; }
            code { background-color: rgba(110,118,129,0.4); }
            pre code { background: transparent; }
            blockquote { border-color: #30363d; color: #8b949e; }
            table { color: #c9d1d9; }
            th, td { border-color: #30363d; }
            th { background-color: #161b22; }
            tr:nth-child(2n) { background-color: #161b22; }
            hr { border-color: #30363d; }
        }
        """

    def update_content(self, text):
        # Use 'extra' extension for improved list handling, tables, etc.
        html_body = markdown.markdown(text, extensions=['extra', 'codehilite', 'sane_lists'])
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self.css}</style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        self.webview.load_html(full_html, None)
