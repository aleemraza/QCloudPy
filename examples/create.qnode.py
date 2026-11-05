
from qcloudrl.circuits import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode import QNode


# --------------------------------------------------
# Step 1: Initialize CircuitService
# --------------------------------------------------

service = CircuitService(
    dataset_root="dataset/mqt_bench",
    manifest_path="data/circuit_manifest.json",
    cache_size=32,
)


# --------------------------------------------------
# Step 2: Index circuits
# --------------------------------------------------

records = service.index(
    limit=500,
    seed=42,
)


# --------------------------------------------------
# Step 3: Create QTasks
# --------------------------------------------------

factory = TaskFactory(service)

tasks = factory.create_tasks(
    records=records,
    shots=1024,
    priority=0,
    arrival_interval=0.1,
    task_id_prefix="MQT500",
)

print("Total tasks:", len(tasks))


# --------------------------------------------------
# Step 4: Create a QNode
# --------------------------------------------------

qnode = QNode(
    node_id="QNODE_001",
    backend_name="washington",
    circuit_service=service,
)

print("\nQNode information:")
print(qnode.get_resource_info())


# --------------------------------------------------
# Step 5: Select one QTask
# --------------------------------------------------

task = tasks[0]

# A Broker will perform these transitions in the
# complete system. We do them manually for now.
task.mark_queued()
task.mark_scheduled(qnode.node_id)


# --------------------------------------------------
# Step 6: Check resource availability
# --------------------------------------------------

if qnode.can_execute(task):

    print("\nExecuting task:", task.task_id)

    result = qnode.execute_task(task)

    print("\nExecution completed!")

    print("Task status:", task.status.value)
    print("Node status:", qnode.status.value)

    print("Backend:", result["backend_name"])
    print("Shots:", result["shots"])
    print("Counts:", result["counts"])

    print(
        "Execution time:",
        result["elapsed_seconds"],
        "seconds",
    )

else:
    print("QNode cannot execute this task")


# --------------------------------------------------
# Step 7: Inspect updated resource information
# --------------------------------------------------

print("\nUpdated QNode information:")
print(qnode.get_resource_info())

print("\nCircuit cache:")
print(service.cache_stats())
