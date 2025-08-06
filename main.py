# main.py
from pathlib import Path
from src.game_state import Game
from src.view import CLIView
from src.controller import GameController
from src.loader import load_json5_data

def select_character() -> str | None:
    # This function remains unchanged
    print("="*30); print("      CHARACTER SELECT"); print("="*30)
    char_data = load_json5_data(Path("data/characters.jsonc"))
    if not char_data: return None
    player_options = {k: v for k, v in char_data.items() if k.startswith("player_")}
    if not player_options: print("No playable characters found!"); return None
    player_list = list(player_options.items())
    for i, (char_id, char_info) in enumerate(player_list):
        print(f"  {i+1}. {char_info.get('display_name', char_id)}")
    while True:
        try:
            choice = input(f"Choose your character (1-{len(player_list)}): ")
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(player_list): return player_list[choice_index][0]
            else: print("Invalid number. Please try again.")
        except ValueError: print("Invalid input. Please enter a number.")

def main():
    """Main entry point: sets up and runs the game, handles replay loop."""
    while True:
        player_id = select_character()
        if not player_id:
            print("Could not start game."); break

        enemy_id = "enemy_automaton"
        
        # --- MVC Setup ---
        # 1. Create the Model
        game = Game(player_id=player_id, enemy_id=enemy_id)
        # 2. Create the View
        view = CLIView()
        # 3. Create the Controller and link Model and View
        controller = GameController(game, view)
        
        # --- Run the game ---
        # The controller now manages the entire game loop
        game_result = controller.run_game() 
        
        if game_result == "quit":
            print("Thanks for playing!")
            break

        # Ask to play again
        while True:
            play_again = input("Play again? (y/n): ").strip().lower()
            if play_again in ['y', 'n']: break
            print("Invalid input. Please enter 'y' or 'n'.")
            
        if play_again == 'n':
            print("Thanks for playing!")
            break

if __name__ == "__main__":
    main()