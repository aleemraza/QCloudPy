
# import pytest

# from qiskit import QuantumCircuit

# from qcloudrl.circuits.models import (
#     CircuitFormat,
#     CircuitRecord,
# )

# from qcloudrl.circuits.loader import (
#     CircuitLoader,
#     CircuitLoadError,
#     UnsupportedCircuitFormatError,
# )


# @pytest.fixture
# def qasm2_file(tmp_path):
#     path = tmp_path / "bell.qasm"

#     path.write_text(
#         'OPENQASM 2.0;\n'
#         'include "qelib1.inc";\n'
#         'qreg q[2];\n'
#         'creg c[2];\n'
#         'h q[0];\n'
#         'cx q[0],q[1];\n'
#         'measure q -> c;\n',
#         encoding="utf-8",
#     )

#     return path


# @pytest.fixture
# def qasm3_file(tmp_path):
#     path = tmp_path / "bell.qasm3"

#     path.write_text(
#         'OPENQASM 3.0;\n'
#         'qubit[2] q;\n'
#         'bit[2] c;\n'
#         'h q[0];\n'
#         'cx q[0], q[1];\n'
#         'c = measure q;\n',
#         encoding="utf-8",
#     )

#     return path


# def test_load_qasm2(qasm2_file):
#     loader = CircuitLoader()

#     circuit = loader.load(qasm2_file)

#     assert isinstance(circuit, QuantumCircuit)
#     assert circuit.num_qubits == 2
#     assert circuit.num_clbits == 2


# def test_load_qasm3(qasm3_file):
#     loader = CircuitLoader()

#     circuit = loader.load(qasm3_file)

#     assert isinstance(circuit, QuantumCircuit)
#     assert circuit.num_qubits == 2


# def test_detect_qasm2_format(qasm2_file):
#     loader = CircuitLoader()

#     assert loader.get_format(qasm2_file) == CircuitFormat.QASM2


# def test_detect_qasm3_format(qasm3_file):
#     loader = CircuitLoader()

#     assert loader.get_format(qasm3_file) == CircuitFormat.QASM3


# def test_load_from_record(qasm2_file):
#     record = CircuitRecord(
#         circuit_id="bell_001",
#         name="bell",
#         file_path=str(qasm2_file),
#         circuit_format=CircuitFormat.QASM2,
#     )

#     loader = CircuitLoader()

#     circuit = loader.load_record(record)

#     assert isinstance(circuit, QuantumCircuit)
#     assert circuit.num_qubits == 2


# def test_circuit_validation(qasm2_file):
#     loader = CircuitLoader()

#     circuit = loader.load(qasm2_file)

#     assert loader.validate(circuit) is True


# def test_missing_file():
#     loader = CircuitLoader()

#     with pytest.raises(FileNotFoundError):
#         loader.load("missing.qasm")


# def test_unknown_format(tmp_path):
#     path = tmp_path / "unknown.qasm"

#     path.write_text(
#         "This is not a valid QASM circuit",
#         encoding="utf-8",
#     )

#     loader = CircuitLoader()

#     with pytest.raises(UnsupportedCircuitFormatError):
#         loader.load(path)


# def test_invalid_qasm2(tmp_path):
#     path = tmp_path / "invalid.qasm"

#     path.write_text(
#         "OPENQASM 2.0;\nthis_is_invalid;\n",
#         encoding="utf-8",
#     )

#     loader = CircuitLoader()

#     with pytest.raises(CircuitLoadError):
#         loader.load(path)


# def test_loader_statistics(qasm2_file):
#     loader = CircuitLoader()

#     loader.load(qasm2_file)

#     assert loader.loaded_count == 1
#     assert loader.failed_count == 0


# def test_reset_statistics(qasm2_file):
#     loader = CircuitLoader()

#     loader.load(qasm2_file)
#     loader.reset_statistics()

#     assert loader.loaded_count == 0
#     assert loader.failed_count == 0


# def test_load_many(qasm2_file):
#     record1 = CircuitRecord(
#         circuit_id="circuit_001",
#         name="bell",
#         file_path=str(qasm2_file),
#         circuit_format=CircuitFormat.QASM2,
#     )

#     record2 = CircuitRecord(
#         circuit_id="circuit_002",
#         name="bell_copy",
#         file_path=str(qasm2_file),
#         circuit_format=CircuitFormat.QASM2,
#     )

#     loader = CircuitLoader()

#     circuits = loader.load_many([record1, record2])

#     assert len(circuits) == 2
#     assert "circuit_001" in circuits
#     assert "circuit_002" in circuits


# def test_load_many_skip_errors(qasm2_file):
#     valid_record = CircuitRecord(
#         circuit_id="valid_001",
#         name="bell",
#         file_path=str(qasm2_file),
#         circuit_format=CircuitFormat.QASM2,
#     )

#     invalid_record = CircuitRecord(
#         circuit_id="invalid_001",
#         name="missing",
#         file_path="missing.qasm",
#         circuit_format=CircuitFormat.QASM2,
#     )

#     loader = CircuitLoader()

#     circuits = loader.load_many(
#         [valid_record, invalid_record],
#         skip_errors=True,
#     )

#     assert len(circuits) == 1
#     assert "valid_001" in circuits



from qcloudrl.circuits.registry import CircuitRegistry
from qcloudrl.circuits.loader import CircuitLoader

registry = CircuitRegistry(
    dataset_dir="dataset/mqt_bench"
)

records = registry.index_dataset(limit=10, seed=42)

loader = CircuitLoader()

for record in records:
    try:
        circuit = loader.load_record(record)

        print(
            record.name,
            "Qubits:", circuit.num_qubits,
            "Depth:", circuit.depth(),
            "Gates:", circuit.size(),
        )

    except Exception as error:
        print("Failed:", record.name, error)

print("Successfully loaded:", loader.loaded_count)
print("Failed:", loader.failed_count)