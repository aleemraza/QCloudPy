
def test_tasks_enter_pending_queue_at_arrival_time(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(
        count=3,
        arrival_interval=1.0,
        first_arrival=0.0,
    )

    node = make_node("QNODE_001", "washington")
    sim_env, broker = make_broker([node])

    broker.submit_tasks(tasks)

    # At time 0, only the first task should be visible.
    assert len(broker.get_pending_tasks()) == 1

    # Advance beyond the second task's arrival.
    sim_env.run(until=1.1)
    assert len(broker.get_pending_tasks()) == 2

    # Advance beyond the third task's arrival.
    sim_env.run(until=2.1)
    assert len(broker.get_pending_tasks()) == 3
