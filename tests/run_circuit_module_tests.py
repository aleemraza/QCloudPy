
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from qiskit import QuantumCircuit

from qcloudrl.circuits import CircuitService
from qcloudrl.circuits.models import (
    CircuitFormat,
    CircuitRecord,
    CircuitFeatures,
    CircuitProfile,
)
from qcloudrl.circuits.profiler import (
    CircuitProfiler,
    CircuitProfilingError,
)


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_DIR = PROJECT_ROOT / "dataset" / "mqt_bench"

REPORT_DIR = PROJECT_ROOT / "reports" / "circuit_module"

CACHE_CAPACITY = 32

# Only one real MQT Bench circuit is loaded.
MAX_SAMPLE_CIRCUITS = 1

REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# REPORT DATA
# ============================================================

report = {
    "project": "QCloudRL",
    "module": "Circuit Module",
    "dataset": "MQT Bench",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "configuration": {
        "cache_capacity": CACHE_CAPACITY,
        "max_sample_circuits": MAX_SAMPLE_CIRCUITS,
        "backend_execution": False,
        "quantum_job_submission": False,
    },
    "components": {},
    "details": {},
    "errors": [],
}

log_messages = []


def log(message):
    print(message)
    log_messages.append(str(message))


def record_result(component, status, details=None, error=None):
    report["components"][component] = {
        "status": status,
        "details": details or {},
    }

    if error:
        report["components"][component]["error"] = str(error)
        report["errors"].append({
            "component": component,
            "error": str(error),
        })


# ============================================================
# TEST 1: DATA MODELS
# ============================================================

def test_models():

    log("\n[TEST 1] Circuit Data Models")

    CircuitFormat.QASM2
    CircuitFormat.QASM3

    record = CircuitRecord(
        circuit_id="model_test",
        name="test_circuit",
        file_path="dataset/test.qasm",
        circuit_format=CircuitFormat.QASM3,
    )

    assert record.circuit_id == "model_test"

    features = CircuitFeatures(
        circuit_id="model_test",
        num_qubits=4,
        circuit_depth=10,
        total_gate_count=20,
    )

    assert features.num_qubits == 4
    assert features.circuit_depth == 10

    profile = CircuitProfile(
        circuit_id="model_test",
        original_depth=10,
        original_gate_count=20,
        backend_name="test_backend",
        transpiled_depth=15,
        transpiled_gate_count=25,
    )

    assert profile.transpiled_depth == 15

    # Validate model constraints.
    try:
        CircuitFeatures(
            circuit_id="invalid",
            num_qubits=-1,
        )
        raise AssertionError("Negative qubit count was accepted.")
    except ValueError:
        pass

    record_result(
        "Models",
        "PASS",
        {
            "format_models": "PASS",
            "record_model": "PASS",
            "features_model": "PASS",
            "profile_model": "PASS",
            "validation": "PASS",
        },
    )

    log("Models: PASS")


# ============================================================
# TEST 2: INITIALIZE CIRCUIT SERVICE AND REGISTRY
# ============================================================

def initialize_service():

    log("\n[TEST 2] Circuit Registry and Service")

    service = CircuitService(
        dataset_dir=str(DATASET_DIR),
        dataset_name="mqt_bench",
        cache_capacity=CACHE_CAPACITY,
    )

    if service.manifest_path.exists():
        service.load_manifest()
        log("Existing manifest loaded.")
    else:
        service.index_dataset()
        log("Dataset indexed.")

    records = service.list_circuits()

    if not records:
        raise RuntimeError("Registry contains no circuit records.")

    format_counts = {}

    for item in records:
        fmt = item.circuit_format.value
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    record_result(
        "Registry",
        "PASS",
        {
            "indexed_circuits": len(records),
            "format_counts": format_counts,
            "manifest": str(service.manifest_path),
        },
    )

    log(f"Registry: PASS ({len(records)} circuits indexed)")

    return service, records


# ============================================================
# TEST 3: CIRCUIT LOADER
# ============================================================

def test_loader(service, records):

    log("\n[TEST 3] QASM Circuit Loader")

    selected_records = records[:MAX_SAMPLE_CIRCUITS]

    loaded = []

    for item in selected_records:

        circuit = service.get_circuit(item.circuit_id)

        assert isinstance(circuit, QuantumCircuit)

        loaded.append({
            "record": item,
            "circuit": circuit,
        })

        log(
            f"Loaded {item.name}: "
            f"{circuit.num_qubits} qubits"
        )

    if not loaded:
        raise RuntimeError("No circuits were loaded.")

    record_result(
        "Loader",
        "PASS",
        {
            "circuits_loaded": len(loaded),
            "sample_circuits": [
                {
                    "circuit_id": item["record"].circuit_id,
                    "name": item["record"].name,
                    "num_qubits": item["circuit"].num_qubits,
                    "num_clbits": item["circuit"].num_clbits,
                }
                for item in loaded
            ],
        },
    )

    log("Loader: PASS")

    return loaded


# ============================================================
# TEST 4: FEATURE EXTRACTOR
# ============================================================

def test_feature_extractor(service, loaded):

    log("\n[TEST 4] Logical Feature Extractor")

    feature_results = []

    for item in loaded:

        record = item["record"]

        features = service.get_features(record.circuit_id)

        assert features.num_qubits > 0
        assert features.circuit_depth >= 0
        assert features.total_gate_count >= 0

        feature_results.append({
            "circuit_id": record.circuit_id,
            "num_qubits": features.num_qubits,
            "depth": features.circuit_depth,
            "gate_count": features.total_gate_count,
            "gate_histogram": features.gate_histogram,
        })

    record_result(
        "FeatureExtractor",
        "PASS",
        {
            "circuits_analyzed": len(feature_results),
            "features": feature_results,
            "transpilation_performed": False,
        },
    )

    log("Feature Extractor: PASS")


# ============================================================
# TEST 5: LRU CIRCUIT CACHE
# ============================================================

def test_cache(service, loaded):

    log("\n[TEST 5] LRU Circuit Cache")

    record = loaded[0]["record"]

    cache = service.cache

    hits_before = cache.hits
    misses_before = cache.misses

    first = service.get_circuit(record.circuit_id)
    second = service.get_circuit(record.circuit_id)

    assert first is second

    hits_after = cache.hits
    misses_after = cache.misses

    assert hits_after > hits_before

    cache_details = {
        "same_object_reused": first is second,
        "hits_before": hits_before,
        "hits_after": hits_after,
        "misses_before": misses_before,
        "misses_after": misses_after,
        "capacity": CACHE_CAPACITY,
        "current_size": cache.size,
        "evictions": cache.evictions,
    }

    record_result(
        "CircuitCache",
        "PASS",
        cache_details,
    )

    log("Cache: PASS")
    log(f"Cache hits: {cache.hits}")
    log(f"Cache misses: {cache.misses}")
    log(f"Same object reused: {first is second}")


# ============================================================
# TEST 6: INDEPENDENT BACKEND PROFILER
# ============================================================

def test_profiler():

    log("\n[TEST 6] Independent Circuit Profiler")

    try:
        from qiskit.providers.fake_provider import GenericBackendV2

    except ImportError as exc:
        raise RuntimeError(
            "GenericBackendV2 is unavailable in this Qiskit version."
        ) from exc

    # Local simulated backend.
    # No IBM Quantum connection or QPU execution.

    backend = GenericBackendV2(
        num_qubits=3,
        basis_gates=[
            "id",
            "rz",
            "sx",
            "x",
            "cx",
            "reset",
        ],
        coupling_map=[
            [0, 1],
            [1, 2],
        ],
    )

    # Small Bell-state circuit.
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.cx(0, 1)

    circuit.measure([0, 1], [0, 1])

    original = circuit.copy()

    profiler = CircuitProfiler(
        optimization_level=1,
        seed_transpiler=42,
    )

    profile = profiler.profile(
        circuit=circuit,
        circuit_id="profiler_bell_test",
        backend=backend,
    )

    # Validate returned profile.
    assert profile.circuit_id == "profiler_bell_test"

    assert profile.original_depth == original.depth()

    assert profile.original_gate_count == 2

    assert profile.transpiled_depth >= 0

    assert profile.transpiled_gate_count >= 0

    assert profile.backend_name == str(backend.name)

    assert profile.optimization_level == 1

    assert profile.is_compatible is True

    assert any(
        "Transpilation succeeded" in note
        for note in profile.compatibility_notes
    )

    assert profile.metadata["profiler"] == "CircuitProfiler"

    assert (
        profile.metadata["profiler_version"] == 1
    )

    assert circuit == original

    details = {
        "backend_name": profile.backend_name,
        "optimization_level": profile.optimization_level,
        "original_depth": profile.original_depth,
        "original_gate_count": profile.original_gate_count,
        "transpiled_depth": profile.transpiled_depth,
        "transpiled_gate_count": profile.transpiled_gate_count,
        "basis_gates": profile.basis_gates,
        "is_compatible": profile.is_compatible,
        "compatibility_notes": profile.compatibility_notes,
        "profiled_at": str(profile.profiled_at),
        "profiler_metadata": profile.metadata,
        "quantum_execution": False,
    }

    record_result(
        "Profiler",
        "PASS",
        details,
    )

    log("Profiler: PASS")
    log(f"Backend: {profile.backend_name}")
    log(f"Original depth: {profile.original_depth}")
    log(f"Transpiled depth: {profile.transpiled_depth}")
    log(f"Transpiled gates: {profile.transpiled_gate_count}")


# ============================================================
# TEST 7: CIRCUIT SERVICE STATISTICS
# ============================================================

def test_service_statistics(service):

    log("\n[TEST 7] Circuit Service Statistics")

    stats = service.get_statistics()

    assert isinstance(stats, dict)

    record_result(
        "CircuitService",
        "PASS",
        {
            "statistics": stats,
            "service_initialized": True,
        },
    )

    log("CircuitService: PASS")


# ============================================================
# JSON REPORT GENERATION
# ============================================================

def generate_reports():

    statuses = [
        item["status"]
        for item in report["components"].values()
    ]

    total = len(statuses)
    passed = statuses.count("PASS")
    failed = statuses.count("FAIL")
    not_tested = statuses.count("NOT_TESTED")

    overall_status = (
        "PASS"
        if total > 0 and passed == total
        else "FAIL"
    )

    report["summary"] = {
        "overall_status": overall_status,
        "total_components": total,
        "passed": passed,
        "failed": failed,
        "not_tested": not_tested,
    }

    summary = {
        "project": report["project"],
        "module": report["module"],
        "dataset": report["dataset"],
        "timestamp": report["timestamp"],
        "overall_status": overall_status,
        "indexed_circuits": report["components"].get(
            "Registry", {}
        ).get("details", {}).get("indexed_circuits", 0),
        "components": report["components"],
        "summary": report["summary"],
    }

    summary_path = REPORT_DIR / "circuit_module_summary.json"

    report_path = REPORT_DIR / "circuit_module_test_report.json"

    log_path = REPORT_DIR / "circuit_module_test.log"

    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=4, default=str)

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, default=str)

    with open(log_path, "w", encoding="utf-8") as file:
        file.write("\n".join(log_messages))

    log("\nReports generated:")
    log(str(summary_path))
    log(str(report_path))
    log(str(log_path))


# ============================================================
# MAIN TEST RUNNER
# ============================================================

def main():

    log("=" * 65)
    log("QCloudRL - COMPLETE CIRCUIT MODULE VALIDATION")
    log("=" * 65)

    service = None
    records = None
    loaded = None

    tests = [
        ("Models", test_models),
    ]

    for name, function in tests:

        try:
            function()

        except Exception as exc:
            record_result(name, "FAIL", error=exc)
            log(f"{name}: FAIL - {exc}")

    try:
        service, records = initialize_service()

    except Exception as exc:
        record_result("Registry", "FAIL", error=exc)
        log(f"Registry: FAIL - {exc}")

    if service is not None and records:

        try:
            loaded = test_loader(service, records)

        except Exception as exc:
            record_result("Loader", "FAIL", error=exc)
            log(f"Loader: FAIL - {exc}")

        if loaded:

            try:
                test_feature_extractor(service, loaded)

            except Exception as exc:
                record_result(
                    "FeatureExtractor", "FAIL", error=exc
                )
                log(f"Feature Extractor: FAIL - {exc}")

            try:
                test_cache(service, loaded)

            except Exception as exc:
                record_result(
                    "CircuitCache", "FAIL", error=exc
                )
                log(f"Cache: FAIL - {exc}")

        try:
            test_service_statistics(service)

        except Exception as exc:
            record_result(
                "CircuitService", "FAIL", error=exc
            )
            log(f"CircuitService: FAIL - {exc}")

    # Profiler is independent of MQT Bench loading.
    try:
        test_profiler()

    except Exception as exc:
        record_result("Profiler", "FAIL", error=exc)
        log(f"Profiler: FAIL - {exc}")

        log(traceback.format_exc())

    # Components that could not run are explicitly identified.
    expected_components = [
        "Models",
        "Registry",
        "Loader",
        "FeatureExtractor",
        "CircuitCache",
        "Profiler",
        "CircuitService",
    ]

    for component in expected_components:

        if component not in report["components"]:

            record_result(
                component,
                "NOT_TESTED",
                {"reason": "Required earlier component failed."},
            )

    log("\n" + "=" * 65)
    log("FINAL CIRCUIT MODULE TEST SUMMARY")
    log("=" * 65)

    for name, result in report["components"].items():
        log(f"{name}: {result['status']}")

    generate_reports()

    log("\nCircuit Module validation completed.")


if __name__ == "__main__":
    main()
