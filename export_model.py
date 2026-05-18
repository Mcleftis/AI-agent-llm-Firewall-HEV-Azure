import torch
import os
from stable_baselines3 import PPO

class DeterministicPolicy(torch.nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.features_extractor = policy.features_extractor
        self.mlp_extractor = policy.mlp_extractor.policy_net
        self.action_net = policy.action_net

    def forward(self, obs):
        features = self.features_extractor(obs)
        latent = self.mlp_extractor(features)
        return self.action_net(latent)

if __name__ == "__main__":
    print("Loading SB3 model...")
    model_path = os.path.join("models", "ppo_hev.zip")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Missing {model_path}. You must have the original zip file.")
        
    sb3_model = PPO.load(model_path, device="cpu")

    pure_pytorch_policy = DeterministicPolicy(sb3_model.policy)
    pure_pytorch_policy.eval()

    dummy_input = torch.zeros(1, 4)

    print("Converting to TorchScript...")
    traced_model = torch.jit.trace(pure_pytorch_policy, dummy_input)

    output_path = os.path.join("models", "ppo_policy.pt")
    torch.jit.save(traced_model, output_path)
    print(f"Success! Model saved to: {output_path}")