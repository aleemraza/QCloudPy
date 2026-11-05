
from .base_scheduler import BaseScheduler


class FIFOScheduler(BaseScheduler):

    def __init__(self):
        super().__init__("FIFO")

    def select_action(self, env):

        actions = self.get_valid_actions(env)

        if not actions:
            raise RuntimeError("No valid scheduling actions.")

        task_candidates = {}

        for action in actions:
            task_index, node_index = self.decode_action(
                action, env.n_qnodes
            )

            task = env.qtasks[task_index]

            if task_index not in task_candidates:
                task_candidates[task_index] = []

            task_candidates[task_index].append(
                (action, node_index)
            )

        # Earliest arrival, then stable task-index tie-break.
        selected_task = min(
            task_candidates,
            key=lambda idx: (
                env.qtasks[idx].arrival_time,
                idx,
            ),
        )

        candidates = task_candidates[selected_task]

        # Choose the node with the lowest estimated
        # task completion time.
        return min(
            candidates,
            key=lambda item: (
                self.get_task_node_estimate(
                    env, selected_task, item[1]
                ),
                item[1],
            ),
        )[0]
