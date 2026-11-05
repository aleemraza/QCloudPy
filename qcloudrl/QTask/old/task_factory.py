
from pathlib import Path

from qcloudrl.QTask.QTask import QTask


class TaskFactory:
    """
    Creates QTask objects from CircuitService registry records.

    Task creation does not load actual quantum circuits.
    """

    def __init__(self, circuit_service):
        self.circuit_service = circuit_service

    def _get_circuit_format(self, record):
        """
        Determine QASM format without loading a Qiskit circuit.
        """

        # Check possible registry metadata fields.
        for attribute in (
            "circuit_format",
            "qasm_format",
            "format",
            "qasm_version",
        ):
            value = getattr(record, attribute, None)

            if value is not None:
                value = str(value).lower().replace(".", "")

                if value in ("2", "qasm2"):
                    return "qasm2"

                if value in ("3", "qasm3"):
                    return "qasm3"

        # Determine format from file extension.
        path = Path(record.path)

        if path.suffix.lower() == ".qasm3":
            return "qasm3"

        if path.suffix.lower() == ".qasm2":
            return "qasm2"

        # For .qasm files, inspect the OpenQASM header.
        with path.open("r", encoding="utf-8") as file:
            header = file.read(1024).lower()

        if "openqasm 3" in header:
            return "qasm3"

        if "openqasm 2" in header:
            return "qasm2"

        raise ValueError(
            f"Cannot determine QASM format: {path}"
        )

    def create_task(
        self,
        record,
        task_id: str,
        shots: int = 1024,
        priority: int = 0,
        arrival_time: float = 0.0,
        deadline=None,
    ) -> QTask:

        circuit_id = record.circuit_id

        circuit_format = self._get_circuit_format(record)

        task = QTask(
            task_id=task_id,
            circuit_id=circuit_id,
            circuit_ref=str(record.path),
            circuit_format=circuit_format,
            shots=shots,
            priority=priority,
            arrival_time=arrival_time,
            deadline=deadline,
            required_qubits=getattr(
                record, "num_qubits", None
            ),
            circuit_metadata={
                "file_size_bytes": getattr(
                    record, "file_size_bytes", None
                ),
                "sha256": getattr(record, "sha256", None),
            },
        )

        # Bind CircuitService without loading the circuit.
        task.bind_circuit_service(self.circuit_service)

        return task

    def create_tasks(
        self,
        records=None,
        shots: int = 1024,
        priority: int = 0,
        arrival_interval: float = 0.0,
        first_arrival: float = 0.0,
        task_id_prefix: str = "QTASK",
    ) -> list[QTask]:

        if arrival_interval < 0:
            raise ValueError(
                "arrival_interval cannot be negative"
            )

        if first_arrival < 0:
            raise ValueError(
                "first_arrival cannot be negative"
            )

        if records is None:
            records = list(
                self.circuit_service.records.values()
            )

        tasks = []

        for index, record in enumerate(records, start=1):

            task_id = f"{task_id_prefix}_{index:05d}"

            arrival_time = (
                first_arrival
                + (index - 1) * arrival_interval
            )

            task = self.create_task(
                record=record,
                task_id=task_id,
                shots=shots,
                priority=priority,
                arrival_time=arrival_time,
            )

            tasks.append(task)

        return tasks
