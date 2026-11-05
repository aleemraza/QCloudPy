
import pytest

from qcloudrl.Broker.constraints import (
    QubitInsufficientError,
    NodeUnavailableError,
)


def test_reject_task_with_insufficient_qubits(
    make_tasks, make_node, make_broker
):
    tasks = make_tasks(count=1)
    task = tasks[0]

    # Washington provides 127 qubits.
    task.required_qubits = 128

    node = make_node("QNODE_001", "washington")
    _, broker = make_broker([node])

    broker.submit_task(task)

    with pytest.raises(QubitInsufficientError):
        broker.assign_task(
            task_id=task.task_id,
            node_id=node.node_id,
        )

    # Rejected tasks must remain unassigned.
    assert task.task_id in broker.pending_tasks
    assert task.task_id not in broker.assigned_tasks


def test_reject_task_on_offline_node(
    make_tasks, make_node, make_broker
):
    task = make_tasks(count=1)[0]
    node = make_node("QNODE_001", "washington")

    _, broker = make_broker([node])
    broker.submit_task(task)

    node.set_offline()

    with pytest.raises(NodeUnavailableError):
        broker.assign_task(
            task_id=task.task_id,
            node_id=node.node_id,
        )

    assert task.task_id in broker.pending_tasks
    assert task.task_id not in broker.assigned_tasks
