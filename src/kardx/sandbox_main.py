import sys

from .scenes.character_select.character_select_controller import CharacterSelectController
from .scenes.sandbox.sandbox_controller import SandboxController
from .view_utils import show_cursor


def main():
    """Launch Sandbox Mode directly."""
    try:
        player_id = sys.argv[1] if len(sys.argv) > 1 else None
        if player_id is None:
            player_id = CharacterSelectController().run()
        if not player_id:
            return
        SandboxController(player_id=player_id).run()
    finally:
        show_cursor()


if __name__ == "__main__":
    main()
