
"""
QCloudRL Broker Admission and Submission Test

Purpose:
    1. Load the existing circuit manifest.
    2. Enrich circuit records with qubit-count metadata.
    3. Validate CircuitRecord metadata.
    4. Create QTasks using TaskFactory.
    5. Verify QTask resource requirements.
    6. Initialize QNodes.
    7. Inspect the actual Broker API.
    8. Submit tasks through the existing Broker interface.
    9. Inspect Broker statistics and rejection history.

Important:
    - Does not construct QuantumCircuit objects during metadata extraction.
    - Does not call unsupported Broker methods.
    - Does not benchmark admission if metadata is incomplete.
"""


# ============================================================
# 0. FORCE PYTHON TO USE THE CURRENT QCloudPy PROJECT
# ============================================================

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Put QCloudPy before other project locations.
project_root_str = str(PROJECT_ROOT)

sys.path = [
    p for p in sys.path
    if Path(p or ".").resolve() != PROJECT_ROOT.resolve()
]

sys.path.insert(0, project_root_str)

print("\n========== PYTHON PROJECT VALIDATION ==========")
print("Current project:", PROJECT_ROOT)
print("Python executable:", sys.executable)

# Import project modules only after correcting sys.path.
import inspect
import re
from time import perf_counter

import simpy

import qcloudrl.circuits.registry as registry_module

from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker

print("Imported registry:", registry_module.__file__)

# Make sure Python imported the correct implementation.
EXPECTED_REGISTRY = (
    PROJECT_ROOT / "qcloudrl" / "circuits" / "registry.py"
).resolve()

ACTUAL_REGISTRY = Path(registry_module.__file__).resolve()

assert ACTUAL_REGISTRY == EXPECTED_REGISTRY, (
    f"Wrong registry imported!\n"
    f"Expected: {EXPECTED_REGISTRY}\n"
    f"Actual:   {ACTUAL_REGISTRY}"
)

assert hasattr(
    registry_module.CircuitRegistry,
    "_extract_qubit_count"
), "Current CircuitRegistry does not contain _extract_qubit_count!"

print("Registry import validation: PASSED")
print("Qubit extraction method: AVAILABLE")



# ============================================================
# 1. TIMING HELPER
# ============================================================

def timed(label, function):

    print(f"\n[START] {label}", flush=True)

    start = perf_counter()

    result = function()

    elapsed = perf_counter() - start

    print(
        f"[DONE] {label} | Time: {elapsed:.3f} seconds",
        flush=True,
    )

    return result


# ============================================================
# 2. INITIALIZE CIRCUIT SERVICE
# ============================================================

print("\n========== BROKER ADMISSION TEST ==========", flush=True)

circuit_service = timed(
    "Initialize CircuitService",
    lambda: CircuitService(
        dataset_dir="dataset/mqt_bench",
        dataset_name="mqt_bench",
        cache_capacity=32,
    ),
)

registry = circuit_service.registry

print("\n========== REGISTRY INFORMATION ==========")

print("Registry class:", type(registry))
print("Registry source:", inspect.getfile(type(registry)))
print("Dataset directory:", registry.dataset_dir)


# ============================================================
# 3. LOAD EXISTING MANIFEST
# ============================================================

timed(
    "Load dataset manifest",
    circuit_service.load_manifest,
)

print("Records loaded:", len(registry))


# ============================================================
# 4. ENRICH CIRCUIT METADATA
# ============================================================

print("\n========== ENRICHING CIRCUIT METADATA ==========")

updated_records = timed(
    "Index and enrich circuit records",
    lambda: registry.index_dataset(),
)

manifest_path = timed(
    "Save enriched manifest",
    registry.save_manifest,
)

print("Records processed:", len(updated_records))
print("Manifest saved:", manifest_path)


# ============================================================
# 5. VALIDATE CIRCUIT METADATA
# ============================================================

records = timed(
    "Read circuit records",
    circuit_service.list_circuits,
)

with_qubits = [
    record for record in records
    if record.metadata.get("num_qubits") is not None
]

without_qubits = [
    record for record in records
    if record.metadata.get("num_qubits") is None
]

print("\n========== CIRCUIT METADATA VALIDATION ==========")

print("Total records:", len(records))
print("Records with qubit metadata:", len(with_qubits))
print("Records without qubit metadata:", len(without_qubits))

print("\nFirst 15 records:")

for record in records[:15]:

    print(
        f"{record.name:35} "
        f"Qubits: {str(record.metadata.get('num_qubits')):>4} "
        f"Source: {record.metadata.get('num_qubits_source')}"
    )


# ============================================================
# 6. DIRECT EXTRACTION DIAGNOSTIC
# ============================================================

print("\n========== DIRECT EXTRACTION DIAGNOSTIC ==========")

if records:

    record = records[0]
    file_path = Path(record.file_path)

    print("Circuit:", record.name)
    print("File:", file_path)
    print("File exists:", file_path.exists())
    print("Format:", record.circuit_format)

    if file_path.exists():

        direct_result = registry._extract_qubit_count(
            file_path,
            record.circuit_format,
        )

        print("Direct extraction result:", direct_result)

        source = file_path.read_text(
            encoding="utf-8-sig"
        )

        global_refs = re.findall(
            r"\$(\d+)\b",
            source,
        )

        print(
            "Global qubit references:",
            len(global_refs),
        )

        print(
            "First 20 references:",
            global_refs[:20],
        )

else:
    raise RuntimeError("No circuit records were loaded.")


# ============================================================
# 7. STOP IF METADATA IS INCOMPLETE
# ============================================================

if without_qubits:

    print("\n========== METADATA VALIDATION FAILED ==========")

    print(
        f"{len(without_qubits)} records do not have "
        "qubit-count metadata."
    )

    print("Broker testing has been stopped.")

    print("\nFirst 10 records missing metadata:")

    for record in without_qubits[:10]:

        print(
            record.name,
            "| Format:", record.circuit_format,
            "| File:", record.file_path,
        )

    raise RuntimeError(
        "Cannot continue Broker admission testing: "
        "circuit qubit metadata is incomplete."
    )


print("\nMETADATA VALIDATION PASSED")


# ============================================================
# 8. SELECT CIRCUITS AND CREATE TASK FACTORY
# ============================================================

selected_records = records[:10]

print("\nSelected circuits:", len(selected_records))

task_factory = TaskFactory(circuit_service)


# ============================================================
# 9. CREATE QTASKS
# ============================================================

tasks = timed(
    "Create 10 QTasks",
    lambda: task_factory.create_tasks(
        records=selected_records,
        shots=1024,
        priority=0,
        arrival_interval=0.5,
        first_arrival=0.0,
    ),
)

print("Created tasks:", len(tasks))


# ============================================================
# 10. VALIDATE QTASK RESOURCE REQUIREMENTS
# ============================================================

print("\n========== QTASK METADATA CHECK ==========")

for task in tasks:

    print(
        task.task_id,
        "| Required qubits:", task.required_qubits,
        "| Circuit loaded:", task.circuit_loaded,
    )

print("\n========== TASK REQUIREMENTS ==========")

for task in tasks:

    print(
        f"Task={task.task_id} | "
        f"Required qubits={task.required_qubits} | "
        f"Arrival={task.arrival_time}",
    )


# Validate TaskFactory metadata transfer.

missing_task_requirements = [
    task for task in tasks
    if task.required_qubits is None
]

if missing_task_requirements:

    raise RuntimeError(
        f"{len(missing_task_requirements)} QTasks have "
        "missing required_qubits. Check TaskFactory."
    )

# Verify that circuit loading remains lazy.

loaded_tasks = [
    task for task in tasks
    if task.circuit_loaded
]

if loaded_tasks:

    raise RuntimeError(
        "Unexpected circuit loading during task creation."
    )

print("\nQTask metadata validation PASSED")
print("All tasks have required_qubits.")
print("All circuits remain unloaded.")


# ============================================================
# 11. CREATE FOUR QNODES
# ============================================================

def create_qnodes():

    return [
        QNode(
            node_id="node_0",
            backend_name="washington",
            circuit_service=circuit_service,
        ),

        QNode(
            node_id="node_1",
            backend_name="kolkata",
            circuit_service=circuit_service,
        ),

        QNode(
            node_id="node_2",
            backend_name="hanoi",
            circuit_service=circuit_service,
        ),

        QNode(
            node_id="node_3",
            backend_name="guadalupe",
            circuit_service=circuit_service,
        ),
    ]


qnodes = timed(
    "Create four QNodes",
    create_qnodes,
)

print("\n========== QNODE INFORMATION ==========")

for node in qnodes:

    print(
        f"{node.node_id} | "
        f"Backend={node.backend_name} | "
        f"Qubits={node.num_qubits} | "
        f"Status={node.status}",
    )


# ============================================================
# 12. INITIALIZE BROKER
# ============================================================

broker = Broker()

print("\n========== BROKER API INSPECTION ==========")

print("Broker source:", inspect.getfile(type(broker)))

for name in dir(broker):

    if name.startswith("_"):
        continue

    attribute = getattr(broker, name)

    if callable(attribute):

        try:
            print(f"{name}{inspect.signature(attribute)}")

        except (TypeError, ValueError):
            print(name)


# ============================================================
# 13. REGISTER QNODES
# ============================================================

timed(
    "Register QNodes with Broker",
    lambda: broker.register_nodes(qnodes),
)


# ============================================================
# 14. ATTACH SIMPY ENVIRONMENT
# ============================================================

simpy_env = simpy.Environment()

timed(
    "Attach SimPy environment",
    lambda: broker.attach_simpy(simpy_env),
)


# ============================================================
# 15. SUBMIT TASKS TO BROKER
# ============================================================

print("\n========== BROKER SUBMISSION TEST ==========")

submission_start = perf_counter()

submission_result = timed(
    "Submit all tasks to Broker",
    lambda: broker.submit_tasks(tasks),
)

submission_time = perf_counter() - submission_start

print("Submission result:", submission_result)
print(
    f"Total submission time: {submission_time:.6f} seconds"
)


# ============================================================
# 16. SIMPY EXECUTION
# ============================================================

print("\n========== SIMPY EXECUTION ==========")

print("Initial simulation time:", simpy_env.now)

# Process events that are already scheduled.
# The Broker may create additional events during submission.
timed(
    "Run SimPy environment",
    lambda: simpy_env.run(),
)

print("Final simulation time:", simpy_env.now)


# ============================================================
# 17. BROKER STATISTICS
# ============================================================

print("\n========== BROKER STATISTICS ==========")

stats = broker.get_stats()

for key, value in stats.items():

    print(f"{key:<30}: {value}")


# ============================================================
# 18. REJECTION HISTORY
# ============================================================

print("\n========== REJECTION HISTORY ==========")

rejections = broker.get_rejection_history()

if rejections:

    for item in rejections:
        print(item)

else:
    print("No rejected tasks recorded.")


# ============================================================
# 19. FINAL CIRCUIT LOADING CHECK
# ============================================================

print("\n========== FINAL LAZY-LOADING CHECK ==========")

for task in tasks:

    print(
        task.task_id,
        "| Required qubits:", task.required_qubits,
        "| Circuit loaded:", task.circuit_loaded,
    )


# ============================================================
# 20. TEST SUMMARY
# ============================================================

print("\n========== TEST SUMMARY ==========")

print("Circuit records:", len(records))
print("Records with qubit metadata:", len(with_qubits))
print("QTasks created:", len(tasks))
print("QNodes registered:", len(qnodes))
print("Submission time:", f"{submission_time:.6f} seconds")
print("SimPy final time:", simpy_env.now)

print("\n========== TEST COMPLETED ==========")
