from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask import TaskFactory, TaskStatus
from qcloudrl.Qnode import QNode


def main():

    # 1. Initialize CircuitService
    circuit_service = CircuitService(
        dataset_dir="dataset/mqt_bench",
        dataset_name="mqt_bench",
        cache_capacity=32,
    )

    circuit_service.load_manifest()

    print("\nCircuitService initialized.")

    # 2. Create TaskFactory
    factory = TaskFactory(circuit_service)

    records = circuit_service.list_circuits()

    if not records:
        raise RuntimeError("No circuit records found.")

    # 3. Create one task
    task = factory.create_task(
        record=records[0],
        task_id="QTASK_000001",
        shots=1024,
        priority=1,
        arrival_time=0.0,
    )

    print("\nTask created:", task)
    print("Circuit initially loaded:", task.circuit_loaded)
    circuit = task.get_circuit()
    print("\n========== RESOURCE COMPATIBILITY ==========")
    print("Circuit ID:", task.circuit_id)
    print("Required qubits:", circuit.num_qubits)
    # print("Backend:", node.backend_name)
    # print("Available qubits:", node.num_qubits)
    # print("Can execute:", node.can_execute(task))

    # 4. Create QNode
    node = QNode(
        node_id="QNODE_001",
        backend_name="guadalupe",
        circuit_service=circuit_service,
    )

    print("\nQNode resource information:")
    print(node.get_resource_info())

    # 5. Queue and schedule task
    task.mark_queued(submitted_at=0.0)
    task.mark_scheduled(node_id=node.node_id)

    print("\nTask status:", task.status.value)

    # 6. Check resource capacity
    if not node.can_execute(task):
        print("Node cannot execute this task.")
        return

    print("Node can execute task.")

    # 7. Execute task
    result = node.execute_task(
        task=task,
        simulation_time=0.0,
    )

    print("\nExecution successful:", result["success"])
    print("Backend:", result["backend_name"])
    print("Shots:", result["shots"])
    print("Counts:", result["counts"])
    print("Elapsed seconds:", result["elapsed_seconds"])
    print("Transpiled depth:", result["transpiled_depth"])

    # 8. Check final task status
    print("\n========== FINAL TASK ==========")
    print("Task ID:", task.task_id)
    print("Status:", task.status.value)
    print("Circuit loaded:", task.circuit_loaded)
    print("Started:", task.started_at)
    print("Completed:", task.completed_at)

    # 9. Check node statistics
    print("\n========== NODE STATISTICS ==========")
    print(node.get_resource_info())

    # 10. Check CircuitService cache
    print("\n========== CIRCUIT CACHE ==========")
    print("Cache hits:", circuit_service.cache.hits)
    print("Cache misses:", circuit_service.cache.misses)
    print("Cache size:", circuit_service.cache.size)


if __name__ == "__main__":
    main()