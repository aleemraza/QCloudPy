
import pytest


def test_invalid_execution_duration_is_rejected(
    make_tasks, make_node, make_broker
):
    task = make_tasks(count=1)[0]
    node = make_node("QNODE_001", "washington")

    sim_env, broker = make_broker([node])

    broker.submit_task(task)
    broker.assign_task(task.task_id, node.node_id)

    with pytest.raises(ValueError, match="cannot be negative"):
        broker.dispatch_task(
            task.task_id,
            execution_time=-1.0,
        )

    # Invalid dispatch must not start execution.
    record = broker.get_execution_record(task.task_id)

    assert record.start_time is None
    assert record.finish_time is None
    assert record.status == "assigned"

    assert task.task_id in broker.assigned_tasks
    assert broker.node_resources[node.node_id].count == 0
    assert node.is_available


def test_valid_dispatch_after_invalid_request(
    make_tasks, make_node, make_broker
):
    task = make_tasks(count=1)[0]
    node = make_node("QNODE_001", "washington")

    sim_env, broker = make_broker([node])

    broker.submit_task(task)
    broker.assign_task(task.task_id, node.node_id)

    # First request is invalid.
    with pytest.raises(ValueError):
        broker.dispatch_task(
            task.task_id,
            execution_time=-1.0,
        )

    # The task should still be assigned and retryable.
    assert task.task_id in broker.assigned_tasks

    # Retry with a valid duration.
    broker.dispatch_task(
        task.task_id,
        execution_time=3.0,
    )

    sim_env.run()

    record = broker.get_execution_record(task.task_id)

    assert record.status == "completed"
    assert record.execution_time == 3.0
    assert record.finish_time == 3.0

    stats = broker.get_stats()

    assert stats["completed"] == 1
    assert stats["failed"] == 0
