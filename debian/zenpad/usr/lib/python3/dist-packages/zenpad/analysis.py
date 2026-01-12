import json
import xml.dom.minidom
import binascii
import re
import csv
import io
import datetime
import dataclasses
from typing import List, Dict, Optional, Any, Tuple

# --- Smart Log Engine (Phase 1) ---

@dataclasses.dataclass
class LogEntry:
    """ECS-compatible log event structure for SOC tools (Splunk/ELK/Wazuh)"""
    timestamp: str = ""         # @timestamp (ISO 8601)
    timestamp_raw: str = ""     # Original timestamp string
    source_type: str = ""       # Profile name (syslog, access, kernel, etc.)
    level: str = ""             # log.level
    message: str = ""           # Main content
    raw_log: str = ""           # Original line(s) preserved
    host: str = ""              # host.name
    program: str = ""           # process.name / app
    pid: str = ""               # process.pid
    # Additional fields for specific log types
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_ecs_dict(self) -> Dict[str, Any]:
        """Output flat ECS-compatible dict (only non-empty fields, raw_log last)"""
        result = {}
        # Core fields first
        if self.timestamp:
            result["@timestamp"] = self.timestamp
        if self.timestamp_raw:
            result["timestamp_raw"] = self.timestamp_raw
        if self.source_type:
            result["source_type"] = self.source_type
        if self.level:
            result["level"] = self.level
        if self.host:
            result["host"] = self.host
        if self.program:
            result["program"] = self.program
        if self.pid:
            result["pid"] = self.pid
        if self.message:
            result["message"] = self.message
        # Extra fields (ip, status, bytes, etc.)
        result.update(self.extra)
        # raw_log always last
        if self.raw_log:
            result["raw_log"] = self.raw_log
        return result

@dataclasses.dataclass
class LogProfile:
    name: str
    regex: re.Pattern
    date_fmt: Optional[str] = None
    level_map: Optional[Dict[str, str]] = None

    def normalize_level(self, raw_lvl: str) -> str:
        if not self.level_map:
            return raw_lvl.upper()
        return self.level_map.get(raw_lvl.upper(), raw_lvl.upper())

    def parse_date(self, raw_date: str) -> Tuple[str, bool]:
        """Returns (normalized_date, success)"""
        # Strategy:
        # 1. Try profile's specific format
        # 2. Try common formats (ISO, simple)
        # 3. Fail
        
        candidates = []
        if self.date_fmt:
            candidates.append(self.date_fmt)
        
        # Common fallbacks
        candidates.extend([
            "%Y-%m-%d %H:%M:%S,%f",
            "%Y-%m-%d %H:%M:%S",
            "%d/%b/%Y:%H:%M:%S %z", # Common Log Format
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ"
        ])

        for fmt in candidates:
            try:
                dt = datetime.datetime.strptime(raw_date, fmt)
                return dt.isoformat(), True
            except ValueError:
                continue
        
        return raw_date, False

# --- Profiles Registry ---

LOG_PROFILES = [
    # 1. Java / Spring Standard
    # Example: [2010-04-24 07:51:54,393] INFO - [main] Message...
    LogProfile(
        name="Java Application Log",
        regex=re.compile(r'^\[(?P<ts>.*?)\]\s+(?P<lvl>\w+)\s+-\s+\[(?P<thread>.*?)\]\s+(?P<msg>.*)'),
        date_fmt="%Y-%m-%d %H:%M:%S,%f",
        level_map={"INF": "INFO", "ERR": "ERROR", "WRN": "WARN", "DBG": "DEBUG"}
    ),

    # 2. Web Access Log (Combined)
    # Example: 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /index.html" 200 2326
    LogProfile(
        name="Web Access Log",
        regex=re.compile(r'^(?P<ip>\S+)\s\S+\s\S+\s\[(?P<ts>.*?)\]\s"(?P<req>.*?)"\s(?P<status>\d{3})\s(?P<bytes>\S+).*'),
        date_fmt="%d/%b/%Y:%H:%M:%S %z"
    ),

    # 3. Simple Syslog / Message
    # Example: 2023-10-27 10:00:00 INFO Some message
    LogProfile(
        name="Simple Timestamp Log",
        regex=re.compile(r'^(?P<ts>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+(?P<lvl>\w+)\s+(?P<msg>.*)'),
        date_fmt="%Y-%m-%d %H:%M:%S"
    ),

    # 4. Standard Linux Syslog (RFC 3164)
    # Example: Oct 11 22:14:15 myhost sshd[1234]: Failed password...
    LogProfile(
        name="Linux Syslog (Standard)",
        regex=re.compile(r'^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<app>[\w\-\.]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<msg>.*)'),
        # RFC 3164 does not have year. We leave it raw for now.
        date_fmt=None 
    ),

    # 5. Linux Kernel Ring Buffer (dmesg)
    # Example: [    0.000000] Linux version...
    LogProfile(
        name="Linux Kernel Log",
        regex=re.compile(r'^\[\s*(?P<ts_rel>\d+\.\d+)\]\s+(?P<msg>.*)'),
        # Relative timestamp, no absolute date format
        date_fmt=None
    ),

    # 6. Nginx Error Log
    # Example: 2023/10/27 10:00:00 [error] 1234#0: *1 connection timed out...
    LogProfile(
        name="Nginx Error Log",
        regex=re.compile(r'^(?P<ts>\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2})\s\[(?P<lvl>\w+)\]\s(?P<pid>\d+)#(?P<tid>\d+):\s(?P<msg>.*)'),
        date_fmt="%Y/%m/%d %H:%M:%S"
    ),

    # 7. Apache Error Log
    # Example: [Fri Oct 27 10:00:00.123456 2023] [core:error] [pid 1234] ...
    LogProfile(
        name="Apache Error Log",
        regex=re.compile(r'^\[(?P<ts>.*?)\]\s\[(?P<module>.*?):(?P<lvl>\w+)\]\s\[pid\s(?P<pid>\d+)\]\s(?P<msg>.*)'),
        # Complex Apache timestamp, letting it fall back to generic parser or raw
        date_fmt=None
    )
]

GENERIC_PROFILE = LogProfile(name="Generic Log (Fallback)", regex=re.compile(r'^(?P<msg>.*)'))

def parse_log(text: str) -> List[Dict[str, Any]]:
    """
    Smart Log Engine (Phase 3 - SOC Compatible).
    Returns a flat array of ECS-compatible events.
    Output format matches Splunk/ELK/Wazuh expectations.
    
    Note: JSON detection is handled by the caller (window.py) to allow user override.
    """
    if not text:
        return []

    lines = text.splitlines()
    
    # 2. Detect Best Profile
    sample_lines = [l for l in lines[:50] if l.strip()]
    best_profile = GENERIC_PROFILE
    best_score = 0.0

    if sample_lines:
        for profile in LOG_PROFILES:
            matches = sum(1 for line in sample_lines if profile.regex.match(line.strip()))
            score = matches / len(sample_lines)
            if score > best_score:
                best_score = score
                best_profile = profile
    
    # Fall back to Generic if no good match
    if best_score < 0.4:
        best_profile = GENERIC_PROFILE

    # 3. Parse Lines
    events = []
    current_entry: Optional[LogEntry] = None
    
    for line in lines:
        raw_line = line.rstrip('\r\n')
        clean_line = line.strip()
        
        if not clean_line:
            # Preserve empty lines in multiline context
            if current_entry:
                current_entry.raw_log += "\n"
                current_entry.message += "\n"
            continue
        
        # Generic Profile: One event per line, no parsing
        if best_profile == GENERIC_PROFILE:
            events.append(LogEntry(
                source_type="plain",
                message=raw_line,
                raw_log=raw_line
            ).to_ecs_dict())
            continue
        
        # Try to match structured profile
        match = best_profile.regex.match(clean_line)
        
        if match:
            # Flush previous entry
            if current_entry:
                events.append(current_entry.to_ecs_dict())
            
            groups = match.groupdict()
            
            # Extract timestamp
            raw_ts = groups.get("ts", "") or groups.get("ts_rel", "")
            norm_ts, _ = best_profile.parse_date(raw_ts) if raw_ts else (raw_ts, False)
            
            # Extract level
            level = best_profile.normalize_level(groups.get("lvl", ""))
            
            # Extract message
            msg = groups.get("msg", "")
            # Special handling for web access logs
            if "req" in groups:
                msg = f"{groups.get('req', '')} [{groups.get('status', '')}]"
            
            # Extract host/program/pid (ECS fields)
            host = groups.get("host", "")
            program = groups.get("app", "") or groups.get("module", "")
            pid = groups.get("pid", "")
            
            # Collect extra fields (ip, thread, etc.)
            extra = {}
            for k, v in groups.items():
                if k not in ["ts", "ts_rel", "lvl", "msg", "req", "host", "app", "module", "pid"] and v:
                    extra[k] = v
            
            # Map profile to source_type
            source_type_map = {
                "Java Application Log": "java",
                "Web Access Log": "access",
                "Simple Timestamp Log": "simple",
                "Linux Syslog (Standard)": "syslog",
                "Linux Kernel Log": "kernel",
                "Nginx Error Log": "nginx",
                "Apache Error Log": "apache"
            }
            source_type = source_type_map.get(best_profile.name, "unknown")
            
            current_entry = LogEntry(
                timestamp=norm_ts,
                timestamp_raw=raw_ts,
                source_type=source_type,
                level=level,
                message=msg,
                raw_log=raw_line,
                host=host,
                program=program,
                pid=pid or "",
                extra=extra
            )
        else:
            # Multiline continuation (stack traces, etc.)
            if current_entry:
                current_entry.raw_log += "\n" + raw_line
                current_entry.message += "\n" + raw_line
            else:
                # Orphan line at start
                events.append(LogEntry(
                    source_type="plain",
                    message=raw_line,
                    raw_log=raw_line
                ).to_ecs_dict())
    
    # Flush final entry
    if current_entry:
        events.append(current_entry.to_ecs_dict())

    return events


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
    Wrapper for Smart Log Engine to match Window interface.
    Returns: (success, json_string, error_msg)
    """
    result = parse_log(text)
    
    # Handle empty result
    if not result:
        return False, "", "No log entries found"

    try:
        json_str = json.dumps(result, indent=2)
        return True, json_str, None
    except Exception as e:
        return False, "", str(e)


# --- Previous Utils (Preserved) ---

def detect_language_by_content(text):
    """
    Analyzes text content to guess the programming language.
    Returns a GtkSourceView language ID or None.
    """
    text = text.strip()
    if not text:
        return None
        
    # 1. Shebang (Highest Priority)
    first_line = text.splitlines()[0]
    if first_line.startswith("#!"):
        if "python" in first_line: return "python"
        if "bash" in first_line or "sh" in first_line: return "sh"
        if "node" in first_line: return "js"
        if "perl" in first_line: return "perl"
        if "ruby" in first_line: return "ruby"
        if "php" in first_line: return "php"

    # 2. Strong Structure Indicators (Java, C++, Go, Python Defs, XML/HTML)
    sample = text[:1500]
    
    # Java (Strong)
    if "public class " in sample and "{" in sample: return "java"
    if "public static void main" in sample: return "java"
    if "package " in sample and ";" in sample: return "java"
    
    # Go (Strong)
    if "package main" in sample and "func main" in sample: return "go"
    
    # C/C++ Includes (Strong)
    if "#include <iostream>" in sample: return "cpp"
    if "#include <vector>" in sample: return "cpp"
    if "using namespace std;" in sample: return "cpp"
    if "#include <" in sample and ".h>" in sample: return "c"
    
    # Python Imports/Defs (Strong)
    if re.search(r'^import [a-zA-Z0-9_]+', sample, re.MULTILINE): return "python"
    if re.search(r'^from [a-zA-Z0-9_]+ import', sample, re.MULTILINE): return "python"
    if re.search(r'def [a-zA-Z0-9_]+\(', sample): return "python"
    if re.search(r'class [a-zA-Z0-9_]+(\(|:)', sample): return "python"
    if "if __name__ == " in sample: return "python"

    # HTML/XML Tags (Strong, if well-formed)
    if "<" in text and ">" in text:
        if re.search(r'<[a-zA-Z0-9_-]+.*?>', text):
             if "</body>" in text or "</div>" in text or "<script" in text or "<br" in text or "<p>" in text: return "html"
             # If strictly XML like, return XML. But C includes might trip this if logical operators are used.
             pass

    # 3. System (Gio) Content Sniffing
    import gi
    try:
        gi.require_version('GtkSource', '4')
    except ValueError:
        gi.require_version('GtkSource', '3.0')
    from gi.repository import Gio, GtkSource

    data = text.encode("utf-8")
    content_type, uncertain = Gio.content_type_guess(None, data)
    
    # If Gio is confident and it's not just generic text
    if not uncertain and content_type != "text/plain":
        # Exception: Gio often sees C++ or even Python/Java as partial C source.
        # We allow falling through for C/C++ types to let our strict/loose heuristics confirm.
        if content_type in ["text/x-csrc", "text/x-c++src", "text/x-chdr"]:
            pass # Fall through to heuristics
        else:
            manager = GtkSource.LanguageManager.get_default()
            language = manager.guess_language(None, content_type)
            if language:
                return language.get_id()

    # 4. JSON
    if (text.startswith("{") and text.endswith("}")) or \
       (text.startswith("[") and text.endswith("]")):
        try:
            import string
            no_space = "".join(text.split())
            if no_space == "{}" or no_space == "[]": return None
            json.loads(text)
            return "json"
        except:
             if text.startswith("{") and re.search(r'"[^"]*"\s*:', text): return "json"
             elif text.startswith("["): return "json"

    # 5. Looser Keyword Heuristics (Fallback)
    
    # C/C++ bodies
    if "int main(" in sample and "{" in sample:
        if "std::" in sample or "cout <<" in sample: return "cpp"
        return "c"
    if "printf(" in sample and ";" in sample: return "c"
    if "std::" in sample or "cout <<" in sample: return "cpp"

    # Java System.out
    if "System.out.println" in sample: return "java"

    # Python Loose (Strict Regex required to avoid prose matches)
    # Match 'for x in y:' on a SINGLE line
    if re.search(r'^\s*for\s+[a-zA-Z0-9_, ]+\s+in\s+.+:\s*$', sample, re.MULTILINE): return "python"
    # Match 'print("...")' but NOT 'System.out.print('
    if re.search(r'(^|\s)print\s*\(["\']', sample): return "python"

    # JavaScript
    if "function " in sample and "{" in sample: return "js"
    if "console.log(" in sample: return "js"
    if "const " in sample and "=" in sample: return "js"
    if "let " in sample and "=" in sample: return "js"
    if "document." in sample or "window." in sample: return "js"
            
    # CSS
    if "body {" in sample or ".class" in sample or "div {" in sample:
        if "{" in sample and ":" in sample and ";" in sample: return "css"
    if "@media" in sample or "@import" in sample: return "css"

    # Markdown
    if re.search(r'^#\s', sample, re.MULTILINE) or re.search(r'^\*\*.*\*\*$', sample, re.MULTILINE):
         return "markdown"

    # XML Fallback (Last resort)
    if "<" in text and ">" in text:
        if re.search(r'<[a-zA-Z0-9_-]+.*?>', text):
             if "</body>" in text or "</div>" in text: return "html"
             # Only return xml if it really looks like xml structure
             if "<?xml" in text: return "xml"
             # Don't default to XML for random brackets in text
             
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