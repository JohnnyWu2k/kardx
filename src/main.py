# src/main.py
# The select_character function is now removed.
from .app_controller import AppController

def main():
    """The single entry point for the application."""
    app = AppController()
    app.run()

if __name__ == "__main__":
    main()