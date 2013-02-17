def force_bytes(s):
    try:
        return s.encode('utf-8')
    except (AttributeError, UnicodeDecodeError):
        return s
