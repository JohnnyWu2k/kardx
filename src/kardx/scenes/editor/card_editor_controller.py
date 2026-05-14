# src/scenes/editor/card_editor_controller.py
from ...keyboard import get_key
from ...view_utils import clear_screen,open_file

class CardEditorController:
    """
    Opens the cards.jsonc file for manual editing.
    """
    def run(self) -> str:
        """Opens the file and waits for a key press to return."""
        clear_screen()
        # Call the utility function to open the specific jsonc file
        open_file("cards.jsonc")
        
        print("\n   The card data file has been opened in your default editor.")
        print("   Make your changes, save the file, and then restart the game")
        print("   for the changes to take effect.")
        print("\n   Press any key to return to the editor menu.")
        get_key()
        return "editor_menu"