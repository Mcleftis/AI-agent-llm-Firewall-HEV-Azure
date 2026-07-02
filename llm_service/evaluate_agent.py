import os
import sys
import torch
import numpy as np
import mlflow

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_agent_training import CustomPPOActorCritic

os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

def load_rl_agent():
    device = "cpu"
    model = CustomPPOActorCritic()
    model.load_state_dict(torch.load("ppo_hev_actor_critic.pth", map_location=device))
    model.eval()
    return model, device

def run_evaluation():
    mlflow.set_tracking_uri("http://localhost:5000")
    mlflow.set_experiment("HEV_RL_Evaluation")

    agent, device = load_rl_agent()

    num_steps = 100
    speed_max = 150.0
    dist_start = 5000.0
    soc_start = 100.0

    state_agent = [0.0, 0.0, dist_start, soc_start]

    cumulative_reward = 0.0
    agent_energy_used = 0.0
    baseline_energy_used = 0.0
    constraint_violations = 0

    with mlflow.start_run():
        mlflow.log_param("model_type", "CustomPPOActorCritic")
        mlflow.log_param("simulation_steps", num_steps)

        for step in range(num_steps):
            norm_state = [
                state_agent[0] / speed_max,
                state_agent[1] / 10.0,
                state_agent[2] / dist_start,
                state_agent[3] / soc_start
            ]
            obs_tensor = torch.tensor([norm_state], dtype=torch.float32).to(device)

            with torch.no_grad():
                action_tensor, _ = agent(obs_tensor)

            agent_throttle = float(action_tensor.cpu().numpy().item())
            agent_throttle = max(0.0, min(1.0, agent_throttle))

            baseline_throttle = 0.40

            if state_agent[3] < 20.0 and agent_throttle > 0.10:
                constraint_violations += 1

            step_reward = float((state_agent[0] / speed_max) - (agent_throttle * 0.5) - (1.0 - (state_agent[3] / soc_start)))
            cumulative_reward += step_reward

            agent_energy_used += agent_throttle * 0.5
            baseline_energy_used += baseline_throttle * 0.5

            state_agent[0] = max(0.0, min(speed_max, state_agent[0] + (agent_throttle * 10.0) - 2.0))
            state_agent[2] = max(0.0, state_agent[2] - (state_agent[0] / 3.6))
            state_agent[3] = max(0.0, state_agent[3] - (agent_throttle * 0.5))
            state_agent[1] = np.sin(step / 5.0) * 2.0

            mlflow.log_metric("live_soc_agent", state_agent[3], step=step)
            mlflow.log_metric("live_throttle_agent", agent_throttle, step=step)
            mlflow.log_metric("cumulative_reward", cumulative_reward, step=step)
            mlflow.log_metric("baseline_energy_used", baseline_energy_used, step=step)
            mlflow.log_metric("agent_energy_used", agent_energy_used, step=step)

        energy_saved = baseline_energy_used - agent_energy_used

        mlflow.log_metric("final_cumulative_reward", cumulative_reward)
        mlflow.log_metric("total_energy_saved", energy_saved)
        mlflow.log_metric("constraint_violations", constraint_violations)

if __name__ == "__main__":
    run_evaluation()
