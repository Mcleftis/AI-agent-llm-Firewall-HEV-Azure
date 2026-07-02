import os
import requests
import torch
import numpy as np
import mlflow
from pydantic import BaseModel

os.environ["PYTHONUTF8"] = "1"

mlflow.set_tracking_uri("http://mlflow_server:5000")
try:
    mlflow.set_experiment("HEV_NeuroSymbolic_Live")
    mlflow_enabled = True
except Exception:
    mlflow_enabled = False

class TelemetryState(BaseModel):
    speed_kmh: float
    slope: float
    distance_m: float
    soc_pct: float

class AIOrchestrator:
    def __init__(self, llm_endpoint="http://hev_llm:8001/predict_intent"):
        self.llm_endpoint = llm_endpoint
        self.cached_intent = None
        self.last_user_text = ""
        self.state_history = []
        self.max_history = 100

    def _update_history(self, telemetry: TelemetryState):
        self.state_history.append(telemetry)
        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)

    def fetch_cognitive_constraints(self, user_text: str) -> dict:
        if user_text == self.last_user_text and self.cached_intent is not None:
            return self.cached_intent
            
        try:
            response = requests.post(
                self.llm_endpoint,
                json={"text": user_text},
                timeout=1.5
            )
            response.raise_for_status()
            self.cached_intent = response.json()
            self.last_user_text = user_text
            return self.cached_intent
        except Exception:
            return {"urgency": 2, "intent": "eco", "max_throttle": 0.4, "use_battery": True}

    def compute_vehicle_action(self, rl_agent, user_text: str, telemetry: TelemetryState) -> dict:
        self._update_history(telemetry)
        constraints = self.fetch_cognitive_constraints(user_text)
        
        obs_np = np.array([
            telemetry.speed_kmh,
            telemetry.slope,
            telemetry.distance_m,
            telemetry.soc_pct
        ], dtype=np.float32)
        
        obs_tensor = torch.tensor(obs_np).unsqueeze(0)
        
        with torch.no_grad():
            action = rl_agent.predict(obs_tensor, deterministic=True)
            raw_throttle = float(action[0])
            
        max_t = constraints.get("max_throttle", 1.0)
        final_throttle = min(max(raw_throttle, 0.0), max_t)
        
        if not constraints.get("use_battery", True) and telemetry.soc_pct < 20.0:
            final_throttle = min(final_throttle, 0.2)
            
        if mlflow_enabled:
            try:
                with mlflow.start_run(run_name="live_inference", nested=True):
                    mlflow.log_param("user_intent", constraints.get("intent", "eco"))
                    mlflow.log_metric("speed_in", telemetry.speed_kmh)
                    mlflow.log_metric("soc_in", telemetry.soc_pct)
                    mlflow.log_metric("final_throttle", final_throttle)
            except Exception:
                pass
            
        return {
            "intent_applied": constraints.get("intent", "eco"),
            "raw_throttle": raw_throttle,
            "final_throttle": final_throttle,
            "history_length": len(self.state_history)
        }

global_orchestrator = AIOrchestrator()
