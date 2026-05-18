import os
os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def load_finetuned_llm():
    print("Loading Fine-Tuned Agent...")
    base_model_id = "HuggingFaceTB/SmolLM-1.7B"
    adapter_dir = "outputs_hev_lora/final_model"

    tokenizer = AutoTokenizer.from_pretrained(base_model_id, revision="main")
    tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float32,
        device_map="cpu", revision="main",
    )

    llm_model = PeftModel.from_pretrained(base_model, adapter_dir)
    llm_model.eval()

    print("LLM is ready.")
    return llm_model, tokenizer

def ask_llm(model, tokenizer, user_input):
    prompt = f"### User: {user_input} ### Assistant:"
    inputs = tokenizer(prompt, return_tensors="pt").to("cpu")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=50,
            do_sample=False,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    final_answer = response.split("### Assistant:")[-1].strip()
    return final_answer

def load_rl_agent():
    print("Loading TorchScript RL Agent...")
    model_path = os.path.join("models", "ppo_policy.pt")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model path missing: {model_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    rl_model = torch.jit.load(model_path, map_location=device)
    rl_model.eval()
    
    print("RL Agent is ready.")
    return rl_model

if __name__ == "__main__":
    print("System Initializing...")

    llm_model, tokenizer = load_finetuned_llm()
    rl_agent = load_rl_agent()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"

    driver_input = "Βιάζομαι πολύ να φτάσω νοσοκομείο"
    print(f"Input: {driver_input}")

    llm_decision = ask_llm(llm_model, tokenizer, driver_input)
    print(f"LLM Decision: {llm_decision}")

    if rl_agent:
        speed_kmh = 50.0
        slope = 0.0
        distance_m = 100.0
        soc_pct = 40.0

        obs_tensor = torch.tensor([[speed_kmh, slope, distance_m, soc_pct]], dtype=torch.float32).to(device)

        with torch.no_grad():
            action_tensor = rl_agent(obs_tensor)
            throttle = float(action_tensor[0][0].item())

        print(f"Telemetry: Speed={speed_kmh} | Distance={distance_m} | SOC={soc_pct} | Slope={slope}")
        if throttle > 0:
            print(f"Action: ACCELERATE {throttle:.2f}")
        else:
            print(f"Action: BRAKE {abs(throttle):.2f}")