
# from qcloudrl.circuits.service import CircuitService
# from qcloudrl.QTask.task_factory import TaskFactory
# from qcloudrl.Qnode.qnode import QNode
# from qcloudrl.Broker.broker import Broker

# from gym_env.env_creator import qcloudrl_env_creator
# from gym_env.config import GymEnvConfig

# from schedulers import (
#     RandomScheduler,
#     FIFOScheduler,
#     PriorityScheduler,
#     GreedyScheduler,
#     BestFitScheduler,
# )


# # =================================================
# # 1. INITIALIZE DATASET
# # =================================================

# circuit_service = CircuitService(
#     dataset_dir="dataset/mqt_bench",
#     dataset_name="mqt_bench",
#     cache_capacity=32,
# )

# circuit_service.load_manifest()

# records = circuit_service.list_circuits()

# if not records:
#     raise RuntimeError("No circuits found.")

# print(circuit_service)

# task_factory = TaskFactory(circuit_service)

# print(f"Loaded circuit records: {len(records)}")


# # =================================================
# # 2. QNODE / BACKEND CONFIGURATION
# # =================================================

# BACKEND_NAMES = {
#     "node_0": "Washington",
#     "node_1": "Kolkata",
#     "node_2": "Hanoi",
#     "node_3": "Guadalupe",
# }


# def create_qnodes():
#     return [
#         QNode(
#             node_id="node_0",
#             backend_name="washington",
#             circuit_service=circuit_service,
#         ),

#         QNode(
#             node_id="node_1",
#             backend_name="kolkata",
#             circuit_service=circuit_service,
#         ),

#         QNode(
#             node_id="node_2",
#             backend_name="hanoi",
#             circuit_service=circuit_service,
#         ),

#         QNode(
#             node_id="node_3",
#             backend_name="guadalupe",
#             circuit_service=circuit_service,
#         ),
#     ]


# # =================================================
# # 3. TASK SOURCE
# # =================================================

# def task_source():

#     return task_factory.create_tasks(
#         records=records[:50],
#         shots=1024,
#         priority=0,
#         arrival_interval=0.0,
#         first_arrival=0.0,
#     )


# # =================================================
# # 4. ENVIRONMENT CONFIGURATION
# # =================================================

# config = GymEnvConfig(
#     n_qnodes=4,
#     max_tasks=500,
#     default_execution_time=2.0,
#     max_episode_steps=100,
#     reward_mode="inverse_time",
# )


# # =================================================
# # 5. CLASSICAL SCHEDULERS
# # =================================================

# schedulers = [
#     RandomScheduler(seed=42),
#     FIFOScheduler(),
#     PriorityScheduler(),
#     GreedyScheduler(),
#     BestFitScheduler(),
# ]


# # =================================================
# # 6. RUN EXPERIMENTS
# # =================================================

# all_results = {}
# all_assignment_histories = {}

# def print_qnode_queues(env):

#     print("\nQNODE QUEUE STATUS")
#     print("-" * 100)

#     print(
#         f"{'QNode':<12}"
#         f"{'Backend':<18}"
#         f"{'Status':<12}"
#         f"{'Waiting':<12}"
#         f"{'Running':<12}"
#         f"{'Assigned':<12}"
#         f"{'Completed':<12}"
#         f"{'Failed':<10}"
#     )

#     print("-" * 100)

#     for item in env.unwrapped.get_qnode_queue_status():

#         print(
#             f"{item['node_id']:<12}"
#             f"{item['backend']:<18}"
#             f"{item['status']:<12}"
#             f"{item['waiting_count']:<12}"
#             f"{item['running_count']:<12}"
#             f"{item['assigned_count']:<12}"
#             f"{item['completed_count']:<12}"
#             f"{item['failed_count']:<10}"
#         )

#     print("-" * 100)
# for scheduler in schedulers:

#     print("\n")
#     print("=" * 110)
#     print(f"RUNNING SCHEDULER: {scheduler.name}")
#     print("=" * 110)

#     # Fresh simulation components
#     broker = Broker()
#     qnodes = create_qnodes()

#     env = qcloudrl_env_creator({
#         "broker": broker,
#         "qnodes": qnodes,
#         "task_source": task_source,
#         "config": config,
#     })

#     assignment_history = []

#     try:

#         observation, info = env.reset(seed=42)

#         core_env = env.unwrapped

#         terminated = False
#         truncated = False
#         decision_count = 0

#         print(f"\nInitial observation shape: {observation.shape}")
#         print(
#             f"Initial valid actions: "
#             f"{len(core_env.get_valid_actions())}"
#         )

#         print("\nTASK SCHEDULING LOG")
#         print("-" * 110)

#         print(
#             f"{'Decision':<12}"
#             f"{'Simulation Time':<20}"
#             f"{'Task ID':<22}"
#             f"{'QNode':<15}"
#             f"{'Backend':<18}"
#             f"{'Reward':<12}"
#         )

#         print("-" * 110)

#         # -----------------------------------------
#         # SCHEDULING LOOP
#         # -----------------------------------------

#         while not (terminated or truncated):

#             # A. Scheduler selects task-node pair

#             action = scheduler.select_action(core_env)

#             # B. Validate action

#             if not core_env.action_space.contains(action):
#                 raise ValueError(
#                     f"{scheduler.name} returned invalid action: {action}"
#                 )

#             action_mask = core_env.get_action_mask()

#             if action_mask[int(action)] != 1:
#                 raise ValueError(
#                     f"{scheduler.name} selected masked action: {action}"
#                 )

#             # C. Decode selected task and QNode

#             task_index, node_index = core_env.decode_action(action)

#             task = core_env.qtasks[task_index]
#             node = core_env.qnodes[node_index]

#             backend_name = BACKEND_NAMES.get(
#                 node.node_id,
#                 node.node_id
#             )

#             # D. Execute scheduling decision

#             observation, reward, terminated, truncated, info = env.step(
#                 action
#             )

#             decision_count += 1

#             # E. Record assignment

#             assignment_history.append({
#                 "scheduler": scheduler.name,
#                 "decision": decision_count,
#                 "simulation_time": core_env.sim_env.now,
#                 "task_id": task.task_id,
#                 "qnode_id": node.node_id,
#                 "backend": backend_name,
#                 "reward": reward,
#             })

#             # F. Display scheduling decision

#             print(
#                 f"{decision_count:<12}"
#                 f"{core_env.sim_env.now:<20.2f}"
#                 f"{task.task_id:<22}"
#                 f"{node.node_id:<15}"
#                 f"{backend_name:<18}"
#                 f"{reward:<12.4f}"
#             )
            
#             print_qnode_queues(env)
#         # -----------------------------------------
#         # 7. TASK ASSIGNMENT REPORT
#         # -----------------------------------------

#         print("\n")
#         print("=" * 90)
#         print(f"TASK ASSIGNMENT REPORT: {scheduler.name}")
#         print("=" * 90)

#         print(
#             f"{'Decision':<12}"
#             f"{'Task ID':<22}"
#             f"{'QNode':<15}"
#             f"{'Backend':<20}"
#             f"{'Sim. Time':<15}"
#         )

#         print("-" * 90)

#         for item in assignment_history:

#             print(
#                 f"{item['decision']:<12}"
#                 f"{item['task_id']:<22}"
#                 f"{item['qnode_id']:<15}"
#                 f"{item['backend']:<20}"
#                 f"{item['simulation_time']:<15.2f}"
#             )

#         # -----------------------------------------
#         # 8. QNODE TASK DISTRIBUTION
#         # -----------------------------------------

#         print("\n")
#         print("=" * 75)
#         print(f"QNODE TASK DISTRIBUTION: {scheduler.name}")
#         print("=" * 75)

#         print(
#             f"{'QNode':<15}"
#             f"{'Backend':<20}"
#             f"{'Assigned Tasks':<20}"
#             f"{'Distribution':<15}"
#         )

#         print("-" * 75)

#         total_assignments = len(assignment_history)

#         for node in qnodes:

#             assigned = sum(
#                 1
#                 for item in assignment_history
#                 if item["qnode_id"] == node.node_id
#             )

#             percentage = (
#                 assigned / total_assignments * 100
#                 if total_assignments > 0
#                 else 0.0
#             )

#             print(
#                 f"{node.node_id:<15}"
#                 f"{BACKEND_NAMES[node.node_id]:<20}"
#                 f"{assigned:<20}"
#                 f"{percentage:.2f}%"
#             )

#         # -----------------------------------------
#         # 9. COLLECT PERFORMANCE RESULTS
#         # -----------------------------------------

#         summary = core_env.collect_results()

#         all_results[scheduler.name] = summary

#         all_assignment_histories[scheduler.name] = (
#             assignment_history
#         )

#         print("\n")
#         print("=" * 75)
#         print(f"EXPERIMENT PERFORMANCE: {scheduler.name}")
#         print("=" * 75)

#         for key, value in summary.items():

#             print(f"{key:<35}: {value}")

#         print(f"{'Scheduling Decisions':<35}: {decision_count}")
#         print(f"{'Recorded Assignments':<35}: {total_assignments}")

#     finally:
#         env.close()


# # =================================================
# # 10. FINAL CLASSICAL SCHEDULER COMPARISON
# # =================================================

# print("\n\n")
# print("=" * 120)
# print("FINAL CLASSICAL SCHEDULER PERFORMANCE COMPARISON")
# print("=" * 120)

# metrics = [
#     "completed_tasks",
#     "failed_tasks",
#     "average_waiting_time",
#     "average_execution_time",
#     "makespan",
# ]

# print(f"{'Scheduler':<20}", end="")

# for metric in metrics:
#     print(f"{metric:<23}", end="")

# print()

# print("-" * 120)

# for scheduler_name, result in all_results.items():

#     print(f"{scheduler_name:<20}", end="")

#     for metric in metrics:

#         value = result.get(metric, "N/A")

#         if isinstance(value, (float, int)):
#             print(f"{value:<23.4f}", end="")
#         else:
#             print(f"{str(value):<23}", end="")

#     print()


# # =================================================
# # 11. FINAL QNODE ASSIGNMENT COMPARISON
# # =================================================

# print("\n\n")
# print("=" * 100)
# print("QNODE TASK DISTRIBUTION COMPARISON")
# print("=" * 100)

# header = (
#     f"{'Scheduler':<20}"
#     f"{'Washington':<18}"
#     f"{'Kolkata':<18}"
#     f"{'Hanoi':<18}"
#     f"{'Guadalupe':<18}"
# )

# print(header)
# print("-" * 100)

# for scheduler_name, history in all_assignment_histories.items():

#     counts = {
#         node_id: sum(
#             1
#             for item in history
#             if item["qnode_id"] == node_id
#         )
#         for node_id in BACKEND_NAMES
#     }

#     print(
#         f"{scheduler_name:<20}"
#         f"{counts['node_0']:<18}"
#         f"{counts['node_1']:<18}"
#         f"{counts['node_2']:<18}"
#         f"{counts['node_3']:<18}"
#     )


# print("\nAll experiments completed successfully.")




from qcloudrl.circuits.service import CircuitService
from qcloudrl.QTask.task_factory import TaskFactory
from qcloudrl.Qnode.qnode import QNode
from qcloudrl.Broker.broker import Broker

from gym_env.env_creator import qcloudrl_env_creator
from gym_env.config import GymEnvConfig

from schedulers import (
    RandomScheduler,
    FIFOScheduler,
    PriorityScheduler,
    GreedyScheduler,
    BestFitScheduler,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

BACKEND_NAMES = {
    "node_0": "Washington",
    "node_1": "Kolkata",
    "node_2": "Hanoi",
    "node_3": "Guadalupe",
}


# ============================================================
# 2. LOAD MQT BENCH DATASET
# ============================================================

print("\nLoading MQT Bench dataset...", flush=True)

circuit_service = CircuitService(
    dataset_dir="dataset/mqt_bench",
    dataset_name="mqt_bench",
    cache_capacity=32,
)

circuit_service.load_manifest()

records = circuit_service.list_circuits()

print(f"Loaded circuit records: {len(records)}", flush=True)

task_factory = TaskFactory(circuit_service)


# ============================================================
# 3. CREATE QNODES
# ============================================================



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


# ============================================================
# 4. TASK SOURCE
# ============================================================

def task_source():

    return task_factory.create_tasks(
        records=records[:500],
        shots=1024,
        priority=0,
        arrival_interval=0.5,
        first_arrival=0.0,
    )


# ============================================================
# 5. GYM ENVIRONMENT CONFIGURATION
# ============================================================

config = GymEnvConfig(
    n_qnodes=4,
    max_tasks=500,
    default_execution_time=2.0,
    max_episode_steps=500,
    reward_mode="inverse_time",
)


# ============================================================
# 6. CLASSICAL SCHEDULERS
# ============================================================

schedulers = [
    RandomScheduler(seed=42),
    FIFOScheduler(),
    PriorityScheduler(),
    GreedyScheduler(),
    BestFitScheduler(),
]


# ============================================================
# 7. PRINT QNODE QUEUE STATUS
# ============================================================

def print_qnode_queues(queue_status):

    if not queue_status:
        print("Queue snapshot not available.", flush=True)
        return

    print("\nQNODE QUEUE STATUS")
    print("-" * 105)

    print(
        f"{'QNode':<12}"
        f"{'Backend':<18}"
        f"{'Status':<12}"
        f"{'Running':<12}"
        f"{'Waiting':<12}"
        f"{'Assigned':<12}"
        f"{'Completed':<12}"
        f"{'Failed':<10}"
    )

    print("-" * 105)

    for item in queue_status:

        print(
            f"{item['node_id']:<12}"
            f"{item['backend']:<18}"
            f"{item['status']:<12}"
            f"{item['running_count']:<12}"
            f"{item['waiting_count']:<12}"
            f"{item['assigned_count']:<12}"
            f"{item['completed_count']:<12}"
            f"{item['failed_count']:<10}"
        )

    print("-" * 105, flush=True)


# ============================================================
# 8. PRINT ASSIGNMENT REPORT
# ============================================================

def print_assignment_report(assignment_history):

    print("\nTASK ASSIGNMENT REPORT")
    print("=" * 100)

    print(
        f"{'Decision':<12}"
        f"{'Sim Time':<15}"
        f"{'Task ID':<25}"
        f"{'QNode':<15}"
        f"{'Backend':<20}"
        f"{'Reward':<12}"
    )

    print("-" * 100)

    for item in assignment_history:

        print(
            f"{item['decision']:<12}"
            f"{item['simulation_time']:<15.2f}"
            f"{item['task_id']:<25}"
            f"{item['qnode_id']:<15}"
            f"{item['backend']:<20}"
            f"{item['reward']:<12.4f}"
        )

    print("=" * 100, flush=True)


# ============================================================
# 9. PRINT QNODE TASK DISTRIBUTION
# ============================================================

def print_qnode_distribution(assignment_history):

    distribution = {
        node_id: 0 for node_id in BACKEND_NAMES
    }

    for item in assignment_history:

        node_id = item["qnode_id"]

        if node_id in distribution:
            distribution[node_id] += 1

    print("\nQNODE TASK DISTRIBUTION")
    print("-" * 65)

    print(
        f"{'QNode':<15}"
        f"{'Backend':<25}"
        f"{'Assigned Tasks':<15}"
    )

    print("-" * 65)

    for node_id, backend in BACKEND_NAMES.items():

        print(
            f"{node_id:<15}"
            f"{backend:<25}"
            f"{distribution[node_id]:<15}"
        )

    print("-" * 65, flush=True)


# ============================================================
# 10. PRINT PERFORMANCE REPORT
# ============================================================

def print_performance_report(scheduler_name, summary):

    print("\nSCHEDULER PERFORMANCE REPORT")
    print("=" * 70)

    print(f"Scheduler: {scheduler_name}")
    print("-" * 70)

    metrics = [
        "completed_tasks",
        "failed_tasks",
        "average_waiting_time",
        "average_execution_time",
        "makespan",
    ]

    for metric in metrics:

        value = summary.get(metric, "N/A")

        print(f"{metric:<35}: {value}")

    print("=" * 70, flush=True)


# ============================================================
# 11. RUN SCHEDULERS SEQUENTIALLY
# ============================================================

all_results = {}
all_assignment_histories = {}

for scheduler in schedulers:

    scheduler_name = scheduler.__class__.__name__

    # --------------------------------------------------------
    # Create fresh Broker, QNodes and Environment
    # --------------------------------------------------------

    broker = Broker()

    qnodes = create_qnodes()

    env = qcloudrl_env_creator({
        "broker": broker,
        "qnodes": qnodes,
        "task_source": task_source,
        "config": config,
    })

    core_env = env.unwrapped

    assignment_history = []

    decision_count = 0

    try:

        # ----------------------------------------------------
        # Reset environment
        # ----------------------------------------------------

        observation, info = env.reset(seed=42)

        terminated = False
        truncated = False
        # ----------------------------------------------------
        # Scheduling progress header
        # ----------------------------------------------------

        print("\nSCHEDULING PROGRESS")
        print(f"Scheduler: {scheduler_name}")
        print("-" * 100)

        print(
            f"{'Decision':<12}"
            f"{'Sim Time':<15}"
            f"{'Task ID':<25}"
            f"{'QNode':<15}"
            f"{'Backend':<18}"
            f"{'Reward':<12}"
        )

        print("-" * 100, flush=True)

        # ====================================================
        # SCHEDULING LOOP
        # ====================================================

        while not (terminated or truncated):
            # 1. Scheduler selects an action
            action = scheduler.select_action(core_env)

            

            # 2. Validate action
            if not core_env.action_space.contains(action):
                raise ValueError(
                    f"Invalid action from {scheduler_name}: {action}"
                )

            # 3. Decode action
            task_index, node_index = core_env.decode_action(action)

            task = core_env.qtasks[task_index]
            node = core_env.qnodes[node_index]

            backend_name = BACKEND_NAMES.get(
                node.node_id,
                node.node_id,
            )

            decision_time = float(core_env.sim_env.now)
            decision_count += 1

            # 4. Print decision BEFORE env.step()
            print(
                f"[{scheduler_name} | DECISION {decision_count}] "
                f"[DECISION {decision_count}] "
                f"Time={decision_time:.2f} | "
                f"Task={task.task_id} | "
                f"QNode={node.node_id} | "
                f"Backend={backend_name}",
                flush=True,
            )

            # 5. Save assignment
            assignment_record = {
                "decision": decision_count,
                "simulation_time": decision_time,
                "task_id": task.task_id,
                "qnode_id": node.node_id,
                "backend": backend_name,
                "reward": 0.0,
            }

            assignment_history.append(assignment_record)

           

            observation, reward, terminated, truncated, info = env.step(action)

            assignment_record["reward"] = float(reward)


            # 7. Print queue snapshot
            print_qnode_queues(
                info.get("qnode_queue_status", [])
            )

        # ====================================================
        # SCHEDULING COMPLETED
        # ====================================================

        print("\n" + "=" * 100)
        print(f"SCHEDULING COMPLETED: {scheduler_name}")
        print(f"Total scheduling decisions: {decision_count}")
        print("=" * 100, flush=True)

        # ====================================================
        # EXECUTION COMPLETION
        # ====================================================

        print(
            "\nSIMULATION EXECUTION: Completing remaining tasks...",
            flush=True,
        )

        # This is called only after all scheduling decisions.
        if not core_env.episode_finished:
            core_env._finish_episode()

        print(
            "SIMULATION EXECUTION: All remaining tasks processed.",
            flush=True,
        )

        # ====================================================
        # COLLECT RESULTS
        # ====================================================

        summary = core_env.collect_results()

        all_results[scheduler_name] = summary

        all_assignment_histories[scheduler_name] = (
            assignment_history
        )

        # ====================================================
        # REPORT 1: TASK ASSIGNMENTS
        # ====================================================

        print_assignment_report(assignment_history)

        # ====================================================
        # REPORT 2: QNODE DISTRIBUTION
        # ====================================================

        print_qnode_distribution(assignment_history)

        # ====================================================
        # REPORT 3: PERFORMANCE
        # ====================================================

        print_performance_report(
            scheduler_name,
            summary,
        )

        print(
            f"\n{scheduler_name} REPORT COMPLETED.",
            flush=True,
        )

    finally:

        env.close()


# ============================================================
# 12. FINAL PERFORMANCE COMPARISON
# ============================================================

print("\n\n")

print("=" * 110)
print("FINAL CLASSICAL SCHEDULER PERFORMANCE COMPARISON")
print("=" * 110)

print(
    f"{'Scheduler':<20}"
    f"{'Completed':<15}"
    f"{'Failed':<12}"
    f"{'Avg Waiting':<18}"
    f"{'Avg Execution':<18}"
    f"{'Makespan':<15}"
)

print("-" * 110)

for scheduler_name, summary in all_results.items():

    print(
        f"{scheduler_name:<20}"
        f"{summary.get('completed_tasks', 0):<15}"
        f"{summary.get('failed_tasks', 0):<12}"
        f"{summary.get('average_waiting_time', 0):<18.2f}"
        f"{summary.get('average_execution_time', 0):<18.2f}"
        f"{summary.get('makespan', 0):<15.2f}"
    )

print("=" * 110)


# ============================================================
# 13. FINAL QNODE DISTRIBUTION COMPARISON
# ============================================================

print("\nFINAL QNODE DISTRIBUTION COMPARISON")
print("=" * 100)

print(
    f"{'Scheduler':<20}"
    f"{'Washington':<18}"
    f"{'Kolkata':<15}"
    f"{'Hanoi':<15}"
    f"{'Guadalupe':<15}"
)

print("-" * 100)

for scheduler_name, history in all_assignment_histories.items():

    distribution = {
        node_id: 0 for node_id in BACKEND_NAMES
    }

    for item in history:

        node_id = item["qnode_id"]

        if node_id in distribution:
            distribution[node_id] += 1

    print(
        f"{scheduler_name:<20}"
        f"{distribution['node_0']:<18}"
        f"{distribution['node_1']:<15}"
        f"{distribution['node_2']:<15}"
        f"{distribution['node_3']:<15}"
    )

print("=" * 100)

print("\nALL CLASSICAL SCHEDULER EXPERIMENTS COMPLETED.", flush=True)




