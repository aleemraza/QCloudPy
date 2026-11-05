from typing import Optional
import simpy
from qcloudrl.Broker.constraints import ConstraintManager
from qcloudrl.Broker.models import (
    Assignment,
    BrokerStats,
    ExecutionRecord,
)


class Broker:
    """
    Central coordinator for QCloudRL.

    Responsibilities:
        1. Register and manage QNodes.
        2. Accept and manage QTasks.
        3. Maintain the pending task queue.
        4. Check task-node compatibility.
        5. Assign tasks to nodes based on external decisions.
        6. Dispatch tasks and collect execution results.
        7. Provide system state to the Gymnasium environment.

    Scheduling algorithms are intentionally external.
    """

    def __init__(self, env=None):
        self.env = env

        # Resource management
        self.qnodes = {}

        # Task management
        self.qtasks = {}
        self.pending_tasks = []
        self.assigned_tasks = {}
        self.completed_tasks = []
        self.failed_tasks = []

        # Execution tracking
        self.assignments = []
        self.execution_records = {}

        # Components
        self.constraints = ConstraintManager()
        self.stats = BrokerStats()

    # --------------------------------------------------
    # Simulation time
    # --------------------------------------------------

    def get_current_time(self, current_time=None):
        """
        Get simulation time.

        Gymnasium or another simulation engine can pass
        current_time explicitly. If an environment exposing
        env.now is attached, use that as a fallback.
        """
        if current_time is not None:
            return float(current_time)

        if self.env is not None and hasattr(self.env, "now"):
            return float(self.env.now)

        return 0.0

    def set_environment(self, env):
        """Attach a simulation or Gym environment."""
        self.env = env

    # --------------------------------------------------
    # QNode management
    # --------------------------------------------------

    def register_node(self, qnode):
        """Register a QNode with the Broker."""

        node_id = qnode.node_id

        if node_id in self.qnodes:
            raise ValueError(
                f"QNode {node_id} is already registered."
            )

        self.qnodes[node_id] = qnode

        return node_id

    def register_nodes(self, qnodes):
        """Register multiple QNodes."""

        registered = []

        for qnode in qnodes:
            registered.append(
                self.register_node(qnode)
            )

        return registered

    def get_node(self, node_id):
        """Retrieve a registered QNode."""

        if node_id not in self.qnodes:
            raise KeyError(
                f"QNode {node_id} is not registered."
            )

        return self.qnodes[node_id]

    def get_nodes(self):
        """Return information about all registered QNodes."""

        return [
            node.get_resource_info()
            for node in self.qnodes.values()
        ]

    # --------------------------------------------------
    # QTask management
    # --------------------------------------------------

    def submit_task(self, task):
        """
        Submit one QTask to the Broker.

        The task is queued but not assigned to a QNode.
        """

        task_id = task.task_id

        if task_id in self.qtasks:
            raise ValueError(
                f"QTask {task_id} already exists."
            )

        if task.status.value != "created":
            raise ValueError(
                f"QTask {task_id} must be in CREATED state. "
                f"Current state: {task.status.value}"
            )

        task.mark_queued()

        self.qtasks[task_id] = task
        self.pending_tasks.append(task_id)

        self.stats.submitted += 1

        self.execution_records[task_id] = ExecutionRecord(
            task_id=task_id
        )

        return task_id

    def submit_tasks(self, tasks):
        """Submit multiple QTasks."""

        submitted = []

        for task in tasks:
            submitted.append(
                self.submit_task(task)
            )

        return submitted

    def get_task(self, task_id):
        """Retrieve a QTask."""

        if task_id not in self.qtasks:
            raise KeyError(
                f"QTask {task_id} does not exist."
            )

        return self.qtasks[task_id]

    def get_pending_tasks(self):
        """Return queued QTask objects."""

        return [
            self.qtasks[task_id]
            for task_id in self.pending_tasks
        ]

    # --------------------------------------------------
    # Constraint and compatibility management
    # --------------------------------------------------

    def check_task_node(self, task, node):
        """
        Check whether a QTask can execute on a QNode.

        This is a metadata-level check. Actual circuit
        capacity is checked again during QNode execution.
        """

        return self.constraints.check(task, node)

    def get_feasible_nodes(self, task):
        """
        Return currently available nodes that pass
        preliminary compatibility checks.
        """

        feasible = []

        for node in self.qnodes.values():
            compatible, _ = self.check_task_node(task, node)

            if compatible:
                feasible.append(node)

        return feasible

    def get_feasible_node_ids(self, task_id):
        """Return feasible node IDs for a task."""

        task = self.get_task(task_id)

        return [
            node.node_id
            for node in self.get_feasible_nodes(task)
        ]

    # --------------------------------------------------
    # Task assignment
    # --------------------------------------------------

    def assign_task(
        self,
        task_id,
        node_id,
        current_time=None,
        allow_busy=False,
    ):
        task = self.get_task(task_id)
        node = self.get_node(node_id)

        if task_id not in self.pending_tasks:
            raise ValueError(
                f"QTask {task_id} is not pending."
            )

        self.constraints.validate(
            task,
            node,
            check_availability=not allow_busy,
        )

        task.mark_scheduled(node_id)
        self.pending_tasks.remove(task_id)

        assignment = Assignment(
            task_id=task_id,
            node_id=node_id,
            assigned_at=self.get_current_time(current_time),
        )

        self.assignments.append(assignment)
        self.assigned_tasks[task_id] = node_id

        self.stats.assigned += 1

        record = self.execution_records[task_id]
        record.node_id = node_id
        record.status = "assigned"

        return assignment

    # --------------------------------------------------
    # Task execution
    # --------------------------------------------------

    def dispatch_task(self, task_id):
        """
        Dispatch an already assigned QTask to its QNode.

        QNode is responsible for loading the circuit,
        executing it, and updating the QTask lifecycle.
        """

        if task_id not in self.assigned_tasks:
            raise ValueError(
                f"QTask {task_id} has not been assigned."
            )

        task = self.get_task(task_id)
        node_id = self.assigned_tasks[task_id]
        node = self.get_node(node_id)

        record = self.execution_records[task_id]

        record.start_time = self.get_current_time()
        record.status = "running"

        try:
            result = node.execute_task(task)

            record.finish_time = self.get_current_time()
            record.result = result
            record.status = "completed"

            self.completed_tasks.append(task_id)
            self.stats.completed += 1

            return {
                "task_id": task_id,
                "node_id": node_id,
                "status": "completed",
                "result": result,
            }

        except Exception as exc:
            record.finish_time = self.get_current_time()
            record.error = str(exc)
            record.status = "failed"

            self.failed_tasks.append(task_id)
            self.stats.failed += 1

            return {
                "task_id": task_id,
                "node_id": node_id,
                "status": "failed",
                "error": str(exc),
            }

        finally:
            self.assigned_tasks.pop(task_id, None)

    # --------------------------------------------------
    # Gymnasium integration
    # --------------------------------------------------

    def get_observation(self):
        """
        Return a structured snapshot of the system.

        Gymnasium will later convert this information into
        NumPy arrays matching its observation_space.
        """

        node_states = []

        for node in self.qnodes.values():
            node_states.append({
                "node_id": node.node_id,
                "num_qubits": node.num_qubits,
                "available": node.is_available,
            })

        task_states = []

        for task_id in self.pending_tasks:
            task = self.qtasks[task_id]

            task_states.append({
                "task_id": task.task_id,
                "priority": task.priority,
                "arrival_time": task.arrival_time,
                "required_qubits": task.required_qubits,
                "shots": task.shots,
            })

        return {
            "simulation_time": self.get_current_time(),
            "nodes": node_states,
            "pending_tasks": task_states,
            "pending_count": len(self.pending_tasks),
            "assigned_count": len(self.assigned_tasks),
            "completed_count": len(self.completed_tasks),
            "failed_count": len(self.failed_tasks),
        }

    # --------------------------------------------------
    # Statistics
    # --------------------------------------------------

    def get_stats(self):
        """Return Broker statistics."""

        return {
            **self.stats.to_dict(),
            "registered_nodes": len(self.qnodes),
            "pending_tasks": len(self.pending_tasks),
            "currently_assigned": len(self.assigned_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
        }

    def reset(self):
        """
        Clear Broker-managed state.

        This does not reset QNode hardware/backend objects.
        Gymnasium should reset task and node simulation state
        according to its own episode-reset procedure.
        """

        self.qnodes.clear()
        self.qtasks.clear()

        self.pending_tasks.clear()
        self.assigned_tasks.clear()
        self.completed_tasks.clear()
        self.failed_tasks.clear()

        self.assignments.clear()
        self.execution_records.clear()

        self.stats = BrokerStats()
        
    def attach_simpy(self, simpy_env):

        self.simpy_env = simpy_env

        # Every QNode has an independent execution resource.
        self.node_resources = {
            node_id: simpy.Resource(
                simpy_env,
                capacity=1,
            )
            for node_id in self.qnodes
        }

        # Predicted next available times are useful for observations
        # and scheduling estimates. SimPy determines actual times.
        self.node_next_available_time = {
            node_id: float(simpy_env.now)
            for node_id in self.qnodes
        }
        
    def submit_qtask_to_qnode(
        self,
        task,
        node,
        execution_time,
    ):
        """
        SimPy process for one QTask.

        The process waits for the selected QNode resource,
        executes for a simulated duration, and records results.
        """

        if not hasattr(self, "simpy_env"):
            raise RuntimeError(
                "Call attach_simpy() before scheduling tasks."
            )

        def execution_process():

            resource = self.node_resources[node.node_id]
            record = self.execution_records[task.task_id]

            with resource.request() as request:

                # Wait until the selected QNode becomes available.
                yield request

                start_time = self.simpy_env.now

                waiting_time = max(
                    0.0,
                    start_time - task.arrival_time,
                )

                task.waiting_time = waiting_time
                task.execution_time = execution_time

                task.mark_running(start_time)

                record.start_time = start_time
                record.status = "running"

                # Simulate execution without blocking Python.
                yield self.simpy_env.timeout(execution_time)

                finish_time = self.simpy_env.now

                task.finish_time = finish_time

                result = {
                    "simulated": True,
                    "task_id": task.task_id,
                    "node_id": node.node_id,
                    "waiting_time": waiting_time,
                    "execution_time": execution_time,
                    "start_time": start_time,
                    "finish_time": finish_time,
                }

                task.mark_completed(
                    result=result,
                    completion_time=finish_time,
                )

                record.finish_time = finish_time
                record.result = result
                record.status = "completed"

                self.completed_tasks.append(task.task_id)
                self.assigned_tasks.pop(task.task_id, None)

                self.stats.completed += 1

                return result

        return self.simpy_env.process(execution_process())