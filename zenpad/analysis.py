import json
import xml.dom.minidom
import binascii
import re
import csv
import io

def format_json(text):
    """
    Formats a JSON string with 4-space indentation.
    Returns: (success: bool, content: str, error: str)
    """
    try:
        if not text.strip():
            return False, "", "Empty selection"
        
        parsed = json.loads(text)
        formatted = json.dumps(parsed, indent=4)
        return True, formatted, None
    except json.JSONDecodeError as e:
        return False, "", f"Invalid JSON: {e}"

def convert_to_json(text):
    """
    Converter that transforms Web Access Logs into JSON.
    Strictly parses Common Log Format (Combined).
    Fallback: Wraps lines into JSON objects.
    """
    text = text.strip()
    if not text:
        return False, "", "Empty text"

    lines = text.splitlines()
    
    # Strategy: Web Access Logs (Regex)
    # Common Log Format (Combined): IP - - [Date] "Request" Status Size "Referer" "UA"
    # Regex Breakdown:
    # ^(\S+)            IP
    # \s\S+\s\S+\s      Ident Auth (skip)
    # \[(.*?)\]         Timestamp
    # \s"(.*?)"         Request (Method Path Proto)
    # \s(\d{3})         Status
    # \s(\S+)           Size
    # \s"(.*?)"         Referer
    # \s"(.*?)"         User Agent
    
    log_pattern = re.compile(r'^(\S+)\s\S+\s\S+\s\[(.*?)\]\s"(.*?)"\s(\d{3})\s(\S+)\s"(.*?)"\s"(.*?)"')
    
    # We attempt to parse assuming it is a log file. 
    # If the first few lines don't match, we might want to fallback immediately, 
    # but the user requested strict line-by-line parsing.
    
    logs = []
    # Check if it looks like a log file at all? 
    # Actually, we will just try to parse every line. Matches get structured, others get _raw.
    
    # Optimization: Check match on first non-empty line
    first_line = next((l for l in lines if l.strip()), "")
    is_log_format = bool(log_pattern.match(first_line))
    
    if is_log_format:
        for line in lines:
            line = line.strip()
            if not line: continue
            
            match = log_pattern.match(line)
            if match:
                g = match.groups()
                # Parse Request
                req_str = g[2]
                method, path, proto = "UNKNOWN", req_str, ""
                if " " in req_str:
                    parts = req_str.split()
                    if len(parts) >= 2:
                        method = parts[0]
                        path = parts[1]
                
                entry = {
                    "ip": g[0],
                    "timestamp": g[1],
                    "method": method,
                    "path": path,
                    "status": int(g[3]),
                    "bytes": int(g[4]) if g[4].isdigit() else 0,
                    "referer": g[5],
                    "user_agent": g[6]
                }
                logs.append(entry)
            else:
                 logs.append({"_error": "Parse Failed", "_raw": line})
        return True, json.dumps(logs, indent=4), None

    # Fallback: Just wrap lines (User explicit request: "Logs must be parsed line-by-line")
    # If regex failed completely on first line, we assume it's generic text.
    fallback = [{"line": i+1, "content": line} for i, line in enumerate(lines)]
    return True, json.dumps(fallback, indent=4), None


def detect_language_by_content(text):
    """
    Analyzes text content to guess the programming language.
    Returns a GtkSourceView language ID or None.
    """
    text = text.strip()
    if not text:
        return None
        
    # 1. Shebang (Strongest Indicator)
    first_line = text.splitlines()[0]
    if first_line.startswith("#!"):
        if "python" in first_line: return "python"
        if "bash" in first_line or "sh" in first_line: return "sh"
        if "node" in first_line: return "js"
        if "perl" in first_line: return "perl"
        if "ruby" in first_line: return "ruby"

    # 2. JSON (Strict Structure)
    if (text.startswith("{") and text.endswith("}")) or \
       (text.startswith("[") and text.endswith("]")):
        # Quick check if it looks valid-ish
        try:
            # Check if it's purely empty brackets/braces (ignoring all whitespace)
            # text.strip() only handles ends. We need to handle internals (newlines, indent).
            
            # Simple check: remove all whitespace
            import string
            # faster than regex for simple check
            no_space = "".join(text.split())
            if no_space == "{}" or no_space == "[]":
                 # Ambiguous. Could be Python dict, JS block, C block, etc.
                 # Prefer avoiding JSON lock-in until we see data.
                 return None
                 
            json.loads(text)
            return "json"
        except:
             # Sometimes incomplete JSON is being typed
             # Heuristic: First line is { or [
             # Check for "Key": Value pattern to distinguish from C/JS blocks
             if text.startswith("{"):
                 if re.search(r'"[^"]*"\s*:', text):
                     return "json"
             # Arrays are ambiguous (Json vs Python), but often JSON is acceptable default if purely data
             elif text.startswith("["):
                 # If it looks like a list interaction
                 return "json"

    # 3. HTML / XML (Tags)
    if "<html" in text.lower() or "<!doctype html" in text.lower():
        return "html"
    if "<?xml" in text.lower():
        return "xml"
    
    # Generic XML check (Tags)
    # Look for at least one tag <tag> and maybe </tag>
    if "<" in text and ">" in text:
        # Avoid identifying C includes or comparisons like a < b
        # Check for standard XML tag pattern
        if re.search(r'<[a-zA-Z0-9_-]+.*?>', text):
             # Prefer HTML for common interactive/web tags even without body/div
             if "</body>" in text or "</div>" in text or "<script" in text or "<br" in text or "<p>" in text:
                 return "html"
             return "xml"
    
    # 4. Content Heuristics (Keywords)
    # We check the first ~1000 chars to avoid scanning massive files
    sample = text[:1000]
    
    # Python
    # Check for keywords OR characteristic indentation structures
    if "def " in sample and ":" in sample: return "python"
    if "class " in sample and ":" in sample: return "python"
    if "import " in sample and "from " in sample: return "python"
    if "import " in sample and "os " in sample: return "python"
    if "if __name__" in sample: return "python"
    
    # C / C++
    if "#include <" in sample: return "c"
    if "int main(" in sample and "{" in sample: return "c"
    if "std::" in sample or "cout <<" in sample: return "cpp"
        
    # JavaScript
    # Keywords often found in modern JS
    if "function " in sample and "{" in sample: return "js"
    if "const " in sample and "=" in sample: return "js"
    if "let " in sample and "=" in sample: return "js"
    if "console.log(" in sample: return "js"
    if "=>" in sample and ("const" in sample or "var" in sample): return "js"
    if "document.getElementById" in sample: return "js"
            
    # CSS
    if "body {" in sample or "div {" in sample or ".class" in sample:
        if "{" in sample and ":" in sample and ";" in sample:
            return "css"
    if "@media" in sample or "@import" in sample:
        return "css"

    # Bash (if no shebang)
    if "echo " in sample and ("if [" in sample or "fi" in sample or "sudo " in sample):
        return "sh"
    if "export " in sample and "=" in sample: return "sh"
    
    # Markdown (Titles)
    if sample.startswith("# ") or "\n# " in sample:
        if "## " in sample or "**" in sample:
             return "markdown"

    return None


def format_xml(text):
    """
    Formats an XML string with 2-space indentation.
    Returns: (success: bool, content: str, error: str)
    """
    try:
        if not text.strip():
            return False, "", "Empty selection"
            
        # Remove empty lines/whitespace between tags to ensure clean format
        # This is a naive cleanup to assist minidom
        cleaned = "".join(line.strip() for line in text.splitlines())
        
        parsed = xml.dom.minidom.parseString(cleaned)
        # toxml() doesn't format, toprettyxml() does
        # Standard minidom adds extra whitespace, so we strip lines then rejoin
        ugly = parsed.toprettyxml(indent="  ")
        
        # Cleanup minidom's aggressive whitespace
        lines = [line for line in ugly.splitlines() if line.strip()]
        formatted = "\n".join(lines)
        
        return True, formatted, None
    except Exception as e:
         return False, "", f"Invalid XML: {e}"

def generate_hex_dump(text):
    """
    Generates a canonical hex dump of the provided text (utf-8 bytes).
    Format: Offset | Hex Bytes | ASCII
    """
    try:
        data = text.encode("utf-8")
        result = []
        chunk_size = 16
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            
            # Offset
            offset = f"{i:08x}"
            
            # Hex
            hex_bytes = " ".join(f"{b:02x}" for b in chunk)
            padding = "   " * (chunk_size - len(chunk))
            
            # ASCII
            ascii_repr = ""
            for b in chunk:
                if 32 <= b <= 126:
                    ascii_repr += chr(b)
                else:
                    ascii_repr += "."
            
            result.append(f"{offset}  {hex_bytes}{padding}  |{ascii_repr}|")
            
    except Exception as e:
        return f"Error generating hex dump: {e}"

def calculate_hashes(text):
    """
    Calculates MD5, SHA1, SHA256, SHA512 hashes of the text.
    Returns: dict {algo_name: hex_digest}
    """
    import hashlib
    
    if not text:
        return {}
        
    data = text.encode("utf-8")
    
    results = {
        "MD5": hashlib.md5(data).hexdigest(),
        "SHA-1": hashlib.sha1(data).hexdigest(),
        "SHA-256": hashlib.sha256(data).hexdigest(),
        "SHA-512": hashlib.sha512(data).hexdigest()
    }
    return results

def transform_text(text, mode):
    """
    Transforms text based on the mode.
    Modes: base64_enc, base64_dec, url_enc, url_dec
    Returns: (success, result, error)
    """
    import base64
    import urllib.parse
    
    if not text:
        return True, "", None
        
    try:
        if mode == "base64_enc":
            # Encode -> bytes -> base64 bytes -> string
            encoded_bytes = base64.b64encode(text.encode("utf-8"))
            return True, encoded_bytes.decode("utf-8"), None
            
        elif mode == "base64_dec":
            # Decode -> base64 bytes -> bytes -> string
            decoded_bytes = base64.b64decode(text)
            return True, decoded_bytes.decode("utf-8"), None
            
        elif mode == "url_enc":
            return True, urllib.parse.quote(text), None
            
        elif mode == "url_dec":
            return True, urllib.parse.unquote(text), None
            
        return False, None, f"Unknown mode: {mode}"
        
    except Exception as e:
        return False, None, str(e)