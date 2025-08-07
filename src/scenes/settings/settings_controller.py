# src/scenes/settings/settings_controller.py
from .settings_view import SettingsView
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ESC
from ...settings import settings_manager
from ...view_utils import Colors # Import Colors to get theme names

class SettingsController:
    def __init__(self):
        self.options = [
            {'key': 'show_enemy_hand', 'name': 'Show Enemy Hand', 'type': 'bool'},
            {'key': 'enable_colors', 'name': 'Enable Colors', 'type': 'bool'},
            {'key': 'enable_menu_animations', 'name': 'Enable Menu Animations', 'type': 'bool'},
            {'key': 'animation_speed_multiplier', 'name': 'Animation Speed', 'type': 'float', 'step': 0.1, 'min': 0.1, 'max': 2.0},
            # NEW THEME OPTION
            {'key': 'color_theme', 'name': 'Color Theme', 'type': 'cycle', 'choices': list(Colors.THEMES.keys())},
        ]
        self.view = SettingsView()
        self.selected_index = 0

    def run(self) -> str:
        # ... (run loop is unchanged) ...
        while True:
            self.view.display(self.options, self.selected_index)
            key = get_key()
            if key == KEY_UP: self.selected_index = (self.selected_index - 1) % len(self.options)
            elif key == KEY_DOWN: self.selected_index = (self.selected_index + 1) % len(self.options)
            elif key == KEY_LEFT or key == KEY_RIGHT: self._change_value(key)
            elif key == KEY_ESC: return "main_menu"

    def _change_value(self, key_direction):
        selected_option = self.options[self.selected_index]
        option_key = selected_option['key']
        option_type = selected_option['type']
        current_value = settings_manager.get(option_key)

        if option_type == 'bool':
            settings_manager.set(option_key, not current_value)
        elif option_type == 'float':
            # ... (float logic is unchanged) ...
            step = selected_option['step']
            new_value = current_value + (step if key_direction == KEY_RIGHT else -step)
            new_value = max(selected_option['min'], min(selected_option['max'], new_value))
            settings_manager.set(option_key, round(new_value, 2))
        
        ### NEW LOGIC for cycling through choices ###
        elif option_type == 'cycle':
            choices = selected_option['choices']
            current_idx = choices.index(current_value)
            if key_direction == KEY_RIGHT:
                new_idx = (current_idx + 1) % len(choices)
            else: # KEY_LEFT
                new_idx = (current_idx - 1) % len(choices)
            settings_manager.set(option_key, choices[new_idx])