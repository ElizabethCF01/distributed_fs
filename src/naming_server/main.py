import uuid
import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis.asyncio as redis_asyncio

app = FastAPI()
redis = None  # to be initialized
REPLICATION_FACTOR = 3

class RegisterStorageRequest(BaseModel):
    host: str
    port: int

class InitFileRequest(BaseModel):
    file_name: str

class ChunkAllocateResponse(BaseModel):
    storage_servers: list  # list of {host, port, server_id}

class FinalizeFileRequest(BaseModel):
    size: int
    chunk_count: int

@app.on_event("startup")
async def startup():
    global redis
    redis = redis_asyncio.Redis(host='redis', port=6379, encoding='utf-8', decode_responses=True)

@app.post("/register_storage")
async def register_storage(req: RegisterStorageRequest):
    server_id = str(uuid.uuid4())
    info = {"host": req.host, "port": req.port}
    await redis.sadd("storage_servers", server_id)
    await redis.set(f"storage:{server_id}", json.dumps(info))
    return {"server_id": server_id}

@app.post("/files/init")
async def init_file(req: InitFileRequest):
    # Check if name exists
    existing = await redis.get(f"file_name_to_id:{req.file_name}")
    if existing:
        raise HTTPException(status_code=400, detail="File name already exists")
    file_id = str(uuid.uuid4())
    await redis.hset(f"file:{file_id}:meta", mapping={"name": req.file_name, "size": "0", "chunk_count": "0"})
    await redis.set(f"file_name_to_id:{req.file_name}", file_id)
    return {"file_id": file_id}

@app.post("/files/{file_id}/chunks")
async def allocate_chunk(file_id: str, chunk_index: int):
    # Check file exists
    exists = await redis.exists(f"file:{file_id}:meta")
    if not exists:
        raise HTTPException(status_code=404, detail="File not found")
    # Get storage servers
    servers = await redis.smembers("storage_servers")
    if len(servers) < REPLICATION_FACTOR:
        raise HTTPException(status_code=500, detail="Not enough storage servers registered")
    import random
    chosen = random.sample(list(servers), REPLICATION_FACTOR)
    server_infos = []
    for sid in chosen:
        data = await redis.get(f"storage:{sid}")
        info = json.loads(data)
        info.update({"server_id": sid})
        server_infos.append(info)
    # Store mapping
    await redis.hset(f"file:{file_id}:chunks", str(chunk_index), ",".join(chosen))
    return {"storage_servers": server_infos}

@app.post("/files/{file_id}/finalize")
async def finalize_file(file_id: str, req: FinalizeFileRequest):
    exists = await redis.exists(f"file:{file_id}:meta")
    if not exists:
        raise HTTPException(status_code=404, detail="File not found")
    await redis.hset(f"file:{file_id}:meta", mapping={"size": str(req.size), "chunk_count": str(req.chunk_count)})
    return {"status": "finalized"}

@app.get("/files/{file_id}/chunks/{chunk_index}")
async def get_chunk_locations(file_id: str, chunk_index: int):
    mapping = await redis.hget(f"file:{file_id}:chunks", str(chunk_index))
    if not mapping:
        raise HTTPException(status_code=404, detail="Chunk not found")
    sids = mapping.split(",")
    server_infos = []
    for sid in sids:
        data = await redis.get(f"storage:{sid}")
        if data:
            info = json.loads(data)
            info.update({"server_id": sid})
            server_infos.append(info)
    return {"storage_servers": server_infos}

@app.get("/files")
async def get_file_by_name(name: str):
    file_id = await redis.get(f"file_name_to_id:{name}")
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found")
    meta = await redis.hgetall(f"file:{file_id}:meta")
    return {"file_id": file_id, **meta}

@app.get("/files/{file_id}/size")
async def get_size(file_id: str):
    meta = await redis.hgetall(f"file:{file_id}:meta")
    if not meta:
        raise HTTPException(status_code=404, detail="File not found")
    return {"size": int(meta.get("size", "0"))}

@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    meta = await redis.hgetall(f"file:{file_id}:meta")
    if not meta:
        raise HTTPException(status_code=404, detail="File not found")
    file_name = meta.get("name")
    chunks = await redis.hgetall(f"file:{file_id}:chunks")
    # Instruct storage servers to delete chunks
    for idx, mapping in chunks.items():
        sids = mapping.split(",")
        for sid in sids:
            data = await redis.get(f"storage:{sid}")
            if data:
                info = json.loads(data)
                # send delete request asynchronously
                asyncio.create_task(delete_chunk_on_storage(info, f"{file_id}_{idx}"))
    # Delete metadata
    await redis.delete(f"file:{file_id}:meta")
    await redis.delete(f"file:{file_id}:chunks")
    await redis.delete(f"file_name_to_id:{file_name}")
    return {"status": "deleted"}

async def delete_chunk_on_storage(info, chunk_id):
    url = f"http://{info['host']}:{info['port']}/chunks/{chunk_id}"
    async with httpx.AsyncClient() as client:
        try:
            await client.delete(url)
        except Exception:
            pass
