from pathlib import Path
from typing import Iterable, Optional

from qcloudrl.QTask.QTask import QTask


class TaskFactory:
    """
    Creates QTask objects using records from CircuitService.

    The factory does not parse or load QASM circuits.
    It only uses circuit metadata already available in the registry.
    """

    def __init__(self, circuit_service):
        if circuit_service is None:
            raise ValueError("CircuitService cannot be None.")

        self.circuit_service = circuit_service

    @staticmethod
    def _get_circuit_format(record) -> str:
        """
        Get the QASM format from CircuitRecord.

        CircuitRecord.circuit_format is normally a CircuitFormat Enum.
        """

        circuit_format = getattr(record, "circuit_format", None)

        if circuit_format is None:
            raise ValueError(
                f"Circuit format is missing for "
                f"circuit: {record.circuit_id}"
            )

        # Convert Enum to its string value when necessary.
        circuit_format = getattr(
            circuit_format,
            "value",
            circuit_format,
        )

        circuit_format = str(circuit_format).lower()

        if circuit_format not in {"qasm2", "qasm3"}:
            raise ValueError(
                f"Unsupported circuit format '{circuit_format}' "
                f"for circuit: {record.circuit_id}"
            )

        return circuit_format

    def create_task(
        self,
        record,
        task_id: str,
        shots: int = 1024,
        priority: int = 0,
        arrival_time: float = 0.0,
        deadline: Optional[float] = None,
        required_qubits: Optional[int] = None,
    ) -> QTask:
        """
        Create one QTask from a CircuitRecord.

        Args:
            record: CircuitRecord returned by CircuitService.
            task_id: Unique identifier for the task.
            shots: Number of measurement shots.
            priority: Task scheduling priority.
            arrival_time: Task arrival time in simulation.
            deadline: Optional task deadline.
            required_qubits: Optional minimum qubit requirement.

        Returns:
            A QTask object bound to CircuitService.
        """

        circuit_id = record.circuit_id

        # Get circuit format without loading the circuit.
        circuit_format = self._get_circuit_format(record)

        # Read metadata already available in CircuitRecord.
        record_metadata = getattr(record, "metadata", None) or {}
        # start remove 
        # print("\n========== CIRCUIT RECORD DEBUG ==========")

        # print("Record type:", type(record))
        # print("Record attributes:", vars(record))
        # print("Metadata:", record_metadata)

        # print("Possible qubit attributes:")

        # for name in (
        #     "num_qubits",
        #     "n_qubits",
        #     "qubit_count",
        #     "number_of_qubits",
        # ):
        #     print(f"{name}: {getattr(record, name, None)}")

        # print("==========================================\n")
        
        # end remove 

        if not isinstance(record_metadata, dict):
            record_metadata = {}

        # Use known qubit metadata if available.
        # Do not parse the circuit just to determine its qubit count.
        if required_qubits is None:
            required_qubits = record_metadata.get("num_qubits")

        # Keep a copy of the circuit registry metadata.
        circuit_metadata = {
            "name": getattr(record, "name", None),
            "dataset_name": getattr(record, "dataset_name", None),
            "file_size_bytes": getattr(
                record,
                "file_size_bytes",
                None,
            ),
            "circuit_hash": getattr(
                record,
                "circuit_hash",
                None,
            ),
            "metadata": record_metadata.copy(),
        }

        circuit_ref = str(
            Path(record.file_path)
        )

        # Construct the task.
        task = QTask(
            task_id=task_id,
            circuit_id=circuit_id,
            circuit_ref=circuit_ref,
            circuit_format=circuit_format,
            shots=shots,
            priority=priority,
            arrival_time=arrival_time,
            deadline=deadline,
            required_qubits=required_qubits,
            circuit_metadata=circuit_metadata,
        )

        # Verify the circuit exists in CircuitService's registry.
        # This does not load the QuantumCircuit.
        task.bind_circuit_service(self.circuit_service)

        return task

    def create_tasks(
        self,
        records: Optional[Iterable] = None,
        shots: int = 1024,
        priority: int = 0,
        arrival_interval: float = 0.0,
        first_arrival: float = 0.0,
        task_id_prefix: str = "QTASK",
    ) -> list[QTask]:
        """
        Create multiple tasks from CircuitRecords.

        If records are not provided, all indexed circuit records
        are obtained through CircuitService.list_circuits().

        Task arrival times are generated using arrival_interval.

        Example:
            first_arrival = 0.0
            arrival_interval = 2.0

            Generated arrival times:
            0.0, 2.0, 4.0, 6.0, ...
        """

        if arrival_interval < 0:
            raise ValueError(
                "arrival_interval cannot be negative."
            )

        if first_arrival < 0:
            raise ValueError(
                "first_arrival cannot be negative."
            )

        if not isinstance(task_id_prefix, str) or not task_id_prefix.strip():
            raise ValueError(
                "task_id_prefix must be a non-empty string."
            )

        # Obtain records from CircuitService if not provided.
        if records is None:
            records = self.circuit_service.list_circuits()

        tasks = []

        for index, record in enumerate(records, start=1):

            task_id = f"{task_id_prefix}_{index:06d}"

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