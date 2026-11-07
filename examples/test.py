# from qcloudrl.circuits.service import CircuitService
# from qcloudrl.QTask.task_factory import TaskFactory
# from qcloudrl.Qnode.qnode import QNode
# from qcloudrl.Broker.broker import Broker
# from gym_env import (
#     GymEnvConfig,
#     qcloudrl_env_creator,
# )

# config = GymEnvConfig(
#     n_qnodes=4,
#     max_tasks=100,
#     default_execution_time=1.0,
# )
# env = qcloudrl_env_creator({
#     "broker": Broker,
#     "qnodes": QNode,
#     "task_source": TaskFactory,
#     "config": config,
#     "obs_filter": "rescale_-1_1",
#     "reward_filter": "scale",
#     "reward_scale": 2.0,
# })

# observation, info = env.reset(seed=42)

# print("Observation shape:", observation.shape)
# print("Action space:", env.action_space)
# print("Observation space:", env.observation_space)
# print("Configuration:", config)

# print("Gym environment package imports successfully.")


# from pathlib import Path
# import re

# file_path = Path(
#     r"C:\Users\Aleem Raza\Desktop\ML&AI-ENG\QAISim\data\QCloudSimpy_NewCode\dataset\mqt_bench\ae_indep_opt2_10.qasm"
# )

# source = file_path.read_text(encoding="utf-8-sig")

# print("\n========== QUBIT DECLARATION SEARCH ==========")

# found = False

# for line_number, line in enumerate(source.splitlines(), start=1):
#     if re.search(r"\b(qubit|qreg)\b", line, re.IGNORECASE):
#         print(f"{line_number}: {line.strip()}")
#         found = True

# if not found:
#     print("No qubit or qreg declarations found.")

# print("\n========== FILE SUMMARY ==========")
# print("Total lines:", len(source.splitlines()))
# print("File size:", len(source), "characters")

# print("\n========== LAST 40 LINES ==========")
# for line_number, line in enumerate(
#     source.splitlines()[-40:],
#     start=max(1, len(source.splitlines()) - 39)
# ):
#     print(f"{line_number}: {line}")


import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Prioritize the current QCloudPy project.
sys.path.insert(0, str(PROJECT_ROOT))

print("Project root:", PROJECT_ROOT)
from qcloudrl.circuits.registry import (
    CircuitRegistry,
    detect_qasm_format
)

import qcloudrl.circuits.registry as registry_module

print("Imported registry:", registry_module.__file__)
print(
    "Extraction method exists:",
    hasattr(
        registry_module.CircuitRegistry,
        "_extract_qubit_count"
    )
)

file_path = Path(
    r"C:\Users\Aleem Raza\Desktop\ML&AI-ENG\QAISim\data\QCloudSimpy_NewCode\dataset\mqt_bench\ae_indep_opt2_10.qasm"
)

circuit_format = detect_qasm_format(file_path)

num_qubits = CircuitRegistry._extract_qubit_count(
    file_path,
    circuit_format
)

print("\n========== EXTRACTION RESULT ==========")
print("Circuit format:", circuit_format)
print("Number of qubits:", num_qubits)