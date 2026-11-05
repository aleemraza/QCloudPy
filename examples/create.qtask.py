
from qcloudrl.circuits import CircuitService
from qcloudrl.QTask import TaskFactory

# Step 1: Initialize CircuitService.
service = CircuitService(
    dataset_root="dataset/mqt_bench",
    manifest_path="data/circuit_manifest.json",
    cache_size=32,
)

# Step 2: Index the dataset.
records = service.index(
    limit=500,
    seed=42,
)

# Step 3: Create TaskFactory.
factory = TaskFactory(service)

# Step 4: Convert circuit records into quantum jobs.
tasks = factory.create_tasks(
    records=records,
    shots=1024,
    priority=0,
    arrival_interval=0.1,
    task_id_prefix="MQT600",
)

# Step 5: Inspect the jobs.
print("Total tasks:", len(tasks))

for task in tasks[:3]:
    print(task.to_dict())

# Step 6: Check whether circuits were loaded.
print("Circuit cache:", service.cache_stats())
print("First task circuit loaded:", tasks[0].circuit_loaded)

# Step 7: Load one circuit only when needed.
circuit = tasks[0].get_circuit()

print("Circuit loaded:", tasks[0].circuit_loaded)
print(circuit)
