# kardx/__main__.py

from importlib import resources
from .game_state import Game
from .loader import load_json5_data

def select_character() -> str | None:
    """Displays a menu for the user to select a character."""
    print("="*30)
    print("      CHARACTER SELECT")
    print("="*30)
    
    try:
        char_path = resources.files('kardx.data').joinpath('characters.jsonc')
        char_data = load_json5_data(char_path)
    except (FileNotFoundError, ModuleNotFoundError):
        char_data = None
        
    if not char_data:
        print("Could not load character data!")
        return None
        
    player_options = {k: v for k, v in char_data.items() if k.startswith("player_")}
    if not player_options:
        print("No playable characters found!")
        return None

    player_list = list(player_options.items())
    
    for i, (char_id, char_info) in enumerate(player_list):
        print(f"  {i+1}. {char_info.get('display_name', char_id)}")
    
    while True:
        try:
            choice = input(f"Choose your character (1-{len(player_list)}): ")
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(player_list):
                return player_list[choice_index][0]
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid input.")

def main():
    """Main entry point for the game."""
    while True:
        player_id = select_character()
        if not player_id:
            print("Exiting game."); break
            
        enemy_id = "enemy_automaton"
        
        game = Game(player_id=player_id, enemy_id=enemy_id)
        game.run()
        
        while True:
            play_again = input("Play again? (y/n): ").strip().lower()
            if play_again in ['y', 'n']: break
            print("Invalid input.")
            
        if play_again == 'n':
            print("Thanks for playing!"); break

if __name__ == '__main__':
    main()