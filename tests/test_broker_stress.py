
def test_fifty_tasks_across_two_nodes(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=50)

    node1 = make_node("QNODE_001", "washington")
    node2 = make_node("QNODE_002", "washington")

    sim_env, broker = make_broker([node1, node2])
    broker.submit_tasks(tasks)

    nodes = [node1, node2]

    for index, task in enumerate(tasks):
        node = nodes[index % len(nodes)]

        broker.assign_task(
            task_id=task.task_id,
            node_id=node.node_id,
            allow_busy=True,
        )

        broker.dispatch_task(
            task_id=task.task_id,
            execution_time=1.0,
        )

    sim_env.run()

    stats = broker.get_stats()
    records = broker.get_execution_records()

    assert len(records) == 50
    assert stats["submitted"] == 50
    assert stats["assigned"] == 50
    assert stats["completed"] == 50
    assert stats["failed"] == 0
    assert stats["pending_tasks"] == 0
    assert stats["assigned_tasks"] == 0


def test_stress_test_preserves_all_task_records(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=50)

    nodes = [
        make_node("QNODE_001", "washington"),
        make_node("QNODE_002", "washington"),
        make_node("QNODE_003", "washington"),
    ]

    sim_env, broker = make_broker(nodes)
    broker.submit_tasks(tasks)

    for index, task in enumerate(tasks):
        node = nodes[index % 3]

        broker.assign_task(
            task.task_id,
            node.node_id,
            allow_busy=True,
        )

        broker.dispatch_task(
            task.task_id,
            execution_time=0.5,
        )

    sim_env.run()

    records = broker.get_execution_records()
    recorded_ids = {record.task_id for record in records}
    submitted_ids = {task.task_id for task in tasks}

    assert recorded_ids == submitted_ids
    assert len(recorded_ids) == 50
