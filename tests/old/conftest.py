import pytest


@pytest.fixture
def qasm_dataset(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()

    qasm2 = root / "bell.qasm"
    qasm2.write_text(
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        'qreg q[2];\n'
        'creg c[2];\n'
        'h q[0];\n'
        'cx q[0],q[1];\n'
        'measure q[0] -> c[0];\n'
        'measure q[1] -> c[1];\n',
        encoding="utf-8",
    )

    qasm3 = root / "ghz.qasm3"
    qasm3.write_text(
        'OPENQASM 3.0;\n'
        'include "stdgates.inc";\n'
        'qubit[3] q;\n'
        'bit[3] c;\n'
        'h q[0];\n'
        'cx q[0], q[1];\n'
        'cx q[1], q[2];\n'
        'c[0] = measure q[0];\n'
        'c[1] = measure q[1];\n'
        'c[2] = measure q[2];\n',
        encoding="utf-8",
    )
    return root
