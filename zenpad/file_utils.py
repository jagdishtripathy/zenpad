"""
File utilities for Zenpad - Binary detection and encoding handling
"""

import os
import mimetypes

# Known binary file extensions
BINARY_EXTENSIONS = {
    # Executables
    '.exe', '.dll', '.so', '.dylib', '.bin', '.o', '.obj', '.a',
    # Archives
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.apk', '.jar', '.deb', '.rpm',
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tiff', '.psd',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    # Media
    '.mp3', '.mp4', '.avi', '.mkv', '.wav', '.flac', '.ogg', '.mov', '.wmv',
    # Database
    '.db', '.sqlite', '.sqlite3',
    # Compiled/bytecode
    '.pyc', '.pyo', '.class', '.wasm', '.elc',
    # Fonts
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # Other
    '.iso', '.img', '.dmg',
}

# BOM signatures for encoding detection
BOM_SIGNATURES = {
    b'\xef\xbb\xbf': 'utf-8-sig',
    b'\xff\xfe': 'utf-16-le',
    b'\xfe\xff': 'utf-16-be',
    b'\xff\xfe\x00\x00': 'utf-32-le',
    b'\x00\x00\xfe\xff': 'utf-32-be',
}


def is_binary_file(file_path: str, sample_size: int = 8192) -> bool:
    """
    Detect if a file is binary using multiple heuristics.
    
    Args:
        file_path: Path to the file to check
        sample_size: Number of bytes to sample (default 8KB)
    
    Returns:
        True if file appears to be binary, False if text
    """
    # Check extension first (fast path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return True
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type.startswith(('image/', 'audio/', 'video/', 'application/octet-stream')):
            return True
        if mime_type.startswith('text/'):
            return False
    
    # Read sample and analyze content
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(sample_size)
    except (IOError, OSError):
        return False  # Can't read, assume text
    
    if not sample:
        return False  # Empty file is text
    
    # Check for null bytes (strong binary indicator)
    if b'\x00' in sample:
        return True
    
    # Check proportion of non-printable characters
    # ASCII printable: 32-126, plus common whitespace (9, 10, 13)
    text_chars = set(range(32, 127)) | {9, 10, 13}
    non_text = sum(1 for byte in sample if byte not in text_chars)
    
    # If more than 30% non-text characters, consider binary
    if len(sample) > 0 and (non_text / len(sample)) > 0.30:
        return True
    
    return False


def detect_encoding(file_path: str) -> tuple:
    """
    Detect file encoding and read content.
    
    Args:
        file_path: Path to the file
    
    Returns:
        Tuple of (encoding: str, content: str, error: str or None)
    """
    # Read raw bytes first
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
    except (IOError, OSError) as e:
        return (None, None, str(e))
    
    # Check for BOM
    for bom, encoding in BOM_SIGNATURES.items():
        if raw_data.startswith(bom):
            try:
                content = raw_data.decode(encoding)
                return (encoding, content, None)
            except UnicodeDecodeError:
                pass  # Try next method
    
    # Try UTF-8 (most common)
    try:
        content = raw_data.decode('utf-8')
        return ('UTF-8', content, None)
    except UnicodeDecodeError:
        pass
    
    # Try Windows-1252 (common for Windows files)
    try:
        content = raw_data.decode('windows-1252')
        return ('Windows-1252', content, None)
    except UnicodeDecodeError:
        pass
    
    # ISO-8859-1 always succeeds (it maps all bytes)
    content = raw_data.decode('iso-8859-1')
    return ('ISO-8859-1', content, None)


def read_file_safe(file_path: str) -> dict:
    """
    Safely read a file, detecting binary vs text and encoding.
    
    Returns:
        dict with keys:
        - 'is_binary': bool
        - 'content': str (for text) or bytes (for binary)
        - 'encoding': str (for text files)
        - 'error': str or None
    """
    result = {
        'is_binary': False,
        'content': '',
        'encoding': 'UTF-8',
        'error': None,
    }
    
    # Check if binary
    if is_binary_file(file_path):
        result['is_binary'] = True
        try:
            with open(file_path, 'rb') as f:
                result['content'] = f.read()
        except (IOError, OSError) as e:
            result['error'] = str(e)
        return result
    
    # Text file - detect encoding and read
    encoding, content, error = detect_encoding(file_path)
    result['encoding'] = encoding or 'UTF-8'
    result['content'] = content or ''
    result['error'] = error
    
    return result
