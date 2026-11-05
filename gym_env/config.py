# from dataclasses import dataclass
# @dataclass
# class GymEnvConfig:

#     # Environment
#     n_qnodes: int = 4
#     max_tasks: int = 500

#     # Simulation
#     rescheduling_time: float = 0.01
#     default_execution_time: float = 1.0
#     max_rescheduling_count: int = 100
#     max_episode_steps: int = 1000

#     # Reward
#     reward_mode: str = "inverse_time"
#     invalid_action_penalty: float = -0.1

#     # Observation normalization scales
#     max_arrival_time: float = 10000.0
#     max_qubits: float = 150.0
#     max_shots: float = 10000.0
#     max_priority: float = 10.0
#     max_execution_time: float = 1000.0

#     def __post_init__(self):

#         if self.n_qnodes <= 0:
#             raise ValueError("n_qnodes must be positive.")

#         if self.max_tasks <= 0:
#             raise ValueError("max_tasks must be positive.")

#         if self.rescheduling_time < 0:
#             raise ValueError("rescheduling_time cannot be negative.")

#         if self.default_execution_time <= 0:
#             raise ValueError("default_execution_time must be positive.")

#         if self.max_rescheduling_count <= 0:
#             raise ValueError("max_rescheduling_count must be positive.")

#         if self.max_episode_steps <= 0:
#             raise ValueError("max_episode_steps must be positive.")

#         if self.reward_mode not in ("inverse_time", "negative_time"):
#             raise ValueError(
#                 "reward_mode must be inverse_time or negative_time."
#             )

#         scales = {
#             "max_arrival_time": self.max_arrival_time,
#             "max_qubits": self.max_qubits,
#             "max_shots": self.max_shots,
#             "max_priority": self.max_priority,
#             "max_execution_time": self.max_execution_time,
#         }

#         for name, value in scales.items():
#             if value <= 0:
#                 raise ValueError(f"{name} must be positive.")


from dataclasses import dataclass


@dataclass
class GymEnvConfig:
    """Configuration for the QCloudRL Gymnasium environment."""

    # Environment
    n_qnodes: int = 4
    max_tasks: int = 500

    # Simulation
    rescheduling_time: float = 0.01
    default_execution_time: float = 1.0
    max_rescheduling_count: int = 100
    max_episode_steps: int = 1000

    # Reward
    reward_mode: str = "inverse_time"
    invalid_action_penalty: float = -0.1

    # Observation normalization scales
    max_arrival_time: float = 10000.0
    max_qubits: float = 150.0
    max_shots: float = 10000.0
    max_priority: float = 10.0
    max_execution_time: float = 1000.0

    def __post_init__(self):
        positive_integers = {
            "n_qnodes": self.n_qnodes,
            "max_tasks": self.max_tasks,
            "max_rescheduling_count": self.max_rescheduling_count,
            "max_episode_steps": self.max_episode_steps,
        }

        for name, value in positive_integers.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")

        if self.rescheduling_time < 0:
            raise ValueError("rescheduling_time cannot be negative.")

        if self.default_execution_time <= 0:
            raise ValueError("default_execution_time must be positive.")

        if self.reward_mode not in ("inverse_time", "negative_time"):
            raise ValueError(
                "reward_mode must be 'inverse_time' or 'negative_time'."
            )

        scales = {
            "max_arrival_time": self.max_arrival_time,
            "max_qubits": self.max_qubits,
            "max_shots": self.max_shots,
            "max_priority": self.max_priority,
            "max_execution_time": self.max_execution_time,
        }

        for name, value in scales.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive.")

        if self.invalid_action_penalty > 0:
            raise ValueError("invalid_action_penalty should be zero or negative.")
