## Distributed Storage Metadata-Service — API Documentation

# Storage Server

This is the **Storage Server** component of the distributed chunk storage system.

---

## Architecture

The Storage Server is responsible for:

- Receiving and storing file chunks sent by clients or the Naming Server.
- Serving stored chunks on request.
- Deleting chunks upon command.

Chunks are stored locally in a directory on disk inside the container.

---

## Running the Storage Server

The server listens on port **5001** by default.

You can run it via Docker:

```bash
docker build -t storage-server .
docker run -p 5001:5001 storage-server

## Endpoints

| Endpoint             | Method | Description                          |
| -------------------- | ------ | ------------------------------------ |
| `/chunks/{chunk_id}` | POST   | Upload a chunk (multipart/form-data) |
| `/chunks/{chunk_id}` | GET    | Download a chunk (binary stream)     |
| `/chunks/{chunk_id}` | DELETE | Delete a chunk                       |


