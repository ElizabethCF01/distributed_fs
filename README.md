# Distributed Chunk Storage — Project README

> **TL;DR** ‣ `docker compose up` spins up a **Naming‑Server**, **Redis**, and three **Storage‑Servers**. Use the bundled **CLI** container to create, read, size‑check, and delete files via a replicated, chunk‑based file‑system.

---

## 1‑Architecture at a Glance

```
              ┌────────────┐                                ┌─────────┐
   (CLI)      │  Naming    │───redis‑py/async──▶ Redis ──▶ │ Metadata│
  docker ▶──▶│  Server    │                                │   DB    │
              └────┬───────┘                                └─────────┘
                   │   (HTTP JSON)
                   │
     ┌─────────────┼─────────────────────────────────────────────────────────┐
     ▼             ▼             ▼                                           ▼
 ┌─────────┐  ┌─────────┐  ┌─────────┐                             (∞) ┌─────────┐
 │Storage A│  │Storage B│  │Storage C│    … replicated chunk nodes     │Storage N│
 └─────────┘  └─────────┘  └─────────┘                                 └─────────┘
```

| Role               | Container          | Ports | Highlights                              |
| ------------------ | ------------------ | ----- | --------------------------------------- |
| **Naming‑Server**  | `naming_server`    | 8000  | FastAPI service; keeps *metadata only*. |
| **Redis**          | `redis`            | 6379  | Single‑node in‑memory KV store.         |
| **Storage‑Server** | `storage_server‑X` | 5001  | Stores binary chunks on local disk.     |
| **CLI**            | `cli` (ephemeral)  | —     | Helper wrapper for file operations.     |

**Replication Factor = 3** — every chunk is written to three distinct storage nodes.

---

## 2 ‑ Failure Modes

| Category                         | Manifestation               | Critical?                    | Effect & Mitigation                                                                              |
| -------------------------------- | --------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------ |
| **Metadata DB Down**             | Redis not reachable         | **Yes**                      | All reads/writes stall. Run Redis in *Sentinel* or *Cluster* for HA, enable AOF/RDB persistence. |
| **< 3 Healthy Storage Nodes**    | Upload request receives 500 | **Yes**                      | Cannot honour replication factor; auto‑retry after nodes recover or scale out.                   |
| **Storage Disk Loss**            | Chunks missing on a node    | **Yes** (if ≥1 replica lost) | Rely on remaining replicas; trigger background re‑replication (future work).                     |
| **Individual Storage Node Down** | Some replicas offline       | *No* (degraded)              | Reads still succeed (2 replicas left); uploads avoid the down node. Health‑checks recommended.   |
| **Async Delete Failures**        | Orphaned chunks linger      | *No*                         | Wastes disk only. Periodic GC job or manual cleanup.                                             |
| **CLI Container Crash**          | –                           | *No*                         | Stateless; rerun command.                                                                        |

---

## 3 ‑ Dockerised Services

All images are built locally by Compose:

```bash
# Build & start everything
docker compose up --build   # or just: docker compose up
```

> **Tip**   The first run fetches base images and may take a minute.

### File Tree (excerpt)

```
src/
├─ cli/              # CLI helper
├─ naming_server/    # FastAPI+Redis metadata service
└─ storage_servers/  # Chunk server implementation
Dockerfile           # language = python:3.11-slim
└─ docker-compose.yml
```

---

## 4 ‑ Quick Start / End‑to‑End Test

1. **Boot the stack**

   ```bash
   docker compose up -d          # -d = detached
   ```

2. **Create & upload** a sample file (`requirements.txt` → logical name `reqs`):

   ```bash
   docker compose run --rm cli \
     python /app/cli.py --naming-url http://naming_server:8000 \
     create ./requirements.txt reqs
   ```

3. **Read** it back:

   ```bash
   docker compose run --rm cli \
     python /app/cli.py --naming-url http://naming_server:8000 \
     read reqs ./requirements.txt
   ```

4. **Check size** metadata:

   ```bash
   docker compose run --rm cli \
     python /app/cli.py --naming-url http://naming_server:8000 \
     size reqs
   ```

5. **Delete** logical file + replicas:

   ```bash
   docker compose run --rm cli \
     python /app/cli.py --naming-url http://naming_server:8000 \
     delete reqs
   ```

> All CLI commands are simple wrappers around the Metadata‑Service REST API.

---

## 5 ‑ CLI Reference (src/cli/cli.py)

The **CLI** is a thin Python wrapper that hides the REST round‑trips required to work with the distributed store. Each invocation spins up a throw‑away container (`docker compose run cli …`).

### 5.1  Global Option

| Flag                      | Description                    | Example                                  |
| ------------------------- | ------------------------------ | ---------------------------------------- |
| `--naming-url` (required) | Base URL of the Naming‑Server. | `--naming-url http://naming_server:8000` |

### 5.2  Commands

| Command  | Positional Args                | What it Does                                                                                                                                                                                                           |
| -------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create` | `<local_path>` `<remote_name>` | ‣ Splits the *local* file into 1 KiB chunks.<br>‣ Asks Naming‑Server for 3 replica targets *per chunk*.<br>‣ Streams each chunk to every target Storage‑Server.<br>‣ Finalises metadata with total size & chunk‑count. |
| `read`   | `<remote_name>` `<local_path>` | ‣ Looks up file → `file_id`.<br>‣ Fetches size, computes chunk‑count.<br>‣ Downloads each chunk from the **first reachable** replica and reassembles the file locally.                                                 |
| `size`   | `<remote_name>`                | Prints the byte size stored in metadata.                                                                                                                                                                               |
| `delete` | `<remote_name>`                | Deletes the metadata and triggers async replica deletion on every Storage‑Server.                                                                                                                                      |

### 5.3  Behavioural Details

* **Chunk Size** is hard‑coded to **1024 bytes** — adjust in `cli.py` if you need bigger chunks.
* **Partial Failures:**

  * On *upload*, if one replica rejects a chunk the whole command fails (best effort is left for future work).
  * On *read*, the CLI tries replicas in order until one succeeds.
* **Exit Codes:**

  * `0` success.
  * non‑zero → an HTTP error or network failure occurred (already printed to stderr).

### 5.4  Examples

```bash
# Upload big.zip under logical name "backup"
docker compose run --rm cli \
  python /app/cli.py --naming-url http://naming_server:8000 \
  create ./big.zip backup

# Fetch it back
docker compose run --rm cli \
  python /app/cli.py --naming-url http://naming_server:8000 \
  read backup ./big.zip

# Show logical size
docker compose run --rm cli \
  python /app/cli.py --naming-url http://naming_server:8000 \
  size backup

# Remove it entirely
docker compose run --rm cli \
  python /app/cli.py --naming-url http://naming_server:8000 \
  delete backup
```

---

## 6 ‑ REST API (Metadata‑Service)

```
POST   /register_storage              → register node
POST   /files/init                    → create file stub
POST   /files/{file_id}/chunks        → allocate 3 targets for chunk
POST   /files/{file_id}/finalize      → commit size + chunk count
GET    /files/{file_id}/chunks/{i}    → discover where a chunk lives
GET    /files?name=foo.txt            → look up by name
GET    /files/{file_id}/size          → size only
DELETE /files/{file_id}               → purge metadata & replicas
```

Full schema & examples live under `src/naming_server/README.md`.

---

## 7 ‑ Configuration & Environment Vars

| Service         | Variable             | Default                | Purpose                              |
| --------------- | -------------------- | ---------------------- | ------------------------------------ |
| all             | `REPLICATION_FACTOR` | **3**                  | How many distinct nodes per chunk.   |
| naming\_server  | `REDIS_URL`          | `redis://redis:6379/0` | Location of metadata store.          |
| storage\_server | `DATA_DIR`           | `/data`                | On‑disk chunk path inside container. |

Change them via `.env` or inline in `docker-compose.yml`.

---

## 8 ‑ Extending / Roadmap

1. **Health‑checks & Heartbeats** — skip dead nodes automatically.
2. **Pluggable Replication Factor** — per‑file overrides.
3. **Checksum & Repair** — detect / self‑heal corrupted chunks.
4. **Observability** — Prometheus metrics, OpenTelemetry traces.
5. **Redis Cluster** — remove single‑point‑of‑failure.

Contributions welcome — fork & raise a PR! 🔧

---

## 9 ‑ Troubleshooting

| Symptom                                        | Likely Cause             | Fix                                                           |
| ---------------------------------------------- | ------------------------ | ------------------------------------------------------------- |
| `500 "Fewer than 3 storage servers available"` | not enough nodes healthy | Scale replicas: `docker compose up --scale storage_server=5`. |
| Metadata calls hang                            | Redis not reachable      | Check `docker compose ps`; restart Redis.                     |
| Disk usage keeps rising                        | Delete tasks failed      | Run manual GC script in `storage_servers/tools/gc.py`.        |

---

© 2025 Distributed FS Team. MIT License.
