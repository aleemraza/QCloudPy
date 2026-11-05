from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker
from gym_env.env_creator import qcloudrl_env_creator
from gym_env.config import GymEnvConfig


# =====================================================
# 1. EXPERIMENT CONFIGURATION
# =====================================================
NUM_TASKS = 40
NUM_NODES = 4
SHOTS = 1024
EXECUTION_TIME = 2.0
# Tasks arrive faster than the execution duration.
# This helps us observe whether queues develop.
ARRIVAL_INTERVAL = 0.5


# =====================================================
# 2. INITIALIZE CIRCUIT DATASET
# =====================================================

circuit_service = CircuitService(
    dataset_dir="dataset/mqt_bench",
    dataset_name="mqt_bench",
    cache_capacity=32,
)

circuit_service.load_manifest()

records = circuit_service.list_circuits()

print("Loaded circuit records:", len(records))

if len(records) < NUM_TASKS:
    raise RuntimeError(
        f"Need {NUM_TASKS} circuits, but only "
        f"{len(records)} records are available."
    )

task_factory = TaskFactory(circuit_service)


# =====================================================
# 3. CREATE FOUR QNODES
# =====================================================

def create_qnodes():

    return [
        QNode(
            node_id="node_0",
            backend_name="washington",
            circuit_service=circuit_service,
        ),
        QNode(
            node_id="node_1",
            backend_name="kolkata",
            circuit_service=circuit_service,
        ),
        QNode(
            node_id="node_2",
            backend_name="hanoi",
            circuit_service=circuit_service,
        ),
        QNode(
            node_id="node_3",
            backend_name="guadalupe",
            circuit_service=circuit_service,
        ),
    ]


qnodes = create_qnodes()


# =====================================================
# 4. CREATE BROKER
# =====================================================

broker = Broker()


# =====================================================
# 5. TASK SOURCE
# =====================================================

def task_source():

    return task_factory.create_tasks(
        records=records[:NUM_TASKS],
        shots=SHOTS,
        priority=0,
        arrival_interval=ARRIVAL_INTERVAL,
        first_arrival=0.0,
    )


# =====================================================
# 6. GYMNASIUM CONFIGURATION
# =====================================================

gym_config = GymEnvConfig(
    n_qnodes=NUM_NODES,
    max_tasks=100,

    default_execution_time=EXECUTION_TIME,
    rescheduling_time=0.01,
    max_rescheduling_count=10,
    max_episode_steps=1000,

    reward_mode="inverse_time",
    invalid_action_penalty=-0.1,
)


# =====================================================
# 7. CREATE GYMNASIUM ENVIRONMENT
# =====================================================

env = qcloudrl_env_creator(
    {
        "broker": broker,
        "qnodes": qnodes,
        "task_source": task_source,
        "config": gym_config,
        "obs_filter": None,
        "reward_filter": None,
    }
)


# =====================================================
# 8. QUEUE MONITORING FUNCTIONS
# =====================================================

peak_waiting_queue = {
    node.node_id: 0
    for node in qnodes
}


def print_queue_state(core_env, decision):

    current_broker = core_env.broker

    print(
        f"\n--- Queue state after decision {decision} "
        f"(time={current_broker.get_current_time():.2f}) ---"
    )

    for node_id, resource in current_broker.node_resources.items():

        running = resource.count
        waiting = len(resource.queue)

        peak_waiting_queue[node_id] = max(
            peak_waiting_queue[node_id],
            waiting,
        )

        print(
            f"{node_id}: "
            f"Running={running} | "
            f"SimPy waiting={waiting} | "
            f"Peak waiting={peak_waiting_queue[node_id]}"
        )

    print(
        f"Broker pending={len(current_broker.pending_tasks)} | "
        f"Assigned={len(current_broker.assigned_tasks)} | "
        f"Completed={len(current_broker.completed_tasks)} | "
        f"Failed={len(current_broker.failed_tasks)}"
    )


# =====================================================
# 9. RESET ENVIRONMENT
# =====================================================

observation, info = env.reset(seed=42)

core_env = env.unwrapped

print("\n========== ENVIRONMENT INITIALIZED ==========")

print("Observation shape:", observation.shape)
print("Action space:", env.action_space)

print("Total tasks:", info["total_tasks"])
print("Ready tasks:", info["ready_tasks"])
print("Future tasks:", info["future_tasks"])

print("Initially valid actions:", int(info["action_mask"].sum()))

print("\nRegistered QNodes:")

for node in core_env.qnodes:
    print(
        node.node_id,
        node.backend_name,
    )


# =====================================================
# 10. RUN ONE GYMNASIUM EPISODE
# =====================================================

terminated = False
truncated = False

decision_count = 0

while not (terminated or truncated):

    core_env = env.unwrapped

    action_mask = core_env.get_action_mask()

    valid_actions = [
        action
        for action, valid in enumerate(action_mask)
        if valid == 1
    ]

    # No valid actions.
    if not valid_actions:

        if (
            not core_env.broker.pending_tasks
            and not core_env.broker.future_tasks
        ):
            break

        raise RuntimeError(
            "No valid actions available while tasks remain. "
            "Inspect task feasibility and arrival handling."
        )

    # Select a random valid task-node action.
    action = int(
        core_env.np_random.choice(valid_actions)
    )

    task_index, node_index = core_env.decode_action(action)

    task = core_env.qtasks[task_index]
    node = core_env.qnodes[node_index]

    # Execute scheduling decision.
    observation, reward, terminated, truncated, info = env.step(
        action
    )

    decision_count += 1

    print(
        f"\nDecision {decision_count:03d} | "
        f"Time={info['simulation_time']:.2f} | "
        f"Task={task.task_id} | "
        f"Node={node.node_id} ({node.backend_name}) | "
        f"Reward={reward:.5f} | "
        f"Ready={info['ready_tasks']} | "
        f"Completed={info['completed_tasks']}"
    )

    # Inspect actual SimPy queues after every decision.
    print_queue_state(
        core_env,
        decision_count,
    )


# =====================================================
# 11. COLLECT EPISODE RESULTS
# =====================================================

summary = env.unwrapped.collect_results()

print("\n========== EPISODE SUMMARY ==========")

for key, value in summary.items():
    print(f"{key}: {value}")


# =====================================================
# 12. BROKER STATISTICS
# =====================================================

print("\n========== BROKER STATISTICS ==========")

broker_stats = core_env.broker.get_stats()

for key, value in broker_stats.items():
    print(f"{key}: {value}")


# =====================================================
# 13. PER-NODE EXECUTION ANALYSIS
# =====================================================

print("\n========== PER-NODE QUEUE ANALYSIS ==========")

all_records = core_env.broker.get_execution_records()

for node in core_env.qnodes:

    node_records = [
        record
        for record in all_records
        if record.node_id == node.node_id
    ]

    waits = [
        float(record.waiting_time)
        for record in node_records
        if record.waiting_time is not None
    ]

    average_wait = (
        sum(waits) / len(waits)
        if waits else 0.0
    )

    print(f"\nNode: {node.node_id} ({node.backend_name})")
    print("Assigned/completed records:", len(node_records))
    print("Average waiting time:", round(average_wait, 4))
    print("Maximum SimPy queue observed:", peak_waiting_queue[node.node_id])


# =====================================================
# 14. TASK EXECUTION DETAILS
# =====================================================

print("\n========== TASK EXECUTION RECORDS ==========")

print(
    f"{'TASK':<18}"
    f"{'NODE':<12}"
    f"{'START':>10}"
    f"{'WAIT':>10}"
    f"{'EXEC':>10}"
    f"{'FINISH':>10}"
    f"{'STATUS':>12}"
)

for record in all_records:

    print(
        f"{record.task_id:<18}"
        f"{str(record.node_id):<12}"
        f"{float(record.start_time or 0):>10.2f}"
        f"{float(record.waiting_time or 0):>10.2f}"
        f"{float(record.execution_time or 0):>10.2f}"
        f"{float(record.finish_time or 0):>10.2f}"
        f"{str(record.status):>12}"
    )


# =====================================================
# 15. CLOSE ENVIRONMENT
# =====================================================

env.close()

print("\n========== EXPERIMENT COMPLETED ==========")
