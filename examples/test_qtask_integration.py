from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask import QTask, TaskFactory, TaskStatus


def main():

    # Initialize CircuitService
    circuit_service = CircuitService(
        dataset_dir="dataset/mqt_bench",
        dataset_name="mqt_bench",
        cache_capacity=32,
    )

    # Load existing manifest.
    # If no manifest exists, index the dataset first.
    circuit_service.load_manifest()

    print("\nCircuitService initialized.")

    # Create TaskFactory
    factory = TaskFactory(circuit_service)

    # Get indexed circuit records
    records = circuit_service.list_circuits()

    if not records:
        raise RuntimeError("No circuit records found.")

    # Create one task
    task = factory.create_task(
        record=records[0],
        task_id="QTASK_000001",
        shots=1024,
        priority=1,
        arrival_time=0.0,
        deadline=100.0,
    )

    print("\nTask created:")
    print(task)

    # Verify lazy loading
    print("\nCircuit loaded:", task.circuit_loaded)

    # Load circuit only when requested
    circuit = task.get_circuit()

    print("Circuit loaded:", task.circuit_loaded)
    print("Circuit qubits:", circuit.num_qubits)
    print("Circuit depth:", circuit.depth())

    # Test task lifecycle
    task.mark_queued(submitted_at=0.0)
    task.mark_scheduled(node_id="QNODE_001")
    task.mark_running(start_time=2.0)

    task.mark_completed(
        result={"counts": {"00": 500, "11": 524}},
        completion_time=5.0,
    )

    print("\nFinal task status:", task.status.value)

    print("\nTask dictionary:")
    print(task.to_dict())

    # Create multiple tasks without loading their circuits
    tasks = factory.create_tasks(
        records=records[:500],
        shots=1024,
        priority=0,
        arrival_interval=2.0,
        first_arrival=0.0,
    )

    print("\nMultiple tasks created:", len(tasks))

    for item in tasks:
        print(
            item.task_id,
            item.circuit_id,
            item.status.value,
            "Loaded:", item.circuit_loaded,
        )
        
    print("\n========== TASK FEATURES ==========")

    for task in tasks[:5]:
        print("\nTask ID:", task.task_id)
        print("Circuit ID:", task.circuit_id)
        print("Circuit Format:", task.circuit_format)
        print("Shots:", task.shots)
        print("Priority:", task.priority)
        print("Arrival Time:", task.arrival_time)
        print("Deadline:", task.deadline)
        print("Required Qubits:", task.required_qubits)
        print("Status:", task.status.value)
        print("Circuit Loaded:", task.circuit_loaded)
        print("Circuit Metadata:", task.circuit_metadata)
        
    print("\n========== ALL TASK SUMMARY ==========")

    for task in tasks:
        print(
            f"{task.task_id} | "
            f"Circuit={task.circuit_id} | "
            f"Shots={task.shots} | "
            f"Priority={task.priority} | "
            f"Arrival={task.arrival_time} | "
            f"Status={task.status.value}"
        )

    print("\nTotal Tasks:", len(tasks))
        
        


if __name__ == "__main__":
    main()