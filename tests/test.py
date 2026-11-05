from qcloudrl.circuits import CircuitService

service = CircuitService(
    dataset_dir="./dataset",
    dataset_name="mqt_bench",
    cache_capacity=32,
)

records = service.index_dataset(
    enrich_metadata=True,
    save_manifest=True,
)

print("Indexed circuits:", len(records))

for record in records[:10]:
    print(
        record.circuit_id,
        record.name,
        record.num_qubits,
        record.required_qubits,
    )