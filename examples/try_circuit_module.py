import argparse

from qcloudrl.circuits import AerExecutor, CircuitRunner, CircuitService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/mqt_bench")
    parser.add_argument("--manifest", default="data/circuit_manifest.json")
    parser.add_argument("--mode", choices=["cloud", "aer", "both"], default="cloud")
    parser.add_argument("--shots", type=int, default=1024)
    args = parser.parse_args()

    service = CircuitService(
        dataset_root=args.dataset,
        manifest_path=args.manifest,
        cache_size=32,
    )
    service.load_manifest()

    if not service.records:
        raise RuntimeError("Manifest is empty. Run examples/index_dataset.py first.")

    circuit_id = next(iter(service.records))
    aer = AerExecutor() if args.mode in {"aer", "both"} else None
    runner = CircuitRunner(service, aer_executor=aer)
    output = runner.run(circuit_id, mode=args.mode, shots=args.shots)

    if output.cloud_artifact:
        print("Cloud artifact:", output.cloud_artifact.metadata)
    if output.aer_result:
        print("Aer backend:", output.aer_result.backend_name)
        print("Counts:", output.aer_result.counts)
        print("Elapsed seconds:", output.aer_result.elapsed_seconds)
    print("Cache:", service.cache_stats())


if __name__ == "__main__":
    main()
