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
            
        return "\n".join(result)
    except Exception as e:
        return f"Error generating hex dump: {e}"
