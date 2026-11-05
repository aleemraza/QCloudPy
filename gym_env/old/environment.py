import gymnasium as gym
import numpy as np
import simpy

from gymnasium.spaces import Box, Discrete

from .config import GymEnvConfig


class QCloudRLEnv(gym.Env):
    """
    SimPy-based Gymnasium environment for QCloudRL.

    One action selects a QNode for the current QTask.

    SimPy independently manages the execution and waiting
    queues of all QNodes.

    The environment uses virtual execution durations.
    It does not execute circuits on Aer or real IBM hardware.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        broker,
        qnodes,
        task_source,
        config=None,
        execution_time_estimator=None,
        render_mode=None,
    ):

        super().__init__()

        self.broker = broker
        self.qnodes = list(qnodes)
        self.task_source = task_source

        self.config = config or GymEnvConfig()

        self.execution_time_estimator = (
            execution_time_estimator
        )

        self.render_mode = render_mode

        if len(self.qnodes) != self.config.n_qnodes:
            raise ValueError(
                "n_qnodes does not match the supplied QNodes."
            )

        self.n_qnodes = len(self.qnodes)

        # =====================================
        # ACTION SPACE
        # =====================================

        # Action = selected QNode index
        self.action_space = Discrete(self.n_qnodes)

        # =====================================
        # OBSERVATION SPACE
        # =====================================

        # Current task:
        # [arrival_time, required_qubits, shots, priority]
        #
        # Each QNode:
        # [num_qubits, predicted_execution_time, next_available_time]

        self.obs_dim = 4 + self.n_qnodes * 3

        self.observation_space = Box(
            low=np.full(
                self.obs_dim,
                -np.inf,
                dtype=np.float32,
            ),
            high=np.full(
                self.obs_dim,
                np.inf,
                dtype=np.float32,
            ),
            dtype=np.float32,
        )

        # =====================================
        # SIMULATION STATE
        # =====================================

        self.sim_env = None

        self.tasks = []
        self.current_qtask = None

        self.task_index = 0
        self.round = 0
        self.episode_steps = 0

        self.node_next_available_time = {}

        self.results = []

        self.current_obs = None
        self.episode_finished = False

    # =================================================
    # SIMULATION INITIALIZATION
    # =================================================

    def _setup_simulation(self):

        # A new SimPy clock for every episode
        self.sim_env = simpy.Environment()

        # Reset Broker-managed state
        self.broker.reset()

        # Register the existing QNodes again
        self.broker.register_nodes(self.qnodes)

        # Give each QNode an independent SimPy resource
        self.broker.attach_simpy(self.sim_env)

        self.node_next_available_time = {
            node.node_id: 0.0
            for node in self.qnodes
        }

    # =================================================
    # TASK GENERATION
    # =================================================

    def generate_qtasks(self):

        tasks = list(self.task_source())

        if len(tasks) == 0:
            raise ValueError(
                "The task source returned an empty workload."
            )

        if len(tasks) > self.config.max_tasks:
            raise ValueError(
                "Workload exceeds max_tasks."
            )

        task_ids = [task.task_id for task in tasks]

        if len(set(task_ids)) != len(task_ids):
            raise ValueError(
                "QTask IDs must be unique within an episode."
            )

        # Tasks are processed in arrival order.
        tasks.sort(key=lambda task: task.arrival_time)

        self.tasks = tasks
        self.task_index = 0

        self.current_qtask = self.tasks[0]

    # =================================================
    # EXECUTION TIME ESTIMATION
    # =================================================

    def estimate_execution_time(self, task, node):

        if self.execution_time_estimator is not None:

            execution_time = (
                self.execution_time_estimator(task, node)
            )

        else:

            execution_time = (
                self.config.default_execution_time
            )

        execution_time = float(execution_time)

        if (
            not np.isfinite(execution_time)
            or execution_time <= 0
        ):
            raise ValueError(
                "Execution time must be finite and positive."
            )

        return execution_time

    # =================================================
    # SIMPY TIME ADVANCEMENT
    # =================================================

    def _advance_to_arrival(self, arrival_time):

        if arrival_time > self.sim_env.now:

            self.sim_env.run(
                until=float(arrival_time)
            )

    def _advance_rescheduling_time(self):

        next_time = (
            self.sim_env.now
            + self.config.rescheduling_time
        )

        self.sim_env.run(until=next_time)

    # =================================================
    # OBSERVATION
    # =================================================

    def _get_obs(self):

        if self.current_qtask is None:

            task_obs = np.zeros(
                4,
                dtype=np.float32,
            )

        else:

            task = self.current_qtask

            required_qubits = (
                task.required_qubits or 0
            )

            task_obs = np.array(
                [
                    task.arrival_time,
                    required_qubits,
                    task.shots,
                    task.priority,
                ],
                dtype=np.float32,
            )

        node_obs = []

        for node in self.qnodes:

            node_id = node.node_id

            # Estimate how long this task would execute
            # on this node.
            if self.current_qtask is not None:

                execution_time = (
                    self.estimate_execution_time(
                        self.current_qtask,
                        node,
                    )
                )

            else:

                execution_time = 0.0

            next_available = (
                self.node_next_available_time[node_id]
            )

            node_obs.append(
                [
                    node.num_qubits,
                    execution_time,
                    next_available,
                ]
            )

        node_obs = np.array(
            node_obs,
            dtype=np.float32,
        ).flatten()

        observation = np.concatenate(
            [task_obs, node_obs]
        ).astype(np.float32)

        return observation

    # =================================================
    # SCHEDULING
    # =================================================

    def submit_task_to_qnode(self, task, node_index):

        node = self.qnodes[node_index]

        # The selected node may be busy.
        # Only actual compatibility is checked here.
        compatible, error_code = (
            self.broker.constraints.check(
                task,
                node,
                check_availability=False,
            )
        )

        if not compatible:

            if error_code == "INSUFFICIENT_QUBITS":

                if hasattr(task, "rescheduling_count"):
                    task.rescheduling_count += 1

            self._advance_rescheduling_time()

            return (
                self.config.invalid_action_penalty,
                False,
                {
                    "invalid_action": True,
                    "error_code": error_code,
                    "task_id": task.task_id,
                    "node_id": node.node_id,
                },
            )

        # -------------------------------------
        # Wait until task arrival
        # -------------------------------------

        self._advance_to_arrival(task.arrival_time)

        # -------------------------------------
        # Submit task to Broker
        # -------------------------------------

        self.broker.submit_task(task)

        # -------------------------------------
        # Assign task to selected QNode
        # -------------------------------------

        self.broker.assign_task(
            task_id=task.task_id,
            node_id=node.node_id,
            current_time=self.sim_env.now,
            allow_busy=True,
        )

        # -------------------------------------
        # Execution time
        # -------------------------------------

        execution_time = (
            self.estimate_execution_time(
                task,
                node,
            )
        )

        # Predicted queue waiting time
        predicted_start = max(
            self.sim_env.now,
            self.node_next_available_time[node.node_id],
        )

        waiting_time = (
            predicted_start - self.sim_env.now
        )

        predicted_finish = (
            predicted_start + execution_time
        )

        self.node_next_available_time[
            node.node_id
        ] = predicted_finish

        # -------------------------------------
        # Start SimPy process
        # -------------------------------------

        process = self.broker.submit_qtask_to_qnode(
            task=task,
            node=node,
            execution_time=execution_time,
        )

        # Process runs independently in SimPy.
        # We do not wait for it to finish here.

        delay_time = max(
            0.0,
            self.sim_env.now - task.arrival_time,
        )

        total_time_cost = (
            delay_time
            + waiting_time
            + execution_time
        )

        if self.config.reward_mode == "inverse_time":

            reward = 1.0 / max(
                total_time_cost,
                1e-6,
            )

        else:

            reward = -total_time_cost

        result = {

            "task_id": task.task_id,

            "node_id": node.node_id,

            "arrival_time": task.arrival_time,

            "waiting_time": waiting_time,

            "execution_time": execution_time,

            "predicted_start_time": predicted_start,

            "predicted_finish_time": predicted_finish,

            "delay_time": delay_time,

            "process": process,
        }

        self.results.append(result)

        return reward, True, result

    # =================================================
    # RESET
    # =================================================

    def reset(self, *, seed=None, options=None):

        super().reset(seed=seed)

        self.round += 1
        self.episode_steps = 0
        self.results = []

        self.episode_finished = False

        self._setup_simulation()

        self.generate_qtasks()

        # First task arrival is handled at its first step.
        self.current_obs = self._get_obs()

        info = {
            "round": self.round,
            "total_tasks": len(self.tasks),
            "total_nodes": self.n_qnodes,
            "simulation_time": self.sim_env.now,
        }

        return self.current_obs, info

    # =================================================
    # STEP
    # =================================================

    def step(self, action):

        if self.episode_finished:
            raise RuntimeError(
                "Episode is finished. Call reset()."
            )

        self.episode_steps += 1

        action = int(action)

        if not self.action_space.contains(action):

            reward = self.config.invalid_action_penalty

            return (
                self._get_obs(),
                reward,
                False,
                False,
                {"invalid_action": True},
            )

        task = self.current_qtask

        # Select a QNode
        reward, accepted, result = (
            self.submit_task_to_qnode(
                task,
                action,
            )
        )

        # If incompatible, retain current task so the
        # agent can try another QNode.
        if not accepted:

            truncated = (
                self.episode_steps
                >= self.config.max_episode_steps
            )

            return (
                self._get_obs(),
                reward,
                False,
                truncated,
                result,
            )

        # Move to next QTask
        self.task_index += 1

        if self.task_index < len(self.tasks):

            self.current_qtask = (
                self.tasks[self.task_index]
            )

            terminated = False

        else:

            self.current_qtask = None

            # All tasks have been submitted.
            # Drain all remaining SimPy events so that
            # every QNode finishes its queued workload.
            self.sim_env.run()

            terminated = True
            self.episode_finished = True

        self.current_obs = self._get_obs()

        truncated = (
            self.episode_steps
            >= self.config.max_episode_steps
            and not terminated
        )

        if truncated:
            self.episode_finished = True

        info = {

            **result,

            "simulation_time": self.sim_env.now,

            "scheduled_tasks": self.task_index,

            "total_tasks": len(self.tasks),

            "completed_tasks": len(
                self.broker.completed_tasks
            ),

            "failed_tasks": len(
                self.broker.failed_tasks
            ),

            "broker_stats": self.broker.get_stats(),
        }

        return (
            self.current_obs,
            float(reward),
            terminated,
            truncated,
            info,
        )

    # =================================================
    # RESULTS
    # =================================================

    def collect_results(self):

        completed = [
            task
            for task in self.tasks
            if task.task_id in self.broker.completed_tasks
        ]

        total_tasks = len(self.tasks)

        waiting_times = [
            getattr(task, "waiting_time", 0.0)
            for task in completed
        ]

        execution_times = [
            getattr(task, "execution_time", 0.0)
            for task in completed
        ]

        completion_times = [
            task.finish_time
            for task in completed
            if task.finish_time is not None
        ]

        summary = {

            "total_tasks": total_tasks,

            "completed_tasks": len(completed),

            "failed_tasks": len(
                self.broker.failed_tasks
            ),

            "total_waiting_time": sum(waiting_times),

            "total_execution_time": sum(execution_times),

            "average_waiting_time": (
                float(np.mean(waiting_times))
                if waiting_times else 0.0
            ),

            "average_execution_time": (
                float(np.mean(execution_times))
                if execution_times else 0.0
            ),

            "makespan": (
                max(completion_times)
                if completion_times else 0.0
            ),
        }

        return summary

    # =================================================
    # RENDER
    # =================================================

    def render(self):

        print("\n========== QCloudRL ==========")

        print("Simulation time:", self.sim_env.now)

        print("Current task:", (
            self.current_qtask.task_id
            if self.current_qtask else None
        ))

        print("Scheduled:", self.task_index)

        print("Completed:", len(
            self.broker.completed_tasks
        ))

        print("==============================")

    def close(self):
        pass