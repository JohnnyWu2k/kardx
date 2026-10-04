"""Unicode text-entry events are separate from physical gameplay controls."""
import curses


def read_text_key(screen):
    try:
        curses.noecho()
    except curses.error:
        pass
    try:
        key = screen.get_wch()
    except curses.error:
        return -1
    if isinstance(key, str) and len(key) == 1 and (ord(key) < 32 or ord(key) == 127):
        return ord(key)
    return key


def edit_text(text, key, limit=40):
    if key in (8, 127, curses.KEY_BACKSPACE):
        return text[:-1]
    if isinstance(key, str) and key.isprintable() and len(text) < limit:
        return text + key
    return text


def visible_input(text, width):
    from wcwidth import wcswidth
    text += "_"
    while text and wcswidth(text) > max(1, width):
        text = text[1:]
    return text
