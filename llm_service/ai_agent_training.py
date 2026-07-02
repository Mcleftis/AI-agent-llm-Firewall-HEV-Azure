import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import multiprocessing as mp

os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"


class CustomPPOActorCritic(nn.Module):
    def __init__(self, obs_dim=4, action_dim=1):
        super(CustomPPOActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, action_dim),
            nn.Sigmoid()
        )
        self.critic = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )
        self.action_log_std = nn.Parameter(torch.zeros(1, action_dim))

    def forward(self, obs):
        return self.actor(obs), self.critic(obs)


class HEVEnv:
    def __init__(self):
        self.speed_max = 150.0
        self.dist_start = 5000.0
        self.soc_start = 100.0
        self.state = np.array([0.0, 0.0, self.dist_start, self.soc_start], dtype=np.float32)
        self.prev_speed = 0.0
        self.step_count = 0
        self.max_steps = 300

    def reset(self):
        self.state = np.array([0.0, 0.0, self.dist_start, self.soc_start], dtype=np.float32)
        self.prev_speed = 0.0
        self.step_count = 0
        return self._get_obs()

    def _get_obs(self):
        return np.array([
            self.state[0] / self.speed_max,
            self.state[1] / 10.0,
            self.state[2] / self.dist_start,
            self.state[3] / self.soc_start
        ], dtype=np.float32)

    def step(self, action, llm_max_throttle=1.0):
        throttle = np.clip(action[0], 0.0, 1.0)

        penalty = 0.0
        if throttle > llm_max_throttle:
            excess = throttle - llm_max_throttle
            penalty = -5.0 * excess

        new_speed = np.clip(self.state[0] + (throttle * 15.0) - 1.0, 0.0, self.speed_max)

        speed_bonus = (new_speed / self.speed_max) * 4.0
        efficiency_penalty = throttle * 0.2
        soc_penalty = (1.0 - (self.state[3] / self.soc_start)) * 0.3

        reward = float(speed_bonus - efficiency_penalty - soc_penalty + penalty)

        self.state[0] = new_speed
        self.state[2] = max(0.0, self.state[2] - (self.state[0] / 3.6))
        self.state[3] = max(0.0, self.state[3] - (throttle * 0.5))
        self.state[1] = np.sin(self.step_count / 5.0) * 2.0

        self.step_count += 1
        done = self.step_count >= self.max_steps or self.state[3] <= 0

        return self._get_obs(), reward, done


def environment_worker(worker_id, pipe, seed):
    np.random.seed(seed)
    env = HEVEnv()
    while True:
        command, data = pipe.recv()
        if command == "reset":
            pipe.send(env.reset())
        elif command == "step":
            action, llm_max = data
            obs, reward, done = env.step(action, llm_max)
            if done:
                obs = env.reset()
            pipe.send((obs, reward, done))
        elif command == "close":
            break


def train_parallel_ppo():
    num_processes = 2
    num_updates = 1500
    steps_per_update = 100
    ppo_epochs = 4
    clip_param = 0.2
    entropy_coef = 0.01
    llm_constraints = [1.0, 0.5, 0.4, 0.9]

    device = torch.device("cpu")
    model = CustomPPOActorCritic().to(device)
    optimizer = optim.Adam(model.parameters(), lr=3e-4)

    processes = []
    pipes = []
    for i in range(num_processes):
        parent_pipe, child_pipe = mp.Pipe()
        p = mp.Process(target=environment_worker, args=(i, child_pipe, 42 + i))
        p.start()
        processes.append(p)
        pipes.append(parent_pipe)

    states = np.zeros((num_processes, 4), dtype=np.float32)
    for i, pipe in enumerate(pipes):
        pipe.send(("reset", None))
        states[i] = pipe.recv()

    for update in range(num_updates):
        mb_states = []
        mb_actions = []
        mb_rewards = []
        mb_masks = []
        mb_log_probs = []
        mb_values = []

        current_llm_limits = np.random.choice(llm_constraints, size=num_processes)

        for _ in range(steps_per_update):
            states_tensor = torch.FloatTensor(states).to(device)
            with torch.no_grad():
                mean, value = model(states_tensor)
                std = torch.exp(model.action_log_std)
                dist = torch.distributions.Normal(mean, std)
                action = dist.sample()
                log_prob = dist.log_prob(action)

            action_np = action.cpu().numpy()
            next_states = np.zeros_like(states)
            rewards = np.zeros(num_processes, dtype=np.float32)
            dones = np.zeros(num_processes, dtype=np.float32)

            for i, pipe in enumerate(pipes):
                pipe.send(("step", (action_np[i], current_llm_limits[i])))

            for i, pipe in enumerate(pipes):
                obs, reward, done = pipe.recv()
                next_states[i] = obs
                rewards[i] = reward
                dones[i] = float(done)

            mb_states.append(states_tensor)
            mb_actions.append(action)
            mb_rewards.append(torch.FloatTensor(rewards).unsqueeze(1).to(device))
            mb_masks.append(torch.FloatTensor(1.0 - dones).unsqueeze(1).to(device))
            mb_log_probs.append(log_prob)
            mb_values.append(value)

            states = next_states

        states_tensor = torch.FloatTensor(states).to(device)
        with torch.no_grad():
            _, next_value = model(states_tensor)

        returns = []
        gae = 0
        values = mb_values + [next_value]
        for step in reversed(range(steps_per_update)):
            delta = mb_rewards[step] + 0.99 * values[step + 1] * mb_masks[step] - values[step]
            gae = delta + 0.99 * 0.95 * mb_masks[step] * gae
            returns.insert(0, gae + values[step])

        returns = torch.cat(returns).detach()
        log_probs = torch.cat(mb_log_probs).detach()
        values = torch.cat(mb_values).detach()
        states_flat = torch.cat(mb_states)
        actions_flat = torch.cat(mb_actions)

        advantages = returns - values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        for _ in range(ppo_epochs):
            mean, value = model(states_flat)
            std = torch.exp(model.action_log_std)
            dist = torch.distributions.Normal(mean, std)
            new_log_probs = dist.log_prob(actions_flat)
            ratio = torch.exp(new_log_probs - log_probs)

            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1.0 - clip_param, 1.0 + clip_param) * advantages

            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = (returns - value).pow(2).mean()
            entropy_loss = -dist.entropy().mean()
            loss = actor_loss + 0.5 * critic_loss + entropy_coef * entropy_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if update % 100 == 0:
            all_rewards = torch.cat(mb_rewards).mean().item()
            mean_action = torch.cat(mb_actions).mean().item()
            mean_value = torch.cat(mb_values).mean().item()
            adv_std = (returns - values).std().item()
            print(f"Update {update:04d} | Reward: {all_rewards:.3f} | Action: {mean_action:.3f} | Value: {mean_value:.3f} | Adv std: {adv_std:.3f}")

    for pipe in pipes:
        pipe.send(("close", None))
    for p in processes:
        p.join()

    torch.save(model.state_dict(), "ppo_hev_actor_critic.pth")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    train_parallel_ppo()
