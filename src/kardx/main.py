# src/main.py
# The select_character function is now removed.
from .app_controller import AppController
from .view_utils import show_cursor

def main():
    """The single entry point for the application."""
    try:
        app = AppController()
        app.run()
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        show_cursor()

if __name__ == "__main__":
    main()
