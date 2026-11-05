
from .base_scheduler import BaseScheduler


class GreedyScheduler(BaseScheduler):

    def __init__(self):
        super().__init__("Greedy")

    def select_action(self, env):

        actions = self.get_valid_actions(env)

        if not actions:
            raise RuntimeError("No valid scheduling actions.")

        return min(
            actions,
            key=lambda action: (
                self.get_task_node_estimate(
                    env,
                    *self.decode_action(
                        action, env.n_qnodes
                    ),
                ),
                action,
            ),
        )
