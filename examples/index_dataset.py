import argparse
from qcloudrl.circuits import CircuitService

def main():
    parser = argparse.ArgumentParser(description="Index OpenQASM circuits lazily.")
    parser.add_argument("--dataset", default="dataset/mqt_bench")
    parser.add_argument("--manifest", default="data/circuit_manifest.json")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hash", action="store_true")
    args = parser.parse_args()

    service = CircuitService(
        dataset_root=args.dataset,
        manifest_path=args.manifest,
        cache_size=32,
    )
    records = service.index(
        limit=args.limit,
        seed=args.seed,
        include_hash=args.hash,
    )

    print(f"Indexed {len(records)} circuit files.")
    print(f"Manifest: {args.manifest}")
    print("No circuits were parsed during indexing.")
    for record in records[:5]:
        print(record)


if __name__ == "__main__":
    main()
