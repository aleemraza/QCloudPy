
def test_broker_observation_contains_simulation_state(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=2)
    node = make_node("QNODE_001", "washington")

    sim_env, broker = make_broker([node])
    broker.submit_tasks(tasks)

    observation = broker.get_observation()

    assert isinstance(observation, dict)
    assert "simulation_time" in observation
    assert observation["simulation_time"] == sim_env.now


def test_execution_history_is_recorded(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=2)
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

    records = broker.get_execution_records()

    assert len(records) == 2

    for record in records:
        assert record.status == "completed"
        assert record.start_time is not None
        assert record.finish_time is not None
        assert record.execution_time == 2.0
        assert record.result is not None


def test_execution_record_lookup(
    make_tasks, make_node, make_broker
):
    task = make_tasks(count=1)[0]
    node = make_node("QNODE_001", "washington")

    _, broker = make_broker([node])
    broker.submit_task(task)

    record = broker.get_execution_record(task.task_id)

    assert record is not None
    assert record.task_id == task.task_id
    assert record.status == "pending"
