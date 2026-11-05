
import pytest

from qcloudrl.QTask import QTask, TaskStatus, TaskFactory


# A small fake circuit record for testing.
class FakeCircuitRecord:
    def __init__(self, circuit_id, path):
        self.circuit_id = circuit_id
        self.path = path
        self.circuit_format = "qasm2"
        self.num_qubits = 3
        self.file_size_bytes = 1200
        self.sha256 = "example_hash"


# A fake CircuitService.
class FakeCircuitService:

    def __init__(self, records):
        self.records = {
            record.circuit_id: record
            for record in records
        }

        self.load_calls = 0

    def get_record(self, circuit_id):
        return self.records.get(circuit_id)

    def load(self, circuit_id):
        self.load_calls += 1

        if circuit_id not in self.records:
            raise ValueError("Circuit not found")

        # A simple placeholder representing a loaded circuit.
        return {"loaded_circuit_id": circuit_id}


@pytest.fixture
def circuit_service():
    records = [
        FakeCircuitRecord(
            "circuit_001",
            "dataset/example_001.qasm",
        ),
        FakeCircuitRecord(
            "circuit_002",
            "dataset/example_002.qasm",
        ),
        FakeCircuitRecord(
            "circuit_003",
            "dataset/example_003.qasm",
        ),
    ]

    return FakeCircuitService(records)


def test_task_factory_creates_tasks_without_loading(
    circuit_service,
):
    factory = TaskFactory(circuit_service)

    tasks = factory.create_tasks()

    assert len(tasks) == 3

    # No circuit should have been loaded.
    assert circuit_service.load_calls == 0

    assert all(
        task.circuit_loaded is False
        for task in tasks
    )


def test_lazy_circuit_loading(circuit_service):
    factory = TaskFactory(circuit_service)

    task = factory.create_tasks()[0]

    assert task.circuit_loaded is False

    circuit = task.get_circuit()

    assert circuit["loaded_circuit_id"] == "circuit_001"
    assert task.circuit_loaded is True

    # The same task should reuse its loaded circuit.
    second_circuit = task.get_circuit()

    assert second_circuit is circuit
    assert circuit_service.load_calls == 1


def test_task_lifecycle(circuit_service):
    factory = TaskFactory(circuit_service)
    task = factory.create_tasks()[0]

    assert task.status == TaskStatus.CREATED

    task.mark_queued()
    assert task.status == TaskStatus.QUEUED

    task.mark_scheduled("QNODE_001")
    assert task.status == TaskStatus.SCHEDULED

    task.mark_running(start_time=10.0)
    assert task.status == TaskStatus.RUNNING

    task.mark_completed(
        result={"00": 500, "11": 524},
        completion_time=15.0,
    )

    assert task.status == TaskStatus.COMPLETED
    assert task.assigned_node_id == "QNODE_001"
    assert task.started_at == 10.0
    assert task.completed_at == 15.0


def test_invalid_lifecycle_transition(circuit_service):
    task = TaskFactory(circuit_service).create_tasks()[0]

    # CREATED cannot directly transition to RUNNING.
    with pytest.raises(ValueError):
        task.mark_running()


def test_task_serialization_excludes_circuit(
    circuit_service,
):
    task = TaskFactory(circuit_service).create_tasks()[0]

    task.get_circuit()

    data = task.to_dict()

    assert "task_id" in data
    assert "circuit_id" in data
    assert "_loaded_circuit" not in data
    assert "_circuit_service" not in data


def test_invalid_shots(circuit_service):
    record = circuit_service.get_record("circuit_001")

    with pytest.raises(ValueError):
        QTask(
            task_id="QTASK_BAD",
            circuit_id=record.circuit_id,
            circuit_ref=str(record.path),
            circuit_format="qasm2",
            shots=0,
        )


def test_invalid_deadline(circuit_service):
    record = circuit_service.get_record("circuit_001")

    with pytest.raises(ValueError):
        QTask(
            task_id="QTASK_BAD",
            circuit_id=record.circuit_id,
            circuit_ref=str(record.path),
            circuit_format="qasm2",
            arrival_time=10.0,
            deadline=5.0,
        )
