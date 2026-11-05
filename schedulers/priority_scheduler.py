
from .base_scheduler import BaseScheduler


class PriorityScheduler(BaseScheduler):

    def __init__(self):
        super().__init__("Priority")

    def select_action(self, env):

        actions = self.get_valid_actions(env)

        if not actions:
            raise RuntimeError("No valid scheduling actions.")

        candidates = {}

        for action in actions:
            task_index, node_index = self.decode_action(
                action, env.n_qnodes
            )

            candidates.setdefault(task_index, []).append(
                (action, node_index)
            )

        selected_task = min(
            candidates,
            key=lambda idx: (
                -env.qtasks[idx].priority,
                env.qtasks[idx].arrival_time,
                idx,
            ),
        )

        return min(
            candidates[selected_task],
            key=lambda item: (
                self.get_task_node_estimate(
                    env, selected_task, item[1]
                ),
                item[1],
            ),
        )[0]
