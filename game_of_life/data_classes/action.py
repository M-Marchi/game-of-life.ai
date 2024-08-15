from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    MOVE = 1
    ATTACK = 2
    FIND_FOOD = 3
    SLEEP = 4
    FIND_PARTNER = 5
    DIE = 6
    IDLE = 7
    GO_TO_TARGET = 8
    TALK = 9
    BUILD = 10


@dataclass
class Action:
    action_type: ActionType = None
    target_id: str | None = None
    explanation: str | None = None

    def parse_action(self, response: str):
        # Ensure response starts with a '/'
        if response.startswith("/"):
            # Split the response into action and explanation parts
            action_part, explanation = response.split(" --END", 1)

            # Further split the action part into command and target
            parts = action_part[1:].split(" ", 1)

            if len(parts) == 2:
                command, target_id = parts
            else:
                command = parts[0]
                target_id = None

            try:
                self.action_type = ActionType[command.upper()]
                self.target_id = target_id
            except KeyError:
                self.action_type = ActionType.IDLE
                self.target_id = None

            # Store or process the explanation if exist
            self.explanation = explanation.strip() if explanation else None
        else:
            self.action_type = ActionType.IDLE
            self.target_id = None
            self.explanation = None
