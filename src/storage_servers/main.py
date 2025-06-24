from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import httpx

app = FastAPI()

CHUNK_DIR = "storage"
naming_url = os.getenv('NAMING_SERVER_URL')
host = os.getenv('HOST', 'storage_server')
port = int(os.getenv('PORT', '8001'))

@app.on_event("startup")
async def startup():
    os.makedirs(CHUNK_DIR, exist_ok=True)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{naming_url}/register_storage", json={"host": host, "port": port})
            resp.raise_for_status()
            data = resp.json()
            print(f"Registered storage server: {data['server_id']}")
        except Exception as e:
            print(f"Failed to register: {e}")

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
    uvicorn.run("main:app", host="0.0.0.0", port=port)
