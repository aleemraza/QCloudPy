
def test_register_multiple_nodes(make_node, make_broker):
    node1 = make_node("QNODE_001", "washington")
    node2 = make_node("QNODE_002", "kolkata")
    node3 = make_node("QNODE_003", "hanoi")

    _, broker = make_broker([node1, node2, node3])

    nodes = broker.get_nodes()

    assert len(nodes) == 3
    assert broker.get_node("QNODE_001") is node1
    assert broker.get_node("QNODE_002") is node2
    assert broker.get_node("QNODE_003") is node3


def test_submit_multiple_tasks(make_tasks, make_node, make_broker):
    tasks = make_tasks(count=5)

    node = make_node("QNODE_001")
    _, broker = make_broker([node])

    broker.submit_tasks(tasks)

    assert len(broker.qtasks) == 5
    assert len(broker.get_pending_tasks()) == 5

    stats = broker.get_stats()

    assert stats["submitted"] == 5
    assert stats["assigned"] == 0
    assert stats["completed"] == 0


def test_register_multiple_tasks_and_nodes(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=10)

    nodes = [
        make_node("QNODE_001", "washington"),
        make_node("QNODE_002", "kolkata"),
    ]

    _, broker = make_broker(nodes)
    broker.submit_tasks(tasks)

    assert len(broker.get_nodes()) == 2
    assert len(broker.get_pending_tasks()) == 10
