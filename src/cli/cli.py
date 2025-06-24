import argparse
import os
import requests

def create(args):
    # Read file, split into chunks
    size = os.path.getsize(args.local_path)
    chunk_size = 1024
    chunk_count = (size + chunk_size - 1) // chunk_size
    # Init file
    resp = requests.post(f"{args.naming_url}/files/init", json={"file_name": args.remote_name})
    resp.raise_for_status()
    file_id = resp.json()['file_id']
    # Upload chunks
    with open(args.local_path, 'rb') as f:
        for idx in range(chunk_count):
            data = f.read(chunk_size)
            # allocate
            resp = requests.post(f"{args.naming_url}/files/{file_id}/chunks", params={"chunk_index": idx})
            resp.raise_for_status()
            servers = resp.json()['storage_servers']
            for srv in servers:
                url = f"http://{srv['host']}:{srv['port']}/chunks/{file_id}_{idx}"
                r2 = requests.post(url, files={'chunk': data})
                r2.raise_for_status()
    # finalize
    resp = requests.post(f"{args.naming_url}/files/{file_id}/finalize", json={"size": size, "chunk_count": chunk_count})
    resp.raise_for_status()
    print(f"Created remote file {args.remote_name} with ID {file_id}")

def read(args):
    # Lookup file
    resp = requests.get(f"{args.naming_url}/files", params={"name": args.remote_name})
    resp.raise_for_status()
    file_id = resp.json()['file_id']
    # Get metadata
    resp2 = requests.get(f"{args.naming_url}/files/{file_id}/size")
    resp2.raise_for_status()
    size = resp2.json()['size']
    chunk_size = 1024
    chunk_count = (size + chunk_size - 1) // chunk_size
    # Download chunks
    with open(args.local_path, 'wb') as f:
        for idx in range(chunk_count):
            resp = requests.get(f"{args.naming_url}/files/{file_id}/chunks/{idx}")
            resp.raise_for_status()
            servers = resp.json()['storage_servers']
            data = None
            for srv in servers:
                try:
                    r2 = requests.get(f"http://{srv['host']}:{srv['port']}/chunks/{file_id}_{idx}")
                    if r2.status_code == 200:
                        data = r2.content
                        break
                except:
                    continue
            if data is None:
                print(f"Failed to retrieve chunk {idx}")
                return
            f.write(data)
    print(f"Downloaded to {args.local_path}")

def delete(args):
    resp = requests.get(f"{args.naming_url}/files", params={"name": args.remote_name})
    if resp.status_code != 200:
        print("Remote file not found")
        return
    file_id = resp.json()['file_id']
    resp = requests.delete(f"{args.naming_url}/files/{file_id}")
    resp.raise_for_status()
    print(f"Deleted remote file {args.remote_name}")

def size(args):
    resp = requests.get(f"{args.naming_url}/files", params={"name": args.remote_name})
    resp.raise_for_status()
    file_id = resp.json()['file_id']
    resp2 = requests.get(f"{args.naming_url}/files/{file_id}/size")
    resp2.raise_for_status()
    print(f"Size: {resp2.json()['size']} bytes")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--naming-url', required=True)
    sub = parser.add_subparsers(dest='cmd')
    p1 = sub.add_parser('create'); p1.add_argument('local_path'); p1.add_argument('remote_name')
    p2 = sub.add_parser('read'); p2.add_argument('remote_name'); p2.add_argument('local_path')
    p3 = sub.add_parser('delete'); p3.add_argument('remote_name')
    p4 = sub.add_parser('size'); p4.add_argument('remote_name')
    args = parser.parse_args()
    if args.cmd == 'create': create(args)
    elif args.cmd == 'read': read(args)
    elif args.cmd == 'delete': delete(args)
    elif args.cmd == 'size': size(args)
    else: parser.print_help()