
def test_two_tasks_wait_in_same_node_queue(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=2)

    node = make_node("QNODE_001", "washington")
    sim_env, broker = make_broker([node])

    broker.submit_tasks(tasks)

    # Both tasks are assigned to the same QNode.
    broker.assign_task(tasks[0].task_id, node.node_id)
    broker.assign_task(
        tasks[1].task_id,
        node.node_id,
        allow_busy=True,
    )

    broker.dispatch_task(tasks[0].task_id, execution_time=5.0)
    broker.dispatch_task(tasks[1].task_id, execution_time=3.0)

    sim_env.run()

    first = broker.get_execution_record(tasks[0].task_id)
    second = broker.get_execution_record(tasks[1].task_id)

    assert first.start_time == 0.0
    assert first.finish_time == 5.0

    assert second.start_time == 5.0
    assert second.finish_time == 8.0
    assert second.waiting_time == 5.0

    assert first.status == "completed"
    assert second.status == "completed"


def test_two_nodes_execute_in_parallel(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=2)

    node1 = make_node("QNODE_001", "washington")
    node2 = make_node("QNODE_002", "kolkata")

    sim_env, broker = make_broker([node1, node2])
    broker.submit_tasks(tasks)

    broker.assign_task(tasks[0].task_id, node1.node_id)
    broker.assign_task(tasks[1].task_id, node2.node_id)

    broker.dispatch_task(tasks[0].task_id, execution_time=5.0)
    broker.dispatch_task(tasks[1].task_id, execution_time=3.0)

    sim_env.run()

    first = broker.get_execution_record(tasks[0].task_id)
    second = broker.get_execution_record(tasks[1].task_id)

    assert first.start_time == 0.0
    assert second.start_time == 0.0

    assert first.finish_time == 5.0
    assert second.finish_time == 3.0

    assert sim_env.now == 5.0


def test_broker_execution_statistics(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=3)

    node = make_node("QNODE_001", "washington")
    sim_env, broker = make_broker([node])

    broker.submit_tasks(tasks)

    for task in tasks:
        broker.assign_task(
            task.task_id,
            node.node_id,
            allow_busy=True,
        )
        broker.dispatch_task(
            task.task_id,
            execution_time=2.0,
        )

    sim_env.run()

    stats = broker.get_stats()

    assert stats["submitted"] == 3
    assert stats["assigned"] == 3
    assert stats["completed"] == 3
    assert stats["failed"] == 0
    assert stats["pending_tasks"] == 0
    assert stats["assigned_tasks"] == 0
