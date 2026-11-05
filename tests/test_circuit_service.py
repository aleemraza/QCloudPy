from pathlib import Path
from qcloudrl.circuits import CircuitService

def main():

    print("=" * 70)
    print("QCloudRL - MQT Bench Circuit Service Integration Test")
    print("=" * 70)

    # -----------------------------------------------------
    # 1. Define dataset and manifest paths
    # -----------------------------------------------------

    dataset_dir = Path("dataset/mqt_bench")

    manifest_path = dataset_dir / "circuit_manifest.json"

    service = CircuitService(
        dataset_dir=str(dataset_dir),
        dataset_name="mqt_bench",
        manifest_path=str(manifest_path),
        cache_capacity=32,
    )

    # -----------------------------------------------------
    # 2. Load or create manifest
    # -----------------------------------------------------

    print("\n[STEP 1] Manifest Management")

    if manifest_path.exists():

        print("Existing manifest found.")

        service.load_manifest()

        print("Manifest loaded successfully.")

    else:

        print("Manifest not found.")
        print("Indexing dataset metadata...")

        service.index_dataset(
            save_manifest=True
        )

        print("Dataset indexed successfully.")
        print("Manifest created successfully.")

    print("Manifest path:", manifest_path.resolve())
    print("Manifest exists:", manifest_path.exists())

    # -----------------------------------------------------
    # 3. Get circuit records from manifest
    # -----------------------------------------------------

    print("\n[STEP 2] Retrieve Circuit Metadata")

    records = service.list_circuits()

    print("Total indexed circuits:", len(records))

    if not records:
        print("No circuits found.")
        return

    # -----------------------------------------------------
    # 4. Dataset format statistics
    # -----------------------------------------------------

    format_counts = {}

    for record in records:

        fmt = record.circuit_format.value

        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    print("\nCircuit formats:")

    for fmt, count in format_counts.items():
        print(f"  {fmt}: {count}")

    # -----------------------------------------------------
    # 5. Verify lazy loading
    # -----------------------------------------------------

    print("\n[STEP 3] Verify Lazy Circuit Loading")

    print("Records available:", len(records))
    print("Parsed circuits in cache:", service.cache.size)

    assert service.cache.size == 0, (
        "Circuits were unexpectedly loaded during indexing "
        "or manifest loading."
    )

    print("Lazy loading verification: PASS")

    # -----------------------------------------------------
    # 6. Load only selected circuits
    # -----------------------------------------------------

    successful = 0
    failed = 0

    test_records = records[:10]

    print("\n" + "=" * 70)
    print("Testing Selected Circuit Loading and Feature Extraction")
    print("=" * 70)

    for index, record in enumerate(test_records, start=1):

        print(f"\n[{index}/{len(test_records)}] {record.name}")

        try:

            # Load one circuit on demand.
            circuit = service.get_circuit(record.circuit_id)

            # Extract logical features.
            features = service.get_features(record.circuit_id)

            print("  Circuit ID:", record.circuit_id)
            print("  Format:", record.circuit_format.value)
            print("  Qubits:", circuit.num_qubits)
            print("  Classical bits:", circuit.num_clbits)
            print("  Depth:", features.circuit_depth)
            print("  Gate count:", features.total_gate_count)
            print("  Gate histogram:", features.gate_histogram)

            successful += 1

        except Exception as exc:

            failed += 1

            print("  ERROR:", str(exc))

    # -----------------------------------------------------
    # 7. Verify LRU cache reuse
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("Testing LRU Circuit Cache")
    print("=" * 70)

    if test_records:

        record = test_records[0]

        first = service.get_circuit(record.circuit_id)

        second = service.get_circuit(record.circuit_id)

        print("Same circuit object:", first is second)
        print("Cache hits:", service.cache.hits)
        print("Cache misses:", service.cache.misses)
        print("Cache size:", service.cache.size)

        assert first is second

    # -----------------------------------------------------
    # 8. Final report
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 70)

    print("Total indexed:", len(records))
    print("Circuits tested:", len(test_records))
    print("Successful:", successful)
    print("Failed:", failed)

    print("\nManifest:", manifest_path.exists())

    print("Parsed circuits in cache:", service.cache.size)

    print("\nService statistics:")

    stats = service.get_statistics()

    for component, values in stats.items():

        print(f"\n{component.upper()}")

        if isinstance(values, dict):

            for key, value in values.items():
                print(f"  {key}: {value}")

    assert failed == 0, "Some circuit tests failed."

    print("\nCIRCUIT SERVICE INTEGRATION TEST: PASS")


if __name__ == "__main__":
    main()