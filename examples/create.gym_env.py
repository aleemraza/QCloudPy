# from qcloudrl.circuits.circuit_service import CircuitService
from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker import Broker
from gym_env.config import GymEnvConfig
from gym_env.env_creator import qcloudrl_env_creator



def main():

    # =====================================
    # 1. Circuit dataset
    # =====================================

    service = CircuitService(
        dataset_root="dataset/mqt_bench",
        manifest_path="data/circuit_manifest.json",
        cache_size=32,
    )

    records = service.index(
        limit=500,
        seed=42,
    )

    print("Indexed circuits:", len(records))

    # =====================================
    # 2. QTask factory
    # =====================================

    factory = TaskFactory(service)

    def task_source():

        return factory.create_tasks(
            records=records,
            shots=1024,
            priority=0,
            arrival_interval=0.1,
            first_arrival=0.0,
            task_id_prefix="MQT500",
        )

    # =====================================
    # 3. QNodes
    # =====================================

    qnodes = [

        QNode(
            node_id="QNODE_001",
            backend_name="washington",
            circuit_service=service,
        ),

        QNode(
            node_id="QNODE_002",
            backend_name="kolkata",
            circuit_service=service,
        ),

        QNode(
            node_id="QNODE_003",
            backend_name="hanoi",
            circuit_service=service,
        ),

        QNode(
            node_id="QNODE_004",
            backend_name="guadalupe",
            circuit_service=service,
        ),
    ]

    # =====================================
    # 4. Broker
    # =====================================

    broker = Broker()

    # =====================================
    # 5. Gym configuration
    # =====================================

    config = GymEnvConfig(

        n_qnodes=4,
        max_tasks=500,

        rescheduling_time=0.01,

        default_execution_time=1.0,

        reward_mode="inverse_time",

        max_episode_steps=600,
    )

    # =====================================
    # 6. Environment creator
    # =====================================

    env = qcloudrl_env_creator({

        "broker": broker,

        "qnodes": qnodes,

        "task_source": task_source,

        "config": config,

        "obs_filter": "rescale_-1_1",

        "reward_filter": "scale",

        "reward_scale": 2.0,
    })

    # =====================================
    # 7. Reset
    # =====================================

    observation, info = env.reset(seed=42)

    print("\nObservation dimension:")
    print(observation.shape)

    print("\nInitial information:")
    print(info)

    # =====================================
    # 8. Random feasible policy
    # =====================================

    base_env = env.unwrapped

    terminated = False
    truncated = False

    total_reward = 0.0

    while not (terminated or truncated):

        task = base_env.current_qtask

        feasible_nodes = [

            index

            for index, node in enumerate(
                base_env.qnodes
            )

            if base_env.broker.constraints.check(
                task,
                node,
                check_availability=False,
            )[0]
        ]

        if not feasible_nodes:

            print(
                "No compatible QNode for:",
                task.task_id,
            )

            break

        action = int(
            env.np_random.choice(feasible_nodes)
        )

        (
            observation,
            reward,
            terminated,
            truncated,
            info,
        ) = env.step(action)

        total_reward += reward

        print(
            f"Step={base_env.episode_steps} | "
            f"Task={info.get('task_id', 'N/A')} | "
            f"Node={info.get('node_id', 'N/A')} | "
            f"Reward={reward:.4f} | "
            f"SimTime={base_env.sim_env.now:.3f}"
        )

    # =====================================
    # 9. Final results
    # =====================================

    print("\n========== SIMULATION RESULTS ==========")

    print("Total reward:", total_reward)

    print(
        "Simulation makespan:",
        base_env.sim_env.now,
    )

    print("Broker statistics:")
    print(broker.get_stats())

    print("Performance summary:")
    print(base_env.collect_results())

    print("Circuit cache:")
    print(service.cache_stats())

    env.close()


if __name__ == "__main__":
    main()