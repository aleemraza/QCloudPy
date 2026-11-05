from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker
from gym_env import (
    GymEnvConfig,
    qcloudrl_env_creator,
)

config = GymEnvConfig(
    n_qnodes=4,
    max_tasks=100,
    default_execution_time=1.0,
)
env = qcloudrl_env_creator({
    "broker": Broker,
    "qnodes": QNode,
    "task_source": TaskFactory,
    "config": config,
    "obs_filter": "rescale_-1_1",
    "reward_filter": "scale",
    "reward_scale": 2.0,
})

observation, info = env.reset(seed=42)

print("Observation shape:", observation.shape)
print("Action space:", env.action_space)
print("Observation space:", env.observation_space)
print("Configuration:", config)

print("Gym environment package imports successfully.")