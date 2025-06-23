## Distributed Storage Metadata-Service — API Documentation (English)

### 1. Overview

This FastAPI application is the **metadata service** for a chunk-based, replicated distributed-storage system.

- **Redis** (via `redis.asyncio`) stores all metadata in memory.
- File contents live on external **storage servers**; this service only tracks _where_ each replica is stored.
- Every chunk is stored on **3 distinct storage servers** (`REPLICATION_FACTOR = 3`).
- Binary data never passes through this service—only metadata.

```
┌────────────┐           ┌────────────────────────┐
│   Client   │─HTTP─────▶│  Metadata-Service      │
└────────────┘           │  (this application)    │
                         ├─────────────┬──────────┤
                         │  Redis (metadata)      │
                         └─────────────┴──────────┘
                                       │
                                       ▼
                  ┌─────────┬─────────┬─────────┐
                  │Node A   │Node B   │Node C   │ ... (storage servers)
                  └─────────┴─────────┴─────────┘
```

### 2. Redis Key Layout

| Type       | Key Pattern                   | Description                         |
| ---------- | ----------------------------- | ----------------------------------- |
| **Set**    | `storage_servers`             | IDs of all registered storage nodes |
| **String** | `storage:{server_id}`         | JSON: `{host, port}`                |
| **String** | `file_name_to_id:{file_name}` | Maps file name ➜ `file_id`          |
| **Hash**   | `file:{file_id}:meta`         | `name`, `size`, `chunk_count`       |
| **Hash**   | `file:{file_id}:chunks`       | `chunk_index` ➜ `"sid1,sid2,sid3"`  |

### 3. API Endpoints

All endpoints are JSON; they return standard HTTP status codes.

| Method     | Path                                      | Body / Query                          | Response                                              | Notes                                                                               |
| ---------- | ----------------------------------------- | ------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **POST**   | `/register_storage`                       | `{ "host": str, "port": int }`        | `{ "server_id": uuid }`                               | Register a storage node.                                                            |
| **POST**   | `/files/init`                             | `{ "file_name": str }`                | `{ "file_id": uuid }`                                 | Create a new file skeleton; 400 if the name already exists.                         |
| **POST**   | `/files/{file_id}/chunks?chunk_index=int` | —                                     | `{ "storage_servers": [ {host,port,server_id}, … ] }` | Returns 3 random nodes and stores the mapping.                                      |
| **POST**   | `/files/{file_id}/finalize`               | `{ "size": int, "chunk_count": int }` | `{ "status": "finalized" }`                           | Completes the write process.                                                        |
| **GET**    | `/files/{file_id}/chunks/{chunk_index}`   | —                                     | `{ "storage_servers": [ … ] }`                        | Where to read a chunk; 404 if unknown.                                              |
| **GET**    | `/files`                                  | `?name=<file_name>`                   | `{ "file_id": uuid, name, size, chunk_count }`        | Lookup by file name.                                                                |
| **GET**    | `/files/{file_id}/size`                   | —                                     | `{ "size": int }`                                     | Returns file size only.                                                             |
| **DELETE** | `/files/{file_id}`                        | —                                     | `{ "status": "deleted" }`                             | Removes metadata and asynchronously calls each storage node to delete its replicas. |

**Common error codes**

| Code | Meaning                                                        |
| ---- | -------------------------------------------------------------- |
| 400  | File name already in use                                       |
| 404  | File or chunk not found                                        |
| 500  | Fewer than 3 storage servers available when allocating a chunk |

### 4. Typical Workflow

1. **Register storage nodes**

   ```bash
   POST /register_storage
   { "host": "10.0.0.21", "port": 8000 }
   ```

2. **Create file metadata**

   ```bash
   POST /files/init
   { "file_name": "video.mp4" }  → returns file_id
   ```

3. **Upload chunks** (loop over each `chunk_index`)

   1. `POST /files/{file_id}/chunks?chunk_index=i` ➜ receive 3 targets
   2. Client uploads the binary chunk directly to those 3 storage servers.

4. **Finalize**

   ```bash
   POST /files/{file_id}/finalize
   { "size": 104857600, "chunk_count": 64 }
   ```

5. **Read**

   ```bash
   GET /files/{file_id}/chunks/0`
   ```

### 5. Implementation Notes

| Aspect                | Detail                                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Startup**           | Single shared Redis connection is created in the `startup` event.                                            |
| **Replica selection** | `random.sample()` picks 3 distinct server IDs from `storage_servers`.                                        |
| **Delete cleanup**    | `DELETE` requests to storage nodes are fired with `asyncio.create_task`; failures are ignored (best-effort). |
| **Reliability**       | All metadata is kept in Redis; file data durability depends on the external nodes.                           |

### 6. Assumptions & Limitations

| Topic                 | Current State                                                  |
| --------------------- | -------------------------------------------------------------- |
| **Security / Auth**   | None. Production should add tokens, mTLS, etc.                 |
| **Consistency**       | Deletes are eventual (garbage may linger if a node is down).   |
| **High Availability** | Redis is a single point of failure; use Sentinel or Cluster.   |
| **Observability**     | No structured logging or metrics; instrumentation recommended. |
| **Schema Migration**  | No versioning strategy provided.                               |

### 7. Possible Enhancements

1. **Node health-checks / heartbeats** to avoid allocating chunks to dead servers.
2. **Configurable replication factor** per file or per cluster.
3. **Chunk checksums** for integrity verification.
4. **File listing API** with pagination & filters.
5. **Prometheus metrics** and **OpenTelemetry tracing** for monitoring.

---

_Generated on 23 Jun 2025 (Europe/Madrid)._
