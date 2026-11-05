import gymnasium as gym
import numpy as np

from gymnasium.spaces import Box
from gymnasium.wrappers import NormalizeObservation


class ScaleQCloudRLReward(gym.RewardWrapper):
    """Scale the reward returned by the environment."""

    def __init__(self, env, scale=1.0):

        super().__init__(env)

        self.scaling_factor = float(scale)

    def reward(self, reward):

        return float(
            reward * self.scaling_factor
        )


class GymNormalizeObservation(NormalizeObservation):
    """
    Running observation normalization.

    The environment uses a flat Box observation, so the
    wrapper retains its one-dimensional observation shape.
    """

    def __init__(self, env, *args, **kwargs):

        super().__init__(
            env,
            *args,
            **kwargs,
        )

        self.observation_space = Box(
            low=np.full(
                env.obs_dim,
                -np.inf,
                dtype=np.float32,
            ),
            high=np.full(
                env.obs_dim,
                np.inf,
                dtype=np.float32,
            ),
            dtype=np.float32,
        )


class RescaleQCloudRLObservation(gym.ObservationWrapper):
    """
    Rescale non-negative observation features to [-1, 1].

    Uses explicit domain scales rather than running statistics.
    """

    def __init__(self, env):

        super().__init__(env)

        cfg = env.config

        scales = [
            cfg.max_arrival_time,
            cfg.max_qubits,
            cfg.max_shots,
            cfg.max_priority,
        ]

        for _ in range(env.n_qnodes):

            scales.extend([
                cfg.max_qubits,
                cfg.max_execution_time,
                cfg.max_arrival_time,
            ])

        self.scales = np.maximum(
            np.asarray(scales, dtype=np.float32),
            1e-6,
        )

        self.observation_space = Box(
            low=-1.0,
            high=1.0,
            shape=(env.obs_dim,),
            dtype=np.float32,
        )

    def observation(self, observation):

        normalized = np.clip(
            observation / self.scales,
            0.0,
            1.0,
        )

        return (
            2.0 * normalized - 1.0
        ).astype(np.float32)