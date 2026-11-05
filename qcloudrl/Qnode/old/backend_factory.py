
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
        name = backend_name.lower()

        if name not in cls.BACKENDS:
            raise ValueError(
                f"Unsupported Fake Backend: {backend_name}. "
                f"Available choices: {list(cls.BACKENDS)}"
            )

        class_names = cls.BACKENDS[name]

        # Newer IBM Runtime package.
        try:
            import qiskit_ibm_runtime.fake_provider as provider

            for class_name in class_names:
                backend_class = getattr(
                    provider, class_name, None
                )

                if backend_class is not None:
                    return backend_class()

        except ImportError:
            pass

        # Older Qiskit Fake Provider package.
        try:
            import qiskit.providers.fake_provider as provider

            for class_name in class_names:
                backend_class = getattr(
                    provider, class_name, None
                )

                if backend_class is not None:
                    return backend_class()

        except ImportError:
            pass

        raise ImportError(
            f"Cannot find Fake Backend '{backend_name}'. "
            "Check your qiskit-ibm-runtime or Qiskit "
            "Fake Provider installation and available "
            "backend classes."
        )
