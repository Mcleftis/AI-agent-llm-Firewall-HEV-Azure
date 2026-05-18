import os
os.environ["PYTHONUTF8"] = "1"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "HEV_LLM_Firewall_Finetuning"

import torch
import mlflow
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig

def main():
    mlflow.set_experiment(os.environ["MLFLOW_EXPERIMENT_NAME"])
    with mlflow.start_run() as run:
        dataset_path = "data/hev_intents.jsonl"

        if not os.path.exists("data"):
            os.makedirs("data")
            with open(dataset_path, "w", encoding="utf-8") as f:
                f.write('{"text": "### User: Βιάζομαι πολύ να φτάσω νοσοκομείο ### Assistant: {\\"urgency\\\": 5, \\\"intent\\\": \\\"emergency\\\"}"}\n')
                f.write('{"text": "### User: Πάμε χαλαρά μια βόλτα ### Assistant: {\\"urgency\\\": 1, \\\"intent\\\": \\\"leisure\\\"}"}\n')

        dataset = load_dataset( # nosec B615"json", data_files=dataset_path, split="train")
        model_id = "HuggingFaceTB/SmolLM-1.7B"

        tokenizer = AutoTokenizer.from_pretrained # nosec B615(model_id, revision="main")
        tokenizer.pad_token = tokenizer.eos_token

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        model = AutoModelForCausalLM.from_pretrained # nosec B615(
            model_id,
            torch_dtype=dtype,
            device_map=device, revision="main",
        )

        lora_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)

        mlflow.log_params({
            "model_id": model_id,
            "lora_r": lora_config.r,
            "lora_alpha": lora_config.lora_alpha,
            "device": device,
            "dtype": str(dtype)
        })

        training_args = SFTConfig(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            max_steps=20,
            learning_rate=2e-4,
            fp16=(device == "cuda"),
            bf16=False,
            output_dir="outputs_hev_lora",
            logging_steps=5,
            save_steps=20,
            report_to="mlflow",
        )

        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            args=training_args,
        )

        trainer.train()

        trainer.model.save_pretrained("outputs_hev_lora/final_model")
        tokenizer.save_pretrained("outputs_hev_lora/final_model")

if __name__ == "__main__":
    main()
