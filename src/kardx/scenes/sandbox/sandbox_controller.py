from __future__ import annotations

from ...sandbox import BattleSession, SandboxGame
from ..game.game_controller import GameController
from ..game.game_view import GameView
from .sandbox_view import SandboxView


class SandboxController:
    HELP_LINES = [
        "Commands:",
        "  look",
        "  go <direction> or north/east/south/west/up/down",
        "  take <item>",
        "  use <item>",
        "  forage",
        "  craft <recipe>",
        "  recipes",
        "  inventory",
        "  deck",
        "  talk [who]",
        "  journal",
        "  save [slot]",
        "  load [slot]",
        "  quit",
    ]

    DIRECTIONS = {"north", "east", "south", "west", "up", "down"}

    def __init__(self, player_id: str):
        self.game = SandboxGame()
        self.game.start(player_id)
        self.view = SandboxView()
        self.messages = ["Sandbox mode started.", "Type 'help' for commands."]

    def run(self) -> str:
        while True:
            self._display()
            try:
                command = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                return "main_menu"
            result = self._handle_command(command)
            if result in {"main_menu", "quit"}:
                return "main_menu"
            encounter_result = self._handle_pending_encounter()
            if encounter_result == "main_menu":
                return "main_menu"

    def _display(self):
        lines = [
            *self.game.look_lines(),
            "",
            "Messages:",
            *(self.messages[-6:] or [""]),
        ]
        self.view.display(lines)

    def _handle_command(self, command: str) -> str:
        if not command:
            return "continue"
        words = command.lower().split()
        verb = words[0]
        arg = "_".join(words[1:]) if len(words) > 1 else ""

        if verb in {"quit", "exit"}:
            return "main_menu"
        if verb == "help":
            self.messages = list(self.HELP_LINES)
        elif verb == "look":
            self.messages = ["You take a careful look around."]
        elif verb in self.DIRECTIONS:
            self.messages = self.game.go(verb)
        elif verb == "go" and arg:
            self.messages = self.game.go(arg)
        elif verb == "take" and arg:
            self.messages = self.game.take(arg)
        elif verb == "use" and arg:
            self.messages = self.game.use(arg)
        elif verb in {"forage", "gather"}:
            self.messages = self.game.forage()
        elif verb == "craft" and arg:
            self.messages = self.game.craft(arg)
        elif verb == "recipes":
            self.messages = self._recipe_lines()
        elif verb in {"inventory", "i"}:
            self.messages = self.game.inventory_lines()
        elif verb == "deck":
            self.messages = self.game.deck_lines()
        elif verb == "talk":
            self.messages = self.game.talk(arg or None)
        elif verb == "journal":
            self.messages = self.game.journal_lines()
        elif verb == "save":
            slot = arg or "sandbox"
            try:
                path = self.game.save(slot)
                self.messages = [f"Saved to {path}."]
            except (OSError, ValueError) as exc:
                self.messages = [f"Could not save slot '{slot}': {exc}"]
        elif verb == "load":
            slot = arg or "sandbox"
            try:
                self.game.load(slot)
                self.messages = [f"Loaded slot: {slot}."]
            except FileNotFoundError:
                self.messages = [f"No save slot named '{slot}'."]
            except (OSError, ValueError) as exc:
                self.messages = [f"Could not load slot '{slot}': {exc}"]
        else:
            self.messages = ["Unknown command. Type 'help'."]
        return "continue"

    def _recipe_lines(self) -> list[str]:
        lines = ["Recipes:"]
        for recipe_id, recipe in sorted(self.game.data.recipes.items()):
            required = ", ".join(
                f"{amount} {item_id}"
                for item_id, amount in recipe.get("requires", {}).items()
            )
            lines.append(f"- {recipe_id}: {required or 'free'}")
        return lines

    def _handle_pending_encounter(self) -> str:
        encounter_id = self.game.pending_encounter_id()
        if not encounter_id:
            return "continue"
        encounter = self.game.data.encounters[encounter_id]
        self.view.message("Encounter", [f"{encounter.get('label', encounter_id)} blocks your path."])
        session = BattleSession(self.game, encounter_id)
        if not session.game.player or not session.game.enemy:
            self.messages = [f"Encounter '{encounter_id}' is misconfigured."]
            return "continue"
        result = GameController(session.game, GameView()).run()
        if result == "main_menu":
            return "main_menu"
        self.messages = session.finish(result)
        return "continue"
