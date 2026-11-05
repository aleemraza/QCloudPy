
import numpy as np

from .base_scheduler import BaseScheduler


class RandomScheduler(BaseScheduler):

    def __init__(self, seed=None):
        super().__init__("Random")
        self.rng = np.random.default_rng(seed)

    def select_action(self, env):

        actions = self.get_valid_actions(env)

        if not actions:
            raise RuntimeError("No valid scheduling actions.")

        return int(self.rng.choice(actions))
