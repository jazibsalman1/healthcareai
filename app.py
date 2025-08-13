from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load model from HF Hub
model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

class TriageRequest(BaseModel):
    name: str
    age: int
    symptoms: str

@app.post("/api/triage")
async def triage(req: TriageRequest):
    prompt = f"""You are a professional medical triage assistant.
    Patient Name: {req.name}
    Age: {req.age}
    Symptoms: {req.symptoms}
    Advice:"""

    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_length=300)
    reply = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return {"response": reply}
