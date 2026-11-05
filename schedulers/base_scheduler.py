
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseScheduler(ABC):
    """
    Base interface for QCloudRL scheduling algorithms.

    A scheduling action jointly selects:
        1. A ready QTask.
        2. A compatible QNode.

    The environment is responsible for validating and
    executing the selected action.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def select_action(self, env) -> int:
        """
        Select one valid task-node action.

        Returns:
            Encoded Gymnasium action.
        """
        raise NotImplementedError

    @staticmethod
    def encode_action(task_index: int, node_index: int,
                      n_qnodes: int) -> int:
        return task_index * n_qnodes + node_index

    @staticmethod
    def decode_action(action: int, n_qnodes: int):
        task_index = action // n_qnodes
        node_index = action % n_qnodes
        return task_index, node_index

    @staticmethod
    def get_valid_actions(env):
        """
        Return all valid task-node actions using the
        environment's current action mask.
        """
        return env.get_valid_actions()

    @staticmethod
    def get_task_node_estimate(env, task_index, node_index):
        """
        Obtain the estimated completion time for a pair.
        """
        return env.estimate_pair_completion(
            task_index,
            node_index,
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r})"
