
# import gymnasium as gym
# import numpy as np
# from gymnasium.spaces import Box
# from gymnasium.wrappers import NormalizeObservation


# class ScaleQCloudRLReward(gym.RewardWrapper):
#     """Multiply the reward by a configurable scaling factor."""

#     def __init__(self, env, scale=2.0):
#         super().__init__(env)

#         if scale <= 0:
#             raise ValueError("Reward scale must be positive.")

#         self.scaling_factor = float(scale)

#     def reward(self, reward):
#         return float(reward) * self.scaling_factor


# class GymNormalizeObservation(NormalizeObservation):
#     """Apply Gymnasium's running observation normalization."""

#     def __init__(self, env, *args, **kwargs):
#         super().__init__(env, *args, **kwargs)

#         self.observation_space = Box(
#             low=-np.inf,
#             high=np.inf,
#             shape=env.observation_space.shape,
#             dtype=np.float32,
#         )


# class RescaleQCloudRLObservation(gym.ObservationWrapper):
#     """
#     Map observation values into the range [-1, 1].

#     tanh provides a bounded transformation even when an observation
#     feature is larger than its configured normalization scale.
#     """

#     def __init__(self, env):
#         super().__init__(env)

#         self.observation_space = Box(
#             low=-1.0,
#             high=1.0,
#             shape=env.observation_space.shape,
#             dtype=np.float32,
#         )

#     def observation(self, observation):
#         observation = np.asarray(observation, dtype=np.float32)
#         return np.tanh(observation).astype(np.float32)



import gymnasium as gym
import numpy as np

from gymnasium.spaces import Box
from gymnasium.wrappers import NormalizeObservation


class ScaleQCloudRLReward(gym.RewardWrapper):
    """Multiply the environment reward by a fixed scaling factor."""

    def __init__(self, env, scale=2.0):
        super().__init__(env)

        if scale <= 0:
            raise ValueError("Reward scale must be positive.")

        self.scaling_factor = float(scale)

    def reward(self, reward):
        return float(reward) * self.scaling_factor


class GymNormalizeObservation(NormalizeObservation):
    """Normalize observations using Gymnasium running statistics."""

    def __init__(self, env, *args, **kwargs):
        super().__init__(env, *args, **kwargs)

        self.observation_space = Box(
            low=-np.inf,
            high=np.inf,
            shape=env.observation_space.shape,
            dtype=np.float32,
        )


class RescaleQCloudRLObservation(gym.ObservationWrapper):
    """Map observations into the bounded range [-1, 1]."""

    def __init__(self, env):
        super().__init__(env)

        self.observation_space = Box(
            low=-1.0,
            high=1.0,
            shape=env.observation_space.shape,
            dtype=np.float32,
        )

    def observation(self, observation):
        observation = np.asarray(observation, dtype=np.float32)
        return np.tanh(observation).astype(np.float32)

