from __future__ import annotations
from .aer_executor import AerExecutor
from .circuit_service import CircuitService
from .models import CircuitRunOutput
class CircuitRunner:
    """Selects cloud preparation, local Aer execution, or both."""

    VALID_MODES = {"cloud", "aer", "both"}

    def __init__(
        self,
        service: CircuitService,
        aer_executor: AerExecutor | None = None,
    ):
        self.service = service
        self.aer_executor = aer_executor

    def run(
        self,
        circuit_id: str,
        mode: str = "cloud",
        shots: int = 1024,
        auto_measure: bool = True,
    ) -> CircuitRunOutput:
        if mode not in self.VALID_MODES:
            raise ValueError(f"mode must be one of {sorted(self.VALID_MODES)}")

        output = CircuitRunOutput()

        if mode in {"cloud", "both"}:
            output.cloud_artifact = self.service.prepare_for_cloud(circuit_id)

        if mode in {"aer", "both"}:
            if self.aer_executor is None:
                raise RuntimeError(
                    "Aer mode requested but no AerExecutor was provided. "
                    "Install qiskit-aer and pass AerExecutor()."
                )
            circuit = self.service.load(circuit_id)
            output.aer_result = self.aer_executor.run(
                circuit,
                shots=shots,
                auto_measure=auto_measure,
            )
        return output
