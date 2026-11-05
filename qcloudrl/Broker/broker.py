from typing import Dict, List, Optional
import simpy
from qcloudrl.Broker.models import (
    Assignment,
    BrokerStats,
    ExecutionRecord,
)
from qcloudrl.Broker.constraints import ConstraintManager
from qcloudrl.Qnode.models import NodeStatus


class Broker:
    """
    SimPy-based Broker for QCloudRL.

    Responsibilities:
        - QNode registration
        - QTask registration and arrival management
        - Task-node compatibility validation
        - Task assignment
        - SimPy-based abstract execution
        - Execution records and statistics

    The Broker does not implement scheduling policies.

    Execution durations are simulated virtual time.
    No Aer or real quantum hardware execution happens here.
    """

    def __init__(self, env=None):

        self.env = env
        self.simpy_env = env

        # -----------------------------------------
        # Registered resources and tasks
        # -----------------------------------------

        self.qnodes: Dict[str, object] = {}
        self.qtasks: Dict[str, object] = {}

        # -----------------------------------------
        # Task queues
        # -----------------------------------------

        # Tasks that have arrived and can be scheduled.
        self.pending_tasks: List[str] = []

        # Tasks registered but waiting for arrival.
        self.future_tasks: List[str] = []

        # Tasks assigned to QNodes.
        self.assigned_tasks: Dict[str, str] = {}

        # Terminal task collections.
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[str] = []

        # -----------------------------------------
        # Assignment and execution history
        # -----------------------------------------

        self.assignments: Dict[str, Assignment] = {}

        self.execution_records: Dict[str, ExecutionRecord] = {}

        # -----------------------------------------
        # SimPy resource management
        # -----------------------------------------

        self.node_resources = {}

        self.node_next_available_time = {}

        self.active_processes = {}

        self._dispatched_tasks = set()

        # -----------------------------------------
        # Constraint management
        # -----------------------------------------

        self.constraints = ConstraintManager()

        # -----------------------------------------
        # Statistics
        # -----------------------------------------

        self.stats = BrokerStats()

        if self.simpy_env is not None:
            self.env = self.simpy_env

    # =====================================================
    # SIMPY INITIALIZATION
    # =====================================================

    def attach_simpy(self, simpy_env):

        if simpy_env is None:
            raise ValueError("SimPy environment cannot be None.")

        self.simpy_env = simpy_env
        self.env = simpy_env

        for node_id in self.qnodes:
            self._create_node_resource(node_id)

    def _create_node_resource(self, node_id):

        if self.simpy_env is None:
            raise RuntimeError(
                "Attach a SimPy environment before creating resources."
            )

        self.node_resources[node_id] = simpy.Resource(
            self.simpy_env,
            capacity=1,
        )

        self.node_next_available_time[node_id] = float(
            self.simpy_env.now
        )

    def get_current_time(self):

        if self.simpy_env is None:
            return 0.0

        return float(self.simpy_env.now)

    # =====================================================
    # QNODE REGISTRATION
    # =====================================================

    def register_node(self, node):

        node_id = node.node_id

        if node_id in self.qnodes:
            raise ValueError(
                f"QNode {node_id} is already registered."
            )

        self.qnodes[node_id] = node

        if self.simpy_env is not None:
            self._create_node_resource(node_id)

        return node

    def register_nodes(self, nodes):

        registered = []

        for node in nodes:
            registered.append(
                self.register_node(node)
            )

        return registered

    def get_node(self, node_id):

        if node_id not in self.qnodes:
            raise KeyError(
                f"QNode {node_id} is not registered."
            )

        return self.qnodes[node_id]

    def get_nodes(self):

        return list(self.qnodes.values())

    # =====================================================
    # TASK SUBMISSION AND ARRIVAL MANAGEMENT
    # =====================================================

    def submit_task(self, task):
        """
        Register a QTask with the Broker.

        If its arrival time has already occurred, activate it
        immediately.

        Otherwise, register a SimPy arrival event.

        Future tasks remain in CREATED status until arrival.
        """

        task_id = task.task_id

        # -----------------------------------------
        # Validate task
        # -----------------------------------------

        if task_id in self.qtasks:
            raise ValueError(
                f"Task {task_id} is already registered."
            )

        task_status = getattr(
            task.status,
            "value",
            task.status,
        )

        if task_status != "created":
            raise ValueError(
                f"Task {task_id} must be in CREATED status. "
                f"Current status: {task_status}"
            )

        current_time = self.get_current_time()

        arrival_time = float(task.arrival_time)

        if arrival_time < 0:
            raise ValueError(
                "Task arrival time cannot be negative."
            )

        if arrival_time > current_time and self.simpy_env is None:
            raise RuntimeError(
                "A SimPy environment is required for future "
                "task arrivals. Call attach_simpy() first."
            )

        # -----------------------------------------
        # Register task
        # -----------------------------------------

        self.qtasks[task_id] = task

        self.execution_records[task_id] = ExecutionRecord(
            task_id=task_id,
            submitted_at=current_time,
            status="waiting_for_arrival",
        )

        self.stats.submitted += 1

        # -----------------------------------------
        # Activate or schedule arrival
        # -----------------------------------------

        if arrival_time <= current_time:

            self._activate_task(task)

        else:

            self.future_tasks.append(task_id)

            self.simpy_env.process(
                self._schedule_task_arrival(task)
            )

        return task

    def submit_tasks(self, tasks):

        submitted = []

        for task in tasks:
            submitted.append(
                self.submit_task(task)
            )

        return submitted

    def _activate_task(self, task):
        """
        Move an arrived task into the pending queue.
        """

        task_id = task.task_id

        # Task must still be registered.
        if task_id not in self.qtasks:
            return False

        # Prevent duplicate activation.
        if task_id in self.pending_tasks:
            return False

        if task_id in self.assigned_tasks:
            return False

        if task_id in self.completed_tasks:
            return False

        if task_id in self.failed_tasks:
            return False

        current_time = self.get_current_time()

        task_status = getattr(
            task.status,
            "value",
            task.status,
        )

        # -----------------------------------------
        # Update QTask lifecycle
        # -----------------------------------------

        if task_status == "created":

            task.mark_queued(
                submitted_at=current_time
            )

        elif task_status != "queued":

            raise ValueError(
                f"Cannot activate task {task_id}. "
                f"Current status: {task_status}"
            )

        # -----------------------------------------
        # Update Broker queues
        # -----------------------------------------

        if task_id in self.future_tasks:
            self.future_tasks.remove(task_id)

        self.pending_tasks.append(task_id)

        self.execution_records[task_id].status = "pending"

        return True

    def _schedule_task_arrival(self, task):
        """
        SimPy process that activates a future task
        when its arrival time is reached.
        """

        arrival_time = float(task.arrival_time)

        current_time = float(self.simpy_env.now)

        delay = max(
            0.0,
            arrival_time - current_time,
        )

        if delay > 0:

            yield self.simpy_env.timeout(delay)

        self._activate_task(task)

    # =====================================================
    # TASK ACCESS
    # =====================================================

    def get_task(self, task_id):

        if task_id not in self.qtasks:
            raise KeyError(
                f"Task {task_id} is not registered."
            )

        return self.qtasks[task_id]

    def get_pending_tasks(self):

        return [
            self.qtasks[task_id]
            for task_id in self.pending_tasks
        ]

    def get_future_tasks(self):

        return [
            self.qtasks[task_id]
            for task_id in self.future_tasks
        ]

    # =====================================================
    # TASK-NODE COMPATIBILITY
    # =====================================================

    def check_task_node(self, task, node):

        return self.constraints.check(
            task=task,
            node=node,
            check_availability=True,
        )

    def get_feasible_nodes(self, task):

        feasible_nodes = []

        for node in self.qnodes.values():

            compatible, _ = self.constraints.check(
                task=task,
                node=node,
                check_availability=True,
            )

            if compatible:
                feasible_nodes.append(node)

        return feasible_nodes

    def get_feasible_node_ids(self, task):

        return [
            node.node_id
            for node in self.get_feasible_nodes(task)
        ]

    # =====================================================
    # TASK ASSIGNMENT
    # =====================================================

    def assign_task(
        self,
        task_id,
        node_id,
        current_time=None,
        allow_busy=False,
    ):
        """
        Assign a pending task to a QNode.

        allow_busy=True permits assignment to a compatible
        QNode even when it is currently executing another task.

        SimPy will manage the actual resource queue.
        """

        if task_id not in self.qtasks:
            raise KeyError(
                f"Task {task_id} is not registered."
            )

        if node_id not in self.qnodes:
            raise KeyError(
                f"QNode {node_id} is not registered."
            )

        if task_id not in self.pending_tasks:
            raise ValueError(
                f"Task {task_id} is not in the pending queue."
            )

        if task_id in self.assigned_tasks:
            raise ValueError(
                f"Task {task_id} has already been assigned."
            )

        task = self.qtasks[task_id]

        node = self.qnodes[node_id]

        # -----------------------------------------
        # Validate compatibility
        # -----------------------------------------

        try:

            self.constraints.validate(
                task=task,
                node=node,
                check_availability=not allow_busy,
            )

        except Exception:

            self.stats.rejected += 1

            raise

        # -----------------------------------------
        # Determine assignment time
        # -----------------------------------------

        if current_time is None:
            current_time = self.get_current_time()

        current_time = float(current_time)

        # -----------------------------------------
        # Update task lifecycle
        # -----------------------------------------

        task.mark_scheduled(node_id)

        # -----------------------------------------
        # Update Broker state
        # -----------------------------------------

        assignment = Assignment(
            task_id=task_id,
            node_id=node_id,
            assigned_at=current_time,
            status="assigned",
        )

        self.assignments[task_id] = assignment

        self.pending_tasks.remove(task_id)

        self.assigned_tasks[task_id] = node_id

        record = self.execution_records[task_id]

        record.node_id = node_id
        record.assigned_at = current_time
        record.status = "assigned"

        self.stats.assigned += 1

        return assignment

    # =====================================================
    # QNODE STATUS MANAGEMENT
    # =====================================================

    def _set_node_busy(self, node):

        node.status = NodeStatus.BUSY

    def _release_node(self, node):

        # Do not accidentally bring an offline/error
        # QNode back online.
        if node.status == NodeStatus.BUSY:
            node.status = NodeStatus.IDLE

    # =====================================================
    # TASK DISPATCH
    # =====================================================

    def dispatch_task(self, task_id, execution_time):
        """
        Start a SimPy execution process for an assigned task.
        """

        if self.simpy_env is None:
            raise RuntimeError(
                "SimPy environment is not attached."
            )

        if task_id not in self.assigned_tasks:
            raise ValueError(
                f"Task {task_id} has not been assigned."
            )

        if task_id in self._dispatched_tasks:
            raise ValueError(
                f"Task {task_id} has already been dispatched."
            )

        execution_time = float(execution_time)

        if execution_time < 0:
            raise ValueError(
                "Execution time cannot be negative."
            )

        if execution_time != execution_time or execution_time == float("inf"):
            raise ValueError(
                "Execution time must be finite."
            )

        task = self.qtasks[task_id]

        node_id = self.assigned_tasks[task_id]

        node = self.qnodes[node_id]

        process = self.simpy_env.process(
            self.submit_qtask_to_qnode(
                task=task,
                node=node,
                execution_time=execution_time,
            )
        )

        self._dispatched_tasks.add(task_id)

        self.active_processes[task_id] = process

        return process

    # =====================================================
    # SIMPY EXECUTION PROCESS
    # =====================================================

    def submit_qtask_to_qnode(
        self,
        task,
        node,
        execution_time,
    ):
        """
        Abstract QTask execution using SimPy.

        SimPy controls resource waiting and virtual execution time.
        No quantum circuit is executed by Aer or IBM hardware.
        """

        task_id = task.task_id

        node_id = node.node_id

        resource = self.node_resources.get(node_id)

        if resource is None:
            raise RuntimeError(
                f"No SimPy resource exists for QNode {node_id}."
            )

        record = self.execution_records[task_id]

        assignment = self.assignments[task_id]

        acquired = False

        try:

            # -------------------------------------
            # Wait for task arrival if necessary
            # -------------------------------------

            if self.simpy_env.now < task.arrival_time:

                yield self.simpy_env.timeout(
                    task.arrival_time - self.simpy_env.now
                )

            # -------------------------------------
            # Request QNode resource
            # -------------------------------------

            with resource.request() as request:

                yield request

                acquired = True

                start_time = float(self.simpy_env.now)

                # ---------------------------------
                # Start execution
                # ---------------------------------

                self._set_node_busy(node)

                task.mark_running(
                    start_time=start_time
                )

                record.start_time = start_time

                record.waiting_time = (
                    start_time - assignment.assigned_at
                )

                record.execution_time = float(execution_time)

                record.status = "running"

                assignment.status = "running"

                # ---------------------------------
                # Simulated execution
                # ---------------------------------

                yield self.simpy_env.timeout(
                    execution_time
                )

                finish_time = float(self.simpy_env.now)

                # ---------------------------------
                # Simulated execution result
                # ---------------------------------

                result = {
                    "task_id": task_id,
                    "node_id": node_id,
                    "simulated": True,
                    "start_time": start_time,
                    "finish_time": finish_time,
                    "execution_time": float(execution_time),
                }

                # ---------------------------------
                # Complete QTask
                # ---------------------------------

                task.mark_completed(
                    result=result,
                    completion_time=finish_time,
                )

                # ---------------------------------
                # Update execution record
                # ---------------------------------

                record.finish_time = finish_time

                record.execution_time = (
                    finish_time - start_time
                )

                record.status = "completed"

                record.result = result

                assignment.status = "completed"

                # ---------------------------------
                # Update Broker collections
                # ---------------------------------

                self.completed_tasks.append(task_id)

                self.assigned_tasks.pop(task_id, None)

                self.stats.completed += 1

        except Exception as exc:

            # -------------------------------------
            # Handle execution failure
            # -------------------------------------

            record.status = "failed"

            record.error = str(exc)

            record.finish_time = float(
                self.simpy_env.now
            )

            assignment.status = "failed"

            try:

                task_status = getattr(
                    task.status,
                    "value",
                    task.status,
                )

                if task_status not in (
                    "completed",
                    "failed",
                    "cancelled",
                ):

                    task.mark_failed(str(exc))

            except Exception:
                pass

            if task_id not in self.failed_tasks:

                self.failed_tasks.append(task_id)

                self.stats.failed += 1

            self.assigned_tasks.pop(task_id, None)

        finally:

            # -------------------------------------
            # Release QNode
            # -------------------------------------

            if acquired:

                self._release_node(node)

            self.node_next_available_time[node_id] = float(
                self.simpy_env.now
            )

            self.active_processes.pop(task_id, None)

    # =====================================================
    # ASSIGNMENT STATUS
    # =====================================================

    def _update_assignment_status(self, task_id, status):

        assignment = self.assignments.get(task_id)

        if assignment is not None:
            assignment.status = status

    # =====================================================
    # EXECUTION HISTORY
    # =====================================================

    def get_execution_record(self, task_id):

        if task_id not in self.execution_records:
            raise KeyError(
                f"No execution record exists for task {task_id}."
            )

        return self.execution_records[task_id]

    def get_execution_history(self):

        return [
            record.to_dict()
            for record in self.execution_records.values()
        ]

    # =====================================================
    # OBSERVATION
    # =====================================================

    def get_observation(self):
        """
        Return the current Broker state.

        Pending task details include only tasks that have arrived.
        Future tasks are counted separately.
        """

        current_time = self.get_current_time()

        nodes = []

        for node_id, node in self.qnodes.items():

            resource = self.node_resources.get(node_id)

            nodes.append({
                "node_id": node_id,
                "num_qubits": node.num_qubits,
                "status": getattr(
                    node.status,
                    "value",
                    node.status,
                ),
                "is_available": node.is_available,
                "resource_users": (
                    resource.count
                    if resource is not None
                    else 0
                ),
                "resource_queue_length": (
                    len(resource.queue)
                    if resource is not None
                    else 0
                ),
            })

        pending = []

        for task_id in self.pending_tasks:

            task = self.qtasks[task_id]

            pending.append({
                "task_id": task_id,
                "arrival_time": task.arrival_time,
                "required_qubits": task.required_qubits,
                "shots": task.shots,
                "priority": task.priority,
                "status": getattr(
                    task.status,
                    "value",
                    task.status,
                ),
            })

        return {
            "simulation_time": current_time,
            "nodes": nodes,
            "pending_tasks": pending,
            "pending_count": len(self.pending_tasks),
            "future_task_count": len(self.future_tasks),
            "assigned_count": len(self.assigned_tasks),
            "completed_count": len(self.completed_tasks),
            "failed_count": len(self.failed_tasks),
        }

    # =====================================================
    # STATISTICS
    # =====================================================

    def get_stats(self):

        stats = self.stats.to_dict()

        stats.update({
            "registered_nodes": len(self.qnodes),
            "registered_tasks": len(self.qtasks),
            "pending_tasks": len(self.pending_tasks),
            "future_tasks": len(self.future_tasks),
            "assigned_tasks": len(self.assigned_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
        })

        return stats

    # =====================================================
    # RESET
    # =====================================================

    def reset(self, preserve_nodes=True):
        """
        Reset Broker state.

        preserve_nodes=True:
            Keep registered QNode objects.

        preserve_nodes=False:
            Remove registered QNodes.

        Call reset only when the previous simulation has no
        active execution processes.
        """

        existing_nodes = (
            list(self.qnodes.values())
            if preserve_nodes
            else []
        )

        # -----------------------------------------
        # Clear task state
        # -----------------------------------------

        self.qtasks.clear()

        self.pending_tasks.clear()

        self.future_tasks.clear()

        self.assigned_tasks.clear()

        self.completed_tasks.clear()

        self.failed_tasks.clear()

        # -----------------------------------------
        # Clear history
        # -----------------------------------------

        self.assignments.clear()

        self.execution_records.clear()

        # -----------------------------------------
        # Clear execution state
        # -----------------------------------------

        self.active_processes.clear()

        self._dispatched_tasks.clear()

        self.node_resources.clear()

        self.node_next_available_time.clear()

        # -----------------------------------------
        # Reset statistics
        # -----------------------------------------

        self.stats.reset()

        # -----------------------------------------
        # Restore QNodes if requested
        # -----------------------------------------

        self.qnodes.clear()

        if preserve_nodes:

            for node in existing_nodes:

                if node.status == NodeStatus.BUSY:
                    node.status = NodeStatus.IDLE

                self.qnodes[node.node_id] = node

        # -----------------------------------------
        # Recreate SimPy resources
        # -----------------------------------------

        if self.simpy_env is not None:

            for node_id in self.qnodes:
                self._create_node_resource(node_id)

        return True


