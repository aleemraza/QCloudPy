
import pytest

from qcloudrl.Qnode import (
    QNodeConfig,
    NodeStatus,
    BackendFactory,
)


def test_qnode_config():
    config = QNodeConfig(
        node_id="QNODE_001",
        backend_name="FakeWashington",
        num_qubits=127,
    )

    assert config.node_id == "QNODE_001"
    assert config.num_qubits == 127
    assert config.simulator is True
    assert config.available is True


def test_invalid_node_config():
    with pytest.raises(ValueError):
        QNodeConfig(
            node_id="",
            backend_name="FakeWashington",
            num_qubits=127,
        )


def test_invalid_qubit_capacity():
    with pytest.raises(ValueError):
        QNodeConfig(
            node_id="QNODE_001",
            backend_name="FakeWashington",
            num_qubits=0,
        )


def test_node_status():
    assert NodeStatus.IDLE.value == "idle"
    assert NodeStatus.BUSY.value == "busy"
    assert NodeStatus.OFFLINE.value == "offline"


def test_unknown_backend():
    with pytest.raises(ValueError):
        BackendFactory.create("unknown_backend")
