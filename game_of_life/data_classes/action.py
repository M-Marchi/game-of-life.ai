from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    MOVE = 1
    ATTACK = 2
    EAT = 3
    SLEEP = 4
    REPRODUCE = 5
    DIE = 6
    IDLE = 7
    NONE = 8


@dataclass
class Action:
    action_type: ActionType = None
    target_id: str | None = None

    def parse_action(self, action: str):
        if action.startswith("/"):
            parts = action[1:].split(" ", 1)
            if len(parts) == 2:
                command, target_id = parts
                try:
                    self.action_type = ActionType[command.upper()]
                    self.target_id = target_id
                    return True
                except KeyError:
                    self.action_type = ActionType.NONE
                    self.target_id = None
                    return False
            else:
                self.action_type = ActionType.NONE
                self.target_id = None
                return False
        else:
            self.action_type = ActionType.NONE
            self.target_id = None
            return False
