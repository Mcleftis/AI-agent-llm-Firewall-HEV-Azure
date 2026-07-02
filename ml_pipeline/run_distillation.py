import os
import json
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments

os.environ["PYTHONUTF8"] = "1"

data = [
    {"text": "Βιάζομαι πολύ να φτάσω νοσοκομείο", "label": 0},
    {"text": "Επείγον περιστατικό τρέξε", "label": 0},
    {"text": "Πάμε χαλαρά μια βόλτα", "label": 1},
    {"text": "Δεν έχω βιασύνη", "label": 1},
    {"text": "Θέλω μέγιστη οικονομία καυσίμου", "label": 2},
    {"text": "Πρόσεχε την μπαταρία", "label": 2},
    {"text": "Άνοιξε το γκάζι τέρμα", "label": 3},
    {"text": "Θέλω σπορ οδήγηση", "label": 3}
]

label_map = {
    0: {"urgency": 5, "intent": "emergency", "max_throttle": 1.0, "use_battery": True},
    1: {"urgency": 1, "intent": "leisure", "max_throttle": 0.5, "use_battery": False},
    2: {"urgency": 2, "intent": "eco", "max_throttle": 0.4, "use_battery": True},
    3: {"urgency": 4, "intent": "sport", "max_throttle": 0.9, "use_battery": False}
}

os.makedirs("distillation_data", exist_ok=True)

with open("distillation_data/dataset.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

dataset = Dataset.from_list(data)

model_id = "distilbert-base-multilingual-cased"
tokenizer = AutoTokenizer.from_pretrained(model_id)

def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=32)

tokenized_datasets = dataset.map(tokenize_function, batched=True)

model = AutoModelForSequenceClassification.from_pretrained(model_id, num_labels=4)

training_args = TrainingArguments(
    output_dir="./distilled_model_checkpoints",
    num_train_epochs=5,
    per_device_train_batch_size=2,
    save_steps=10,
    logging_steps=1,
    use_cpu=True
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets,
)

trainer.train()

trainer.save_model("./distilled_model/final")
tokenizer.save_pretrained("./distilled_model/final")

with open("./distilled_model/final/label_map.json", "w", encoding="utf-8") as f:
    json.dump(label_map, f, ensure_ascii=False)