import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from state_orchestrator import global_orchestrator
from rl_control_engine import load_rl_agent
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

os.environ["PYTHONUTF8"] = "1"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

SECURITY_ENABLED = False

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("System Initialization via Lifespan")
    if SECURITY_ENABLED:
        logging.info("Security modules are ACTIVE.")
    else:
        logging.warning("SECURITY IS DISABLED.")
    
    global_rl_agent, global_rl_device = load_rl_agent()
    app.state.rl_agent = global_rl_agent
    
    yield
    
    logging.info("Shutting down System Lifespan")

app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Instrumentator().instrument(app).expose(app)

class DriveRequest(BaseModel):
    user_text: str
    speed_kmh: float
    slope: float
    distance_m: float
    soc_pct: float

@app.post("/drive")
@limiter.limit("5/minute")
def drive_vehicle(request: Request, req: DriveRequest):
    try:
        rl_agent = app.state.rl_agent
        decision = global_orchestrator.compute_vehicle_action(rl_agent, req.user_text, req)
        return decision
        
    except Exception as e:
        logging.error(f"Error during control computation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
