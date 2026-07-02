import os
os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def load_finetuned_llm():
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
    return llm_model, tokenizer

def ask_llm(model, tokenizer, user_input):
    prompt = f"### User: {user_input} ### Assistant:"
    inputs = tokenizer(prompt, return_tensors="pt").to("cpu")
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=50, temperature=0.7, do_sample=True
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response.split("### Assistant:")[-1].strip()

def load_rl_agent():
    model_path = os.path.join("models", "ppo_policy.pt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model path missing: {model_path}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rl_model = torch.jit.load(model_path, map_location=device)
    rl_model.eval()
    return rl_model

if __name__ == "__main__":
    speed_kmh = 50.0
    acceleration = 1.2
    engine_power = 20.0
    soc_pct = 80.0

    llm_model, tokenizer = load_finetuned_llm()
    rl_agent = load_rl_agent()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    driver_input = "Βιάζομαι πολύ να φτάσω νοσοκομείο"
    
    print(f"\n--- Testing LLM ---")
    print(f"Input: {driver_input}")
    llm_decision = ask_llm(llm_model, tokenizer, driver_input)
    print(f"Output: {llm_decision}")

    if rl_agent:
        print(f"\n--- Testing RL Agent ---")
        obs_tensor = torch.tensor([[
            speed_kmh,
            acceleration,
            engine_power,
            soc_pct
        ]], dtype=torch.float32).to(device)

        with torch.no_grad():
            rl_action = rl_agent(obs_tensor)

        print(f"State [Speed, Accel, Power, SOC]: [{speed_kmh}, {acceleration}, {engine_power}, {soc_pct}]")
        print(f"Throttle Action: {rl_action.cpu().numpy()[0]}")