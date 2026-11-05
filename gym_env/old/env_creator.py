from .environment import QCloudRLEnv
from .wrappers import (
    ScaleQCloudRLReward,
    GymNormalizeObservation,
    RescaleQCloudRLObservation,
)


def qcloudrl_env_creator(env_config):

    env_config = dict(env_config)

    broker = env_config.pop("broker", None)
    qnodes = env_config.pop("qnodes", None)
    task_source = env_config.pop("task_source", None)

    config = env_config.pop("config", None)

    if broker is None:
        raise ValueError("Broker is not specified.")

    if qnodes is None:
        raise ValueError("QNodes are not specified.")

    if task_source is None:
        raise ValueError("Task source is not specified.")

    env = QCloudRLEnv(
        broker=broker,
        qnodes=qnodes,
        task_source=task_source,
        config=config,
        execution_time_estimator=env_config.pop(
            "execution_time_estimator",
            None,
        ),
        render_mode=env_config.pop(
            "render_mode",
            None,
        ),
    )

    # -------------------------------------
    # Observation filter
    # -------------------------------------

    obs_filter = env_config.pop(
        "obs_filter",
        None,
    )

    if obs_filter == "rescale_-1_1":

        env = RescaleQCloudRLObservation(env)

    elif obs_filter == "normalize":

        env = GymNormalizeObservation(env)

    elif obs_filter is not None:

        raise ValueError(
            f"Unknown observation filter: {obs_filter}"
        )

    # -------------------------------------
    # Reward filter
    # -------------------------------------

    reward_filter = env_config.pop(
        "reward_filter",
        None,
    )

    if reward_filter == "scale":

        reward_scale = env_config.pop(
            "reward_scale",
            2.0,
        )

        env = ScaleQCloudRLReward(
            env,
            scale=reward_scale,
        )

    elif reward_filter is not None:

        raise ValueError(
            f"Unknown reward filter: {reward_filter}"
        )

    return env