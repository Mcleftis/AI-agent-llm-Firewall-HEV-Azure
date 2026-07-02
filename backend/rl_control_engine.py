import os
import requests
import torch
import torch.nn as nn
import numpy as np

os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

class CustomPPOActorCritic(nn.Module):
    def __init__(self, obs_dim=4, action_dim=1):
        super(CustomPPOActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, action_dim),
            nn.Tanh()
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
        
    def predict(self, obs, deterministic=True):
        action_mean = self.actor(obs)
        if deterministic:
            return action_mean.detach().cpu().numpy()[0]
        else:
            action_std = torch.exp(self.action_log_std)
            dist = torch.distributions.Normal(action_mean, action_std)
            action = dist.sample()
            action = torch.clamp(action, -1.0, 1.0)
            return action.detach().cpu().numpy()[0]

def get_llm_constraints(user_text):
    try:
        resp = requests.post(
            "http://hev_llm:8001/predict_intent", 
            json={"text": user_text},
            timeout=2.0
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"urgency": 2, "intent": "eco", "max_throttle": 0.4, "use_battery": True}

def load_rl_agent():
    model_path = "ppo_hev_actor_critic.pth"
    device = torch.device("cpu")
    rl_model = CustomPPOActorCritic(obs_dim=4, action_dim=1).to(device)
    if os.path.exists(model_path):
        rl_model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    rl_model.eval()
    return rl_model, device

def compute_action(user_text, telemetry):
    constraints = get_llm_constraints(user_text)
    rl_agent, rl_device = load_rl_agent()
    
    speed_max = 150.0
    dist_start = 5000.0
    soc_start = 100.0

    obs_np = np.array([
        telemetry["speed_kmh"] / speed_max, 
        telemetry["slope"] / 10.0, 
        telemetry["distance_m"] / dist_start, 
        telemetry["soc_pct"] / soc_start
    ], dtype=np.float32)
    
    obs_tensor = torch.tensor(obs_np).unsqueeze(0).to(rl_device)
    
    with torch.no_grad():
        action = rl_agent.predict(obs_tensor, deterministic=True)
        raw_throttle = float(action[0])
    
    max_t = constraints.get("max_throttle", 1.0)
    final_throttle = min(max(raw_throttle, 0.0), max_t)
    
    if not constraints.get("use_battery", True) and telemetry["soc_pct"] < 20.0:
        final_throttle = min(final_throttle, 0.2)
        
    return {
        "intent_applied": constraints["intent"],
        "raw_rl_throttle": raw_throttle,
        "final_throttle": final_throttle
    }