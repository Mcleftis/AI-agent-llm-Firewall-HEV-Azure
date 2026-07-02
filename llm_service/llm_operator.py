import os
import json
import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification

os.environ["PYTHONUTF8"] = "1"

app = FastAPI()

MODEL_PATH = "./distilled_model/final"

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()

with open(os.path.join(MODEL_PATH, "label_map.json"), "r", encoding="utf-8") as f:
    label_map = json.load(f)

class IntentRequest(BaseModel):
    text: str

@app.post("/predict_intent")
def predict_intent(req: IntentRequest):
    inputs = tokenizer(req.text, return_tensors="pt", padding="max_length", truncation=True, max_length=32)
    with torch.no_grad():
        outputs = model(**inputs)
    
    predicted_class_id = outputs.logits.argmax(dim=-1).item()
    decision = label_map[str(predicted_class_id)]
    
    return decision
