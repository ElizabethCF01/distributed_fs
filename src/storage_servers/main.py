from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import argparse

app = FastAPI()
CHUNK_DIR = "storage"
os.makedirs(CHUNK_DIR, exist_ok=True)

@app.post("/chunks/{chunk_id}")
async def upload_chunk(chunk_id: str, chunk: UploadFile = File(...)):
    file_path = os.path.join(CHUNK_DIR, chunk_id)
    with open(file_path, "wb") as f:
        content = await chunk.read()
        f.write(content)
    return {"status": "saved", "chunk_id": chunk_id}

@app.get("/chunks/{chunk_id}")
async def download_chunk(chunk_id: str):
    file_path = os.path.join(CHUNK_DIR, chunk_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Chunk not found")
    return FileResponse(file_path, media_type="application/octet-stream")

@app.delete("/chunks/{chunk_id}")
async def delete_chunk(chunk_id: str):
    file_path = os.path.join(CHUNK_DIR, chunk_id)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Chunk not found")


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    uvicorn.run("server:app", host="0.0.0.0", port=args.port)
