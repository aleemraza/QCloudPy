
# from gym_env.config import GymEnvConfig
# from gym_env.environment import QCloudRLEnv
# from gym_env.wrappers import (
#     ScaleQCloudRLReward,
#     GymNormalizeObservation,
#     RescaleQCloudRLObservation,
# )


# def qcloudrl_env_creator(env_config):
#     """
#     Create a QCloudRL Gymnasium environment.

#     Required env_config entries:
#         broker: Broker instance
#         qnodes: List of QNode instances
#         task_source: Callable returning fresh QTasks

#     Optional entries:
#         config: GymEnvConfig instance or dictionary
#         obs_filter: None, "rescale_-1_1", or "normalize"
#         reward_filter: None or "scale"
#         reward_scale: Positive reward multiplier
#     """

#     env_config = dict(env_config)

#     broker = env_config.pop("broker", None)
#     qnodes = env_config.pop("qnodes", None)
#     task_source = env_config.pop("task_source", None)

#     config = env_config.pop("config", None)
#     obs_filter = env_config.pop("obs_filter", None)
#     reward_filter = env_config.pop("reward_filter", None)
#     reward_scale = env_config.pop("reward_scale", 2.0)

#     execution_time_estimator = env_config.pop(
#         "execution_time_estimator",
#         None,
#     )

#     render_mode = env_config.pop("render_mode", None)

#     if broker is None:
#         raise ValueError("Broker is required.")

#     if qnodes is None:
#         raise ValueError("QNodes are required.")

#     if task_source is None:
#         raise ValueError("task_source is required.")

#     if env_config:
#         raise ValueError(
#             f"Unknown environment configuration keys: "
#             f"{list(env_config.keys())}"
#         )

#     if config is None:
#         config = GymEnvConfig()
#     elif isinstance(config, dict):
#         config = GymEnvConfig(**config)
#     elif not isinstance(config, GymEnvConfig):
#         raise TypeError(
#             "config must be a GymEnvConfig instance or dictionary."
#         )

#     env = QCloudRLEnv(
#         broker=broker,
#         qnodes=qnodes,
#         task_source=task_source,
#         config=config,
#         execution_time_estimator=execution_time_estimator,
#         render_mode=render_mode,
#     )

#     # Observation wrapper.
#     if obs_filter == "rescale_-1_1":
#         env = RescaleQCloudRLObservation(env)

#     elif obs_filter == "normalize":
#         env = GymNormalizeObservation(env)

#     elif obs_filter is not None:
#         raise ValueError(f"Unknown observation filter: {obs_filter}")

#     # Reward wrapper.
#     if reward_filter == "scale":
#         env = ScaleQCloudRLReward(
#             env,
#             scale=reward_scale,
#         )

#     elif reward_filter is not None:
#         raise ValueError(f"Unknown reward filter: {reward_filter}")

#     return env



from gym_env.config import GymEnvConfig
from gym_env.environment import QCloudRLEnv

from gym_env.wrappers import (
    ScaleQCloudRLReward,
    GymNormalizeObservation,
    RescaleQCloudRLObservation,
)


def qcloudrl_env_creator(env_config):
    """
    Create a QCloudRL Gymnasium environment.

    Required:
        broker: Broker instance
        qnodes: List of QNode instances
        task_source: Callable returning fresh QTasks

    Optional:
        config: GymEnvConfig instance or dictionary
        execution_time_estimator: Optional execution-time estimator
        obs_filter: None, "rescale_-1_1", or "normalize"
        reward_filter: None or "scale"
        reward_scale: Positive reward multiplier
        render_mode: Optional Gymnasium render mode
    """

    if not isinstance(env_config, dict):
        raise TypeError("env_config must be a dictionary.")

    env_config = dict(env_config)

    broker = env_config.pop("broker", None)
    qnodes = env_config.pop("qnodes", None)
    task_source = env_config.pop("task_source", None)

    config = env_config.pop("config", None)

    execution_time_estimator = env_config.pop(
        "execution_time_estimator", None
    )

    obs_filter = env_config.pop("obs_filter", None)
    reward_filter = env_config.pop("reward_filter", None)
    reward_scale = env_config.pop("reward_scale", 2.0)
    render_mode = env_config.pop("render_mode", None)

    # Validate required arguments.
    if broker is None:
        raise ValueError("Broker is required.")

    if not isinstance(qnodes, (list, tuple)) or not qnodes:
        raise ValueError("qnodes must be a non-empty list or tuple.")

    if not callable(task_source):
        raise ValueError("task_source must be callable.")

    if env_config:
        raise ValueError(
            f"Unknown environment configuration keys: "
            f"{list(env_config.keys())}"
        )

    # Validate environment configuration.
    if config is None:
        config = GymEnvConfig()

    elif isinstance(config, dict):
        config = GymEnvConfig(**config)

    elif not isinstance(config, GymEnvConfig):
        raise TypeError(
            "config must be a GymEnvConfig instance or dictionary."
        )

    if len(qnodes) != config.n_qnodes:
        raise ValueError(
            f"Configuration expects {config.n_qnodes} QNodes, "
            f"but {len(qnodes)} were provided."
        )

    if obs_filter not in (None, "rescale_-1_1", "normalize"):
        raise ValueError(f"Unknown observation filter: {obs_filter}")

    if reward_filter not in (None, "scale"):
        raise ValueError(f"Unknown reward filter: {reward_filter}")

    if reward_filter == "scale" and reward_scale <= 0:
        raise ValueError("reward_scale must be positive.")

    # Create the core environment.
    env = QCloudRLEnv(
        broker=broker,
        qnodes=list(qnodes),
        task_source=task_source,
        config=config,
        execution_time_estimator=execution_time_estimator,
        render_mode=render_mode,
    )

    # Apply observation wrapper.
    if obs_filter == "rescale_-1_1":
        env = RescaleQCloudRLObservation(env)

    elif obs_filter == "normalize":
        env = GymNormalizeObservation(env)

    # Apply reward wrapper.
    if reward_filter == "scale":
        env = ScaleQCloudRLReward(
            env,
            scale=reward_scale,
        )

    return env
