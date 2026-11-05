from qcloudrl.circuits.circuit_service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker import Broker


def main():

    # ---------------------------------------
    # 1. Initialize Circuit Service
    # ---------------------------------------

    service = CircuitService(
        dataset_root="dataset/mqt_bench",
        manifest_path="data/circuit_manifest.json",
        cache_size=32,
    )

    records = service.index(
        limit=500,
        seed=42,
    )

    print("Indexed circuits:", len(records))

    # ---------------------------------------
    # 2. Create QTasks
    # ---------------------------------------

    factory = TaskFactory(service)

    tasks = factory.create_tasks(
        records=records,
        shots=1024,
        priority=0,
        arrival_interval=0.1,
        task_id_prefix="MQT500",
    )

    print("Created QTasks:", len(tasks))

    # ---------------------------------------
    # 3. Create QNodes
    # ---------------------------------------

    nodes = [
        QNode(
            node_id="QNODE_001",
            backend_name="washington",
            circuit_service=service,
        ),
        QNode(
            node_id="QNODE_002",
            backend_name="kolkata",
            circuit_service=service,
        ),
        QNode(
            node_id="QNODE_003",
            backend_name="hanoi",
            circuit_service=service,
        ),
        QNode(
            node_id="QNODE_004",
            backend_name="guadalupe",
            circuit_service=service,
        ),
    ]

    # ---------------------------------------
    # 4. Initialize Broker
    # ---------------------------------------

    broker = Broker()

    broker.register_nodes(nodes)

    # ---------------------------------------
    # 5. Submit QTasks
    # ---------------------------------------

    broker.submit_tasks(tasks)

    print("\nBroker observation:")
    print(broker.get_observation())

    # ---------------------------------------
    # 6. Inspect feasible nodes
    # ---------------------------------------

    task = broker.get_pending_tasks()[0]

    feasible_nodes = broker.get_feasible_nodes(task)

    print("\nTask:", task.task_id)

    print(
        "Feasible nodes:",
        [node.node_id for node in feasible_nodes]
    )

    # ---------------------------------------
    # 7. Assign and execute one task
    # ---------------------------------------

    if feasible_nodes:

        selected_node = feasible_nodes[0]

        broker.assign_task(
            task_id=task.task_id,
            node_id=selected_node.node_id,
            current_time=0.0,
        )

        result = broker.dispatch_task(task.task_id)

        print("\nExecution result:")
        print(result)

    # ---------------------------------------
    # 8. Statistics
    # ---------------------------------------

    print("\nBroker statistics:")
    print(broker.get_stats())

    print("\nCircuit cache:")
    print(service.cache_stats())


if __name__ == "__main__":
    main()