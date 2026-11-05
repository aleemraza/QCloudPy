class BackendFactory:
    """
    Creates IBM Fake Backend instances.

    Supports Qiskit IBM Runtime and older Qiskit
    Fake Provider package locations.
    """

    BACKENDS = {
        "manila": ("FakeManilaV2", "FakeManila"),
        "washington": ("FakeWashingtonV2", "FakeWashington"),
        "kolkata": ("FakeKolkataV2", "FakeKolkata"),
        "hanoi": ("FakeHanoiV2", "FakeHanoi"),
        "guadalupe": ("FakeGuadalupeV2", "FakeGuadalupe"),
    }

    @classmethod
    def create(cls, backend_name: str):
        if not isinstance(backend_name, str) or not backend_name.strip():
            raise ValueError("backend_name must be a non-empty string.")

        name = backend_name.strip().lower()

        if name not in cls.BACKENDS:
            raise ValueError(
                f"Unsupported Fake Backend: {backend_name}. "
                f"Available choices: {list(cls.BACKENDS)}"
            )

        class_names = cls.BACKENDS[name]

        providers = []

        # Newer IBM Runtime package
        try:
            import qiskit_ibm_runtime.fake_provider as provider
            providers.append(provider)
        except ImportError:
            pass

        # Older Qiskit Fake Provider package
        try:
            import qiskit.providers.fake_provider as provider
            providers.append(provider)
        except ImportError:
            pass

        for provider in providers:
            for class_name in class_names:
                backend_class = getattr(provider, class_name, None)

                if backend_class is not None:
                    return backend_class()

        raise ImportError(
            f"Cannot find Fake Backend '{backend_name}'. "
            "Check your Qiskit installation and available "
            "Fake Backend classes."
        )

    @classmethod
    def available_backends(cls):
        """Return the supported backend names."""

        return list(cls.BACKENDS.keys())