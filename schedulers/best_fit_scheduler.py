
from .base_scheduler import BaseScheduler


class BestFitScheduler(BaseScheduler):

    def __init__(self):
        super().__init__("BestFit")

    def select_action(self, env):

        actions = self.get_valid_actions(env)

        if not actions:
            raise RuntimeError("No valid scheduling actions.")

        def score(action):

            task_index, node_index = self.decode_action(
                action, env.n_qnodes
            )

            task = env.qtasks[task_index]
            node = env.qnodes[node_index]

            required = env.get_required_qubits(task)

            resource_waste = node.num_qubits - required

            completion_time = self.get_task_node_estimate(
                env, task_index, node_index
            )

            return (
                resource_waste,
                completion_time,
                action,
            )

        return min(actions, key=score)
