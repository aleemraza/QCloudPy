from __future__ import annotations

import math
from typing import Callable, Optional

import gymnasium as gym
import numpy as np
import simpy

from gymnasium.spaces import Box, Discrete

from qcloudrl.Broker.constraints import ConstraintManager
from gym_env.config import GymEnvConfig


class QCloudRLEnv(gym.Env):
    """
    Joint task-QNode scheduling environment.

    Each action selects:
        1. A ready QTask.
        2. A compatible QNode.

    Broker:
        Task registration, assignment, and execution lifecycle.

    SimPy:
        Task arrivals, resource queues, and execution events.

    Gymnasium:
        Observations, actions, rewards, and episode management.
    """

    metadata = {"render_modes": ["human"]}

    TASK_FEATURES = 5
    NODE_FEATURES = 4
    PAIR_FEATURES = 2

    def __init__(
        self,
        broker,
        qnodes,
        task_source: Callable,
        config: Optional[GymEnvConfig] = None,
        execution_time_estimator: Optional[Callable] = None,
        render_mode=None,
    ):
        super().__init__()

        self.config = config or GymEnvConfig()

        if not callable(task_source):
            raise TypeError("task_source must be callable.")

        if not qnodes:
            raise ValueError("At least one QNode is required.")

        if len(qnodes) != self.config.n_qnodes:
            raise ValueError(
                f"Expected {self.config.n_qnodes} QNodes, "
                f"received {len(qnodes)}."
            )

        if render_mode not in (None, "human"):
            raise ValueError(f"Unsupported render mode: {render_mode}")

        self.broker = broker
        self.qnodes = list(qnodes)
        self.task_source = task_source
        self.execution_time_estimator = execution_time_estimator
        self.render_mode = render_mode

        self.n_qnodes = len(self.qnodes)
        self.max_tasks = self.config.max_tasks

        # --------------------------------------------------
        # Observation dimensions
        # --------------------------------------------------

        self.obs_dim = (
            self.max_tasks * self.TASK_FEATURES
            + self.n_qnodes * self.NODE_FEATURES
            + self.max_tasks * self.n_qnodes * self.PAIR_FEATURES
        )

        self.observation_space = Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.obs_dim,),
            dtype=np.float32,
        )

        # One action represents one task-node pair.
        self.action_space = Discrete(
            self.max_tasks * self.n_qnodes
        )

        # --------------------------------------------------
        # Episode state
        # --------------------------------------------------

        self.sim_env = None

        self.qtasks = []
        self.task_by_id = {}
        self.task_slot = {}

        self.predicted_node_available_time = {}

        self.results = []

        self.episode_steps = 0
        self.episode_finished = False

        self.current_obs = None

    # ======================================================
    # GENERAL HELPERS
    # ======================================================

    def _limit(self, name, default):
        """Return a safe positive normalization scale."""

        value = float(getattr(self.config, name, default))

        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                f"Normalization scale {name} must be finite and positive."
            )

        return value

    @staticmethod
    def _status_name(status):
        """Convert string or enum status into lowercase text."""

        return str(getattr(status, "value", status)).lower()

    def _pending_ids(self):
        """Return IDs of tasks currently waiting for scheduling."""

        return set(self.broker.pending_tasks)

    def _future_ids(self):
        """Return IDs of tasks that have not arrived yet."""

        return set(self.broker.future_tasks)

    # ======================================================
    # TASK INFORMATION AND LAZY LOADING
    # ======================================================

    @staticmethod
    def get_required_qubits(task):
        """
        Obtain a task's qubit requirement.

        Circuit loading happens only if metadata is unavailable
        and this method is called for a task that needs evaluation.
        """

        if task.required_qubits is not None:
            return int(task.required_qubits)

        circuit = task.get_circuit()

        required = int(circuit.num_qubits)

        # Cache the metadata so the circuit does not need to be
        # inspected again for this task.
        task.required_qubits = required

        return required

    def _get_required_qubits_for_observation(
        self,
        task,
        pending_ids,
    ):
        """
        Do not load circuits belonging to future tasks.

        A zero value for a future task means unknown metadata.
        It does not mean that the task requires zero qubits.
        """

        if task.required_qubits is not None:
            return int(task.required_qubits)

        if task.task_id in pending_ids:
            return self.get_required_qubits(task)

        return 0

    # ======================================================
    # EXECUTION-TIME ESTIMATION
    # ======================================================

    def estimate_execution_time(self, task, node):
        """
        Estimate execution duration for a task on a QNode.

        If no estimator is provided, use the configured default.
        """

        if self.execution_time_estimator is None:
            duration = self.config.default_execution_time
        else:
            duration = self.execution_time_estimator(task, node)

        duration = float(duration)

        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(
                "Execution time must be finite and positive."
            )

        return duration

    def estimate_pair_completion(self, task_index, node_index):
        """Estimate absolute completion time for a task-node pair."""

        task = self.qtasks[task_index]
        node = self.qnodes[node_index]

        execution_time = self.estimate_execution_time(task, node)

        predicted_start = max(
            float(self.sim_env.now),
            self.predicted_node_available_time[node.node_id],
        )

        return float(predicted_start + execution_time)

    # ======================================================
    # NODE COMPATIBILITY
    # ======================================================

    def check_compatibility(self, task, node):
        """
        Check whether a task can be accepted by a QNode.

        Busy nodes are allowed because SimPy manages resource queues.
        Offline and error nodes are rejected.
        """

        status = self._status_name(node.status)

        if status in ("offline", "error"):
            return False, "NODE_UNAVAILABLE"

        return ConstraintManager.check(
            task,
            node,
            check_availability=False,
        )

    def _check_ready_task_feasibility(self):
        """
        Ensure every ready task can run on at least one QNode.

        This prevents the environment from becoming stuck with
        an all-zero action mask due to permanently infeasible tasks.
        """

        for task_id in self._pending_ids():

            task = self.task_by_id[task_id]

            compatible_nodes = [
                node
                for node in self.qnodes
                if self.check_compatibility(task, node)[0]
            ]

            if not compatible_nodes:
                required = self.get_required_qubits(task)

                capacities = [
                    getattr(node, "num_qubits", 0)
                    for node in self.qnodes
                ]

                raise RuntimeError(
                    f"Ready task {task_id} has no compatible QNode. "
                    f"Required qubits: {required}. "
                    f"Available node capacities: {capacities}. "
                    "Check task requirements and QNode status."
                )

    # ======================================================
    # ACTION ENCODING
    # ======================================================

    def encode_action(self, task_index, node_index):
        """Encode a task-node pair into one Discrete action."""

        if not 0 <= task_index < self.max_tasks:
            raise ValueError("Invalid task index.")

        if not 0 <= node_index < self.n_qnodes:
            raise ValueError("Invalid node index.")

        return task_index * self.n_qnodes + node_index

    def decode_action(self, action):
        """Decode an action into task slot and node index."""

        action = int(action)

        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        task_index = action // self.n_qnodes
        node_index = action % self.n_qnodes

        return task_index, node_index

    # ======================================================
    # ACTION MASK
    # ======================================================

    def get_action_mask(self):
        """
        Return a binary mask for all task-node pairs.

        1 = valid assignment.
        0 = invalid assignment.

        A task must be ready, and its selected QNode must
        be online and compatible.
        """

        mask = np.zeros(
            self.action_space.n,
            dtype=np.int8,
        )

        pending_ids = self._pending_ids()

        if not pending_ids:
            return mask

        self._check_ready_task_feasibility()

        for task_id in pending_ids:

            task_index = self.task_slot[task_id]
            task = self.task_by_id[task_id]

            for node_index, node in enumerate(self.qnodes):

                compatible, _ = self.check_compatibility(
                    task,
                    node,
                )

                if compatible:
                    action = self.encode_action(
                        task_index,
                        node_index,
                    )

                    mask[action] = 1

        return mask

    def get_valid_actions(self):
        """Return the indices of all currently valid actions."""

        return np.flatnonzero(
            self.get_action_mask()
        ).tolist()

    # ======================================================
    # SIMULATION INITIALIZATION
    # ======================================================

    def _setup_simulation(self):
        """
        Create a fresh SimPy environment and reset the Broker.

        Important:
            Attach SimPy before registering QNodes so their
            resources are created against the new environment.
        """

        self.sim_env = simpy.Environment()

        self.broker.reset(preserve_nodes=False)

        self.broker.attach_simpy(self.sim_env)

        self.broker.register_nodes(self.qnodes)

        self.predicted_node_available_time = {
            node.node_id: 0.0
            for node in self.qnodes
        }

        self.results = []

        self.episode_steps = 0
        self.episode_finished = False
        self.current_obs = None

    # ======================================================
    # TASK REGISTRATION
    # ======================================================

    def _register_tasks(self):
        """
        Register all tasks at episode initialization.

        Broker and SimPy manage future task arrivals.
        """

        tasks = list(self.task_source())

        if not tasks:
            raise ValueError(
                "task_source returned no tasks."
            )

        if len(tasks) > self.max_tasks:
            raise ValueError(
                f"Received {len(tasks)} tasks, but max_tasks is "
                f"{self.max_tasks}."
            )

        task_ids = [task.task_id for task in tasks]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Duplicate task IDs detected.")

        for task in tasks:

            if task.arrival_time < 0:
                raise ValueError(
                    f"Task {task.task_id} has a negative arrival time."
                )

            if task.shots <= 0:
                raise ValueError(
                    f"Task {task.task_id} must have positive shots."
                )

        # Stable ordering and action-slot mapping.
        self.qtasks = sorted(
            tasks,
            key=lambda task: (
                task.arrival_time,
                task.task_id,
            ),
        )

        self.task_by_id = {
            task.task_id: task
            for task in self.qtasks
        }

        self.task_slot = {
            task.task_id: index
            for index, task in enumerate(self.qtasks)
        }

        # Submit all tasks. Future arrivals remain in Broker's
        # future queue until their SimPy arrival events occur.
        self.broker.submit_tasks(self.qtasks)

    # ======================================================
    # SIMPY EVENT MANAGEMENT
    # ======================================================

    def _advance_until_ready(self):
        """
        Advance simulation until at least one task is ready.

        All events at the same timestamp are processed before
        the scheduler receives its next decision.
        """

        while (
            not self.broker.pending_tasks
            and self.broker.future_tasks
        ):

            next_event_time = self.sim_env.peek()

            if next_event_time == float("inf"):
                break

            # Process the next event.
            self.sim_env.step()

            # Drain all events at exactly the same timestamp.
            while self.sim_env.peek() == next_event_time:
                self.sim_env.step()

    def _finish_episode(self):
        """Complete all remaining SimPy execution processes."""

        if not self.episode_finished:

            self.sim_env.run()

            self.episode_finished = True

    # ======================================================
    # OBSERVATION GENERATION
    # ======================================================

    def _get_obs(self):
        """
        Construct a fixed-size observation.

        Task features:
            0. Ready flag
            1. Relative arrival time
            2. Required qubits
            3. Shots
            4. Priority

        Node features:
            0. Qubit capacity
            1. Online indicator
            2. Waiting queue length
            3. Predicted waiting time

        Pair features:
            0. Compatibility indicator
            1. Estimated execution time
        """

        task_features = np.zeros(
            (self.max_tasks, self.TASK_FEATURES),
            dtype=np.float32,
        )

        node_features = np.zeros(
            (self.n_qnodes, self.NODE_FEATURES),
            dtype=np.float32,
        )

        pair_features = np.zeros(
            (
                self.max_tasks,
                self.n_qnodes,
                self.PAIR_FEATURES,
            ),
            dtype=np.float32,
        )

        pending_ids = self._pending_ids()

        now = float(self.sim_env.now)

        # --------------------------------------------------
        # Task features and task-node pair features
        # --------------------------------------------------

        for task_index, task in enumerate(self.qtasks):

            task_id = task.task_id
            is_ready = task_id in pending_ids

            required = self._get_required_qubits_for_observation(
                task,
                pending_ids,
            )

            relative_arrival = (
                float(task.arrival_time) - now
            )

            task_features[task_index] = [
                float(is_ready),
                relative_arrival
                / self._limit("max_arrival_time", 10000.0),
                required
                / self._limit("max_qubits", 150.0),
                float(task.shots)
                / self._limit("max_shots", 10000.0),
                float(task.priority)
                / self._limit("max_priority", 10.0),
            ]

            # Only ready tasks receive pair features.
            # Future task circuits remain unloaded.
            if not is_ready:
                continue

            for node_index, node in enumerate(self.qnodes):

                compatible, _ = self.check_compatibility(
                    task,
                    node,
                )

                if not compatible:
                    continue

                execution_time = self.estimate_execution_time(
                    task,
                    node,
                )

                pair_features[task_index, node_index] = [
                    1.0,
                    execution_time
                    / self._limit("max_execution_time", 1000.0),
                ]

        # --------------------------------------------------
        # QNode features
        # --------------------------------------------------

        for node_index, node in enumerate(self.qnodes):

            resource = self.broker.node_resources.get(
                node.node_id
            )

            status = self._status_name(node.status)

            online = float(
                status not in ("offline", "error")
            )

            queue_length = (
                len(resource.queue)
                if resource is not None
                else 0
            )

            waiting_time = max(
                0.0,
                self.predicted_node_available_time[node.node_id] - now,
            )

            node_features[node_index] = [
                float(node.num_qubits)
                / self._limit("max_qubits", 150.0),

                online,

                float(queue_length)
                / self._limit("max_tasks", 500.0),

                waiting_time
                / self._limit("max_execution_time", 1000.0),
            ]

        observation = np.concatenate([
            task_features.flatten(),
            node_features.flatten(),
            pair_features.flatten(),
        ])

        return observation.astype(np.float32)

    # ======================================================
    # SCHEDULING AND DISPATCH
    # ======================================================

    def _execute_scheduling_action(self, action):
        """
        Execute one task-node scheduling decision.

        The Broker performs assignment and dispatch.
        SimPy manages actual resource waiting and execution.
        """

        task_index, node_index = self.decode_action(action)

        if task_index >= len(self.qtasks):
            raise ValueError("Action refers to an unused task slot.")

        task = self.qtasks[task_index]
        node = self.qnodes[node_index]

        if task.task_id not in self._pending_ids():
            raise ValueError(
                f"Task {task.task_id} is not ready for scheduling."
            )

        compatible, reason = self.check_compatibility(
            task,
            node,
        )

        if not compatible:
            raise ValueError(
                f"Incompatible task-node assignment: {reason}"
            )

        execution_time = self.estimate_execution_time(
            task,
            node,
        )

        now = float(self.sim_env.now)

        predicted_start = max(
            now,
            self.predicted_node_available_time[node.node_id],
        )

        estimated_waiting_time = predicted_start - now

        predicted_finish = predicted_start + execution_time

        # Time already spent waiting since task arrival.
        elapsed_waiting_time = max(
            0.0,
            now - float(task.arrival_time),
        )

        estimated_total_time = (
            elapsed_waiting_time
            + estimated_waiting_time
            + execution_time
        )

        # Broker assignment. Busy nodes are allowed:
        # SimPy will queue the task on their resource.
        self.broker.assign_task(
            task_id=task.task_id,
            node_id=node.node_id,
            allow_busy=True,
        )

        self.broker.dispatch_task(
            task_id=task.task_id,
            execution_time=execution_time,
        )

        # Update the predicted availability of this QNode.
        self.predicted_node_available_time[node.node_id] = (
            predicted_finish
        )

        if self.config.reward_mode == "inverse_time":
            reward = 1.0 / max(estimated_total_time, 1e-8)
        else:
            reward = -estimated_total_time

        result = {
            "task_id": task.task_id,
            "task_index": task_index,
            "node_id": node.node_id,
            "node_index": node_index,
            "simulation_time": now,
            "estimated_waiting_time": estimated_waiting_time,
            "estimated_execution_time": execution_time,
            "estimated_total_time": estimated_total_time,
            "predicted_finish_time": predicted_finish,
        }

        self.results.append(result)

        return float(reward), result

    # ======================================================
    # GYMNASIUM RESET
    # ======================================================

    def reset(self, *, seed=None, options=None):

        super().reset(seed=seed)

        self._setup_simulation()

        self._register_tasks()

        # Move to the first arrival and process all events
        # occurring at that same timestamp.
        self._advance_until_ready()

        if not self.broker.pending_tasks:
            raise RuntimeError(
                "No task became ready during initialization."
            )

        self._check_ready_task_feasibility()

        self.current_obs = self._get_obs()

        info = {
            "simulation_time": float(self.sim_env.now),
            "total_tasks": len(self.qtasks),
            "ready_tasks": len(self.broker.pending_tasks),
            "future_tasks": len(self.broker.future_tasks),
            "action_mask": self.get_action_mask(),
        }

        return self.current_obs, info
    
    # debug
    def debug_broker_resources(self):

        print("\nSIMPY RESOURCE DEBUG")
        print("-" * 70)

        for node in self.qnodes:

            resource = self.broker.node_resources[node.node_id]

            assigned_count = sum(
                1 for n in self.broker.assigned_tasks.values()
                if n == node.node_id
            )

            print(f"\nNode: {node.node_id}")
            print(f"Resource capacity: {resource.capacity}")
            print(f"Resource count: {resource.count}")
            print(f"Waiting requests: {len(resource.queue)}")
            print(f"Active users: {len(resource.users)}")
            print(f"Assigned tasks: {assigned_count}")
            
            # end debug

    # ======================================================
    # GYMNASIUM STEP
    # ======================================================

    # def step(self, action):

    #     if self.episode_finished:
    #         raise RuntimeError(
    #             "Episode has finished. Call reset() before step()."
    #         )

    #     if not self.action_space.contains(action):
    #         raise ValueError(f"Invalid action: {action}")

    #     # Truncate when the decision-step limit has been reached.
    #     if self.episode_steps >= self.config.max_episode_steps:

    #         self._finish_episode()

    #         observation = self._get_obs()

    #         return (
    #             observation,
    #             0.0,
    #             False,
    #             True,
    #             {
    #                 "reason": "Maximum episode steps reached.",
    #                 "simulation_time": float(self.sim_env.now),
    #             },
    #         )

    #     action = int(action)

    #     action_mask = self.get_action_mask()

    #     if action_mask[action] == 0:
    #         raise ValueError(
    #             f"Invalid scheduling action {action}. "
    #             "The selected task-node pair is not currently feasible."
    #         )

    #     self.episode_steps += 1

    #     reward, info = self._execute_scheduling_action(action)
    #      # --------------------------------------------------
    #     # 3. Capture actual resource queue status.
    #     # --------------------------------------------------

    #     queue_snapshot = self.get_qnode_queue_status()

    #     # If no ready tasks remain, advance to the next arrival.
    #     self._advance_until_ready()

    #     terminated = not (
    #         self.broker.pending_tasks
    #         or self.broker.future_tasks
    #     )

    #     if terminated:
    #         # Complete any tasks still executing on QNodes.
    #         self._finish_episode()

    #     self.current_obs = self._get_obs()

    #     info.update({
    #         "simulation_time": float(self.sim_env.now),
    #         "ready_tasks": len(self.broker.pending_tasks),
    #         "future_tasks": len(self.broker.future_tasks),
    #         "completed_tasks": len(self.broker.completed_tasks),
    #         "episode_step": self.episode_steps,
    #         "action_mask": self.get_action_mask(),
    #         "terminated": terminated,
    #     })

    #     return (
    #         self.current_obs,
    #         reward,
    #         terminated,
    #         False,
    #         info,
    #     )
    
     
     
    # new method
    def get_qnode_queue_status(self):

        status_list = []

        for node in self.qnodes:

            node_id = node.node_id

            resource = self.broker.node_resources[node_id]

            waiting_task_ids = []

            running_task_ids = []

            for request in resource.queue:
                for task_id, process in self.broker.active_processes.items():
                    if request.proc == process:
                        waiting_task_ids.append(task_id)

            for request in resource.users:
                for task_id, process in self.broker.active_processes.items():
                    if request.proc == process:
                        running_task_ids.append(task_id)

            completed = sum(
                1
                for record in self.broker.execution_records.values()
                if record.node_id == node_id
                and self._status_name(record.status) == "completed"
            )

            failed = sum(
                1
                for record in self.broker.execution_records.values()
                if record.node_id == node_id
                and self._status_name(record.status) == "failed"
            )

            status_list.append({
                "node_id": node_id,
                "backend": node.backend_name,
                "status": self._status_name(node.status),
                "waiting_count": len(resource.queue),
                "running_count": resource.count,
                "assigned_count": sum(
                    1 for assigned_node in
                    self.broker.assigned_tasks.values()
                    if assigned_node == node_id
                ),
                "completed_count": completed,
                "failed_count": failed,
                "waiting_tasks": waiting_task_ids,
                "running_tasks": running_task_ids,
            })

        return status_list
    # end new method 
    
    
    def step(self, action):

        if self.episode_finished:
            raise RuntimeError(
                "Episode has finished. Call reset() before step()."
            )

        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        # Truncate when the decision-step limit has been reached.
        if self.episode_steps >= self.config.max_episode_steps:

            observation = self._get_obs()

            return (
                observation,
                0.0,
                False,
                True,
                {
                    "reason": "Maximum episode steps reached.",
                    "simulation_time": float(self.sim_env.now),
                },
            )

        action = int(action)

        action_mask = self.get_action_mask()

        if action_mask[action] == 0:
            raise ValueError(
                f"Invalid scheduling action {action}. "
                "The selected task-node pair is not currently feasible."
            )

        self.episode_steps += 1

        # 1. Assign selected task to a QNode.
        reward, info = self._execute_scheduling_action(action)

        # 2. Advance simulation if no ready tasks remain.
        self._advance_until_ready()

        terminated = not (
            self.broker.pending_tasks
            or self.broker.future_tasks
        )

        # 3. Process SimPy events at the current simulation time.
        # This allows dispatched tasks to request QNode resources.
        now = self.sim_env.now

        while self.sim_env.peek() == now:
            self.sim_env.step()

        # 4. Capture queue state before execution completion.
        queue_snapshot = self.get_qnode_queue_status()

        # 5. Do NOT call _finish_episode() here.
        # The experiment runner will complete execution after
        # all scheduling decisions have been made.

        # 6. Build next observation.
        self.current_obs = self._get_obs()

        # 7. Update information returned to the caller.
        info.update({
            "simulation_time": float(self.sim_env.now),
            "ready_tasks": len(self.broker.pending_tasks),
            "future_tasks": len(self.broker.future_tasks),
            "completed_tasks": len(self.broker.completed_tasks),
            "episode_step": self.episode_steps,
            "action_mask": self.get_action_mask(),
            "terminated": terminated,
            "qnode_queue_status": queue_snapshot,
        })

        return (
            self.current_obs,
            reward,
            terminated,
            False,
            info,
        )

   

    # ======================================================
    # RESULTS
    # ======================================================

    def collect_results(self):
        """
        Collect actual execution metrics from Broker records.

        Estimated values in self.results are not used as actual
        waiting time, execution time, or makespan.
        """

        records = list(
            self.broker.execution_records.values()
        )

        completed = [
            record
            for record in records
            if self._status_name(record.status) == "completed"
        ]

        failed = [
            record
            for record in records
            if self._status_name(record.status) == "failed"
        ]

        waiting_times = [
            float(record.waiting_time)
            for record in completed
            if record.waiting_time is not None
        ]

        execution_times = [
            float(record.execution_time)
            for record in completed
            if record.execution_time is not None
        ]

        finish_times = [
            float(record.finish_time)
            for record in completed
            if record.finish_time is not None
        ]

        cancelled_count = sum(
            self._status_name(task.status) == "cancelled"
            for task in self.qtasks
        )

        return {
            "submitted_tasks": len(records),
            "completed_tasks": len(completed),
            "failed_tasks": len(failed),
            "cancelled_tasks": cancelled_count,

            "average_waiting_time": (
                float(np.mean(waiting_times))
                if waiting_times else 0.0
            ),

            "average_execution_time": (
                float(np.mean(execution_times))
                if execution_times else 0.0
            ),

            "makespan": (
                float(max(finish_times) - min(
                    float(record.start_time)
                    for record in completed
                    if record.start_time is not None
                ))
                if finish_times and any(
                    record.start_time is not None
                    for record in completed
                )
                else 0.0
            ),

            "total_rescheduling_count": 0,
            "simulation_end_time": float(self.sim_env.now),
            "broker_stats": self.broker.get_stats(),
        }

    # ======================================================
    # RENDER AND CLOSE
    # ======================================================

    def render(self):

        if self.render_mode == "human":

            print(
                f"Time: {self.sim_env.now:.2f} | "
                f"Ready: {len(self.broker.pending_tasks)} | "
                f"Future: {len(self.broker.future_tasks)} | "
                f"Completed: {len(self.broker.completed_tasks)}"
            )

    def close(self):
        """No external resources currently need closing."""
        pass


