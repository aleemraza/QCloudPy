
import pytest
import simpy

from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker


@pytest.fixture(scope="session")
def circuit_service():
    service = CircuitService(
        dataset_dir="dataset/mqt_bench",
        dataset_name="mqt_bench",
        cache_capacity=32,
    )
    service.load_manifest()
    return service


@pytest.fixture(scope="session")
def task_factory(circuit_service):
    return TaskFactory(circuit_service)


@pytest.fixture
def make_tasks(task_factory, circuit_service):
    """Create tasks without loading every circuit."""

    def _make_tasks(
        count=3,
        arrival_interval=0.0,
        first_arrival=0.0,
    ):
        records = circuit_service.list_circuits()

        if count > len(records):
            raise ValueError("Requested more tasks than available circuits.")

        return task_factory.create_tasks(
            records=records[:count],
            shots=1024,
            priority=1,
            arrival_interval=arrival_interval,
            first_arrival=first_arrival,
        )

    return _make_tasks


@pytest.fixture
def make_node(circuit_service):
    """Create a QNode backed by a local Fake Backend configuration."""

    def _make_node(node_id, backend_name="washington"):
        return QNode(
            node_id=node_id,
            backend_name=backend_name,
            circuit_service=circuit_service,
        )

    return _make_node


@pytest.fixture
def make_broker():
    """Create a Broker with its own SimPy environment."""

    def _make_broker(nodes=None):
        sim_env = simpy.Environment()
        broker = Broker()
        broker.attach_simpy(sim_env)

        if nodes:
            broker.register_nodes(nodes)

        return sim_env, broker

    return _make_broker
