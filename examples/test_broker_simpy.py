
import simpy

from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker


def main():

    print("\n========== QCloudRL Broker Test ==========\n")

    # 1. Initialize circuit service.
    circuit_service = CircuitService(
        dataset_dir="dataset/mqt_bench",
        dataset_name="mqt_bench",
        cache_capacity=32,
    )

    circuit_service.load_manifest()

    # 2. Create QTasks.
    factory = TaskFactory(circuit_service)

    records = circuit_service.list_circuits()

    tasks = factory.create_tasks(
        records=records[:3],
        shots=1024,
        priority=1,
        arrival_interval=1.0,
        first_arrival=0.0,
    )

    print("Created tasks:", len(tasks))

    # 3. Initialize QNodes.
    node1 = QNode(
        node_id="QNODE_001",
        backend_name="washington",
        circuit_service=circuit_service,
    )

    node2 = QNode(
        node_id="QNODE_002",
        backend_name="kolkata",
        circuit_service=circuit_service,
    )

    # 4. Initialize SimPy.
    sim_env = simpy.Environment()

    # 5. Initialize Broker.
    broker = Broker()

    broker.attach_simpy(sim_env)

    # 6. Register QNodes.
    broker.register_nodes([node1, node2])

    # 7. Submit QTasks.
    broker.submit_tasks(tasks)

    print("\nPending tasks:", len(broker.get_pending_tasks()))

    # 8. Assign tasks.
    # Example assignment decisions are manually supplied here.
    # Later, the scheduler will choose these assignments.

    assignment_plan = [
        (tasks[0].task_id, "QNODE_001", 5.0),
        (tasks[1].task_id, "QNODE_001", 3.0),
        (tasks[2].task_id, "QNODE_002", 4.0),
    ]

    processes = []

    for task_id, node_id, execution_time in assignment_plan:

        broker.assign_task(
            task_id=task_id,
            node_id=node_id,
            allow_busy=True,
        )

        process = broker.dispatch_task(
            task_id=task_id,
            execution_time=execution_time,
        )

        processes.append(process)

    # 9. Run the simulation.
    sim_env.run()

    # 10. Display execution records.
    print("\n========== EXECUTION RESULTS ==========\n")

    for record in broker.get_execution_records():

        print(record.to_dict())

    # 11. Display statistics.
    print("\n========== BROKER STATISTICS ==========\n")

    print(broker.get_stats())

    print("\nFinal simulation time:", sim_env.now)


if __name__ == "__main__":
    main()
