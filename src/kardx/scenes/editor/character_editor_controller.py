# src/scenes/editor/character_editor_controller.py
from ...keyboard import get_key
# Import our new utility function
from ...view_utils import clear_screen, open_file

class CharacterEditorController:
    """
    Opens the characters.jsonc file for manual editing.
    """
    def run(self) -> str:
        """Opens the file and waits for a key press to return."""
        clear_screen()
        # Call the utility function to open the specific jsonc file
        open_file("characters.jsonc")
        
        print("\n   The character data file has been opened in your default editor.")
        print("   Make your changes, save the file, and then restart the game")
        print("   for the changes to take effect.")
        print("\n   Press any key to return to the editor menu.")
        get_key()
        return "editor_menu"