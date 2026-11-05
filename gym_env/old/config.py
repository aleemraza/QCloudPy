from dataclasses import dataclass


@dataclass
class GymEnvConfig:

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

        if self.n_qnodes <= 0:
            raise ValueError("n_qnodes must be positive.")

        if self.max_tasks <= 0:
            raise ValueError("max_tasks must be positive.")

        if self.default_execution_time <= 0:
            raise ValueError(
                "default_execution_time must be positive."
            )

        if self.reward_mode not in (
            "inverse_time",
            "negative_time",
        ):
            raise ValueError(
                "reward_mode must be inverse_time or negative_time."
            )