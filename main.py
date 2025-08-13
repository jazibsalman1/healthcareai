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

# Serve index.html at root
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
    # Parse incoming JSON request
    try:
        data = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Validate incoming data
    try:
        triage_data = TriageRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Prompt for TinyLlama
    prompt = f"""You are a professional medical triage assistant.
Provide concise, safe, and clear medical advice.
Patient Info:
- Name: {triage_data.name}
- Age: {triage_data.age}
- Symptoms: {triage_data.symptoms}

Triage advice:
"""

    # Run ollama with TinyLlama
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "run", "tinyllama",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        logging.error(f"Failed to start ollama subprocess: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start AI model process")

    # Send prompt to TinyLlama
    try:
        process.stdin.write(prompt.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()
    except Exception as e:
        logging.error(f"Error writing to ollama stdin: {str(e)}")
        raise HTTPException(status_code=500, detail="Error sending prompt to AI model")

    # Streaming generator
    async def stream_generator():
        try:
            buffer = ""
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                decoded_line = line.decode()
                buffer += decoded_line

                # Send chunks for better UX
                if len(buffer) > 50 or "\n" in buffer:
                    yield buffer
                    buffer = ""

            # Yield leftover buffer
            if buffer:
                yield buffer

            # Log stderr output
            stderr = await process.stderr.read()
            if stderr:
                stderr_text = stderr.decode().strip()
                if stderr_text:
                    logging.warning(f"TinyLlama stderr: {stderr_text}")

        except Exception as e:
            yield f"\n[Error streaming AI output: {str(e)}]"
        finally:
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    logging.warning("Forcibly terminated ollama process due to timeout")

    return StreamingResponse(stream_generator(), media_type="text/plain")

# Health check
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "model": "tinyllama"}

# 404 handler
@app.exception_handler(404)
def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"message": "Resource not found. Please check the URL."}
    )

# 500 handler
@app.exception_handler(500)
def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error. Please try again later."}
    )
