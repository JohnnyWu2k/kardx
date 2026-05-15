from ...keyboard import get_key
from ...view_utils import clear_screen, open_file


class DataFileEditorController:
    """Opens a data file for manual editing."""

    def __init__(self, filename: str, label: str):
        self.filename = filename
        self.label = label

    def run(self) -> str:
        clear_screen()
        open_file(self.filename)

        print(f"\n   The {self.label} data file has been opened in your default editor.")
        print("   Make your changes, save the file, and then restart the game")
        print("   for the changes to take effect.")
        print("\n   Press any key to return to the editor menu.")
        get_key()
        return "editor_menu"
