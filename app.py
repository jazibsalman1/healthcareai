from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import asyncio
import subprocess
import logging

app = FastAPI()

# Logging setup
logging.basicConfig(level=logging.INFO)

# Mount static folder to serve CSS/JS/images
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the index.html on root
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# Pydantic model for request validation
class TriageRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., gt=0, lt=120)
    symptoms: str = Field(..., min_length=5, max_length=500)

@app.post("/api/triage_stream")
async def triage_stream(req: Request):
    try:
        data = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Validate incoming data manually with Pydantic
    try:
        triage_data = TriageRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    prompt = f"""
Patient Name: {triage_data.name}
Age: {triage_data.age}
Symptoms: {triage_data.symptoms}

You are a professional medical triage assistant.
Provide a concise, clear, and safe advice for the patient.
Keep it short and easy to understand.
Avoid dangerous or misleading suggestions.
Respond as a helpful human medical assistant.
"""

    # Run ollama subprocess asynchronously
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "run", "medllama2",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        logging.error(f"Failed to start ollama subprocess: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start AI model process")

    # Send prompt to ollama stdin
    try:
        process.stdin.write(prompt.encode())
        await process.stdin.drain()
        process.stdin.close()
    except Exception as e:
        logging.error(f"Error writing to ollama stdin: {str(e)}")
        raise HTTPException(status_code=500, detail="Error sending prompt to AI model")

    async def stream_generator():
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()
            # Also log and yield any stderr output if needed
            stderr = await process.stderr.read()
            if stderr:
                logging.warning(f"Ollama stderr: {stderr.decode().strip()}")
        except Exception as e:
            yield f"\n[Error streaming AI output: {str(e)}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")


# 404 Error handler
@app.exception_handler(404)
def not_found_exception_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"message": "Resource not found. Please check the URL."}
    )

# 500 Error handler
@app.exception_handler(500)
def internal_server_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error. Please try again later."}
    )