'''
Created on Apr 30, 2017

@author: ny
'''

import timeit
import matplotlib.pyplot as plt
import numpy as np
np.random.seed(0)

import tensorflow as tf
tf.set_random_seed(0)

from rl_gym.agents.monte_carlo_agent import MonteCarloTabularAgent
from rl_gym.agents.sarsa_agent import SarsaTabularAgent
from rl_gym.agents.qlearning_agent import QLearningTabularAgent, QLearningFunctionAproximationAgent
from rl_gym.agents.policy_gradient_agent import PolicyGradientAgent, ValueModel, PolicyModel
from rl_gym.agents.dqn_agent import DQNAgent, DQNModel

from rl_gym.environments import gym_like as gym
from rl_gym.models.linear_models import RbfRegressor
from rl_gym.models.mlp_models import FeedForwardModel
from rl_gym.environments.grid_world import GridWorldSolver, EnvironmentFactory, EnvironmentBase

GAMMA = 0.9
ALPHA = 0.8

REWARD_GOAL = 10

def create_model(env, model_name, verbose=False):
    obs = env.reset()
    obs_dim = len(np.array([obs]))
    if model_name == 'rbf':
        observation_examples = np.array([env.observation_space.sample() for x in range(100)])
        model = RbfRegressor(in_size=obs_dim, num_features=200, output_size=env.action_space.n, gammmas=[3.0, 2.0, 1.5, 1.0], normalize=False)
        model.fit_features(observation_examples, env)
        gamma = 0.99
    elif model_name == 'ff':
        mid_size = 64
        model = FeedForwardModel(in_size=obs_dim, out_sizes=[mid_size, mid_size, mid_size, int(mid_size/2), env.action_space.n],verbose=verbose)
        gamma = 0.99

    return model, gamma

def create_agent(env, agent_type, gamma, alpha, verbosity=0):
    class EnvDescriptor(object):
        def __init__(self):
            self.episod_limit = EnvironmentBase.grid_size
        def action_to_str(self, action):
            return EnvironmentBase.action_to_str(action)

    agent_verb_level = 3
    if agent_type == "monte_carlo":
        agent = MonteCarloTabularAgent(gamma=gamma, env_descriptor=EnvDescriptor(), verbose=verbosity >= agent_verb_level)
    elif agent_type == "sarsa":
        agent = SarsaTabularAgent(gamma=gamma, alpha=alpha, env_descriptor=EnvDescriptor(), verbose=verbosity >= agent_verb_level)
    elif agent_type == "qlearning":
        agent = QLearningTabularAgent(gamma=gamma, alpha=alpha, env_descriptor=EnvDescriptor(), verbose=verbosity >= agent_verb_level)
    elif agent_type == "qlearning_fa":
        model, gamma = create_model(env, 'ff')
        agent = QLearningFunctionAproximationAgent(model=model, gamma=gamma, eps_decay=0.9, verbose=verbosity >= agent_verb_level)
    elif agent_type == "pg":
        actor = PolicyModel(env.observation_space.shape[0], env.action_space.n, [])
        critic = ValueModel(env.observation_space.shape[0], [64, 64])
        agent = PolicyGradientAgent(actor, critic, gamma=0.99)
    elif agent_type == "dqn":
        D = env.observation_space.shape[0]
        K = env.action_space.n
        sizes = [4, 4]
        gamma = 0.99
        model = DQNModel(D, K, sizes, gamma=gamma, min_experiences=10, max_experiences=400, batch_sz=8)
        target_model = DQNModel(D, K, sizes, gamma=gamma, min_experiences=10, max_experiences=400, batch_sz=4)
        agent = DQNAgent(model, target_model, gamma=gamma, copy_period=50)

    return agent

def create_environment(env_name):
    if env_name == 'BasicGridWorld-v0':
        iters = EnvironmentBase.grid_size
        env_type = EnvironmentFactory.EnvironmentType.RandomPlayer
    elif env_name == 'BasicGridWorld-v1':
        iters = EnvironmentBase.grid_size**2
        env_type = EnvironmentFactory.EnvironmentType.RandomPlayerAndGoal
    elif env_name == 'BasicGridWorld-v2':
        iters = EnvironmentBase.grid_size**3
        env_type = EnvironmentFactory.EnvironmentType.RandomPlayerGoalAndPit
    elif env_name == 'BasicGridWorld-v3':
        iters = EnvironmentBase.grid_size**4
        env_type = EnvironmentFactory.EnvironmentType.AllRandom

    env = gym.make(env_name)
    return env, iters, env_type

def train(agent, env, num_iter, verbosity=0):
    if verbosity >= 1:
        print("Train agent for %d iterations." % num_iter)
        start_time = timeit.default_timer()

    steps = 0
    mean_return = 0
    # num_iter=100
    for i in range(num_iter):
        if verbosity >= 2:
            print("Episode %d." % i)
        stps, total_return, r = agent.single_episode_train(env)
        mean_return+=total_return
        if verbosity >= 2:
            print("Episode return: %f" % total_return)
        steps += stps

    mean_return /= num_iter
    if verbosity >= 1:
        elapsed = timeit.default_timer() - start_time
        print("Mean return: %f" % mean_return)
        print("Training time %.3f[ms]" % (elapsed * 1000))
    if verbosity == 0:
        print(" steps: %d" % steps)
    return steps

def train_agent(agent_name, env_name, gamma, alpha, verbosity=1):
    env, iters, env_type = create_environment(env_name)
    agent = create_agent(env, agent_name, gamma, alpha, verbosity=verbosity)
    env_factory = EnvironmentFactory(env_type)
    solver = GridWorldSolver(env_factory, agent)
    print("Evaluate %s performance on %s grid world\n" % (agent.__class__.__name__, env.__class__.__name__))
    if verbosity >= 0:
        print("World example:")
        env.reset()
        env.render()
        print()

    start_time = timeit.default_timer()

    save_model = False
    converged = False
    rewards = []
    total_steps = 0
    total_iterations = 0
    convergence_count = 0
    CONVERGENCE_LIMIT = 10e-3
    CONVERGENCE_STOP_COUNT = 2
    MAX_ITER = 10

    train_iter = iters
    eval_iter = iters
    while not converged:
        print("[%d] Train agent with all possible states" % total_iterations)
        steps = train(agent, env, train_iter, verbosity)
        total_steps += steps
        print("[%d] Evaluate agent to test convergence" % total_iterations)
        res = solver.evaluate(range(eval_iter), env_wrapper = env, verbosity = verbosity)
        print("Reward: %f" % res)
        rewards.append(res.mean())
        if res.max() == REWARD_GOAL:
            converged = True
        if total_iterations > 0:
            diff = rewards[total_iterations] - rewards[total_iterations - 1]
            if np.abs(diff) < CONVERGENCE_LIMIT:
                convergence_count += 1

        if convergence_count >= CONVERGENCE_STOP_COUNT:
            converged = True

        if verbosity >= 0:
            print()
        total_iterations += 1
        # if total_iterations % 2 == 0:
        #     agent.adjust()
        if total_iterations > MAX_ITER:
            break
        # break

    elapsed = timeit.default_timer() - start_time

    print("Evaluation finished.")
    print("Agent final reward is %f" % res)
    print("Training finished after %d iterations. Total learning steps are %d." % (total_iterations, total_steps))
    print("Total time spent %.3f[s]" % elapsed)
    print("Final mean overal reward %f" % rewards[-1:][0])
    print("Saving V table to vtable.bin")
    if save_model:
        agent.save_model('vtable.bin')

    return rewards, total_iterations, total_steps

if __name__ == '__main__':
    # Prepare Agent
    verbosity = 1  # 0 - no verbosity; 1 - show prints between episodes; 2 - show agent log
    envs = ['BasicGridWorld-v0', 'BasicGridWorld-v1', 'BasicGridWorld-v2', 'BasicGridWorld-v3']
    # agents = ["monte_carlo", "sarsa", "qlearning", "qlearning_fa"]
    # agents = ["sarsa", "qlearning"]
    # agents = ["qlearning"]
    # agents = ["qlearning_fa"]
    agents = ["pg"]
    # agents = ["dqn"]
    res = {}
    max_it = -1
    env_name = envs[0]
    for agent in agents:
        res[agent] = train_agent(agent, env_name, gamma=GAMMA, alpha=ALPHA, verbosity=verbosity)
        if res[agent][1] > max_it:
            max_it = res[agent][1]

    print()
    fig, ax = plt.subplots()
    for agent in agents:
        rewards = res[agent][0]
        it = res[agent][1]
        steps = res[agent][2]
        print("Agent: %s, training iterations: %d, total steps %d, final reward %f" % (agent, it, steps, rewards[-1:][0]))
        rewards = np.append(rewards, [rewards[-1:][0]] * (max_it - len(rewards)))
        ax.plot(rewards, label="%s, %d iter, %d steps" % (agent, it, steps))

    ax.legend(loc='lower right', shadow=True)
    plt.show()
    print('Done')