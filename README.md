```
docker compose up
```

- - - - - To test if it works

```
docker compose run cli python /app/cli.py --naming-url http://naming_server:8000 create ./requirements.txt reqs
```

```
docker compose run cli python /app/cli.py --naming-url http://naming_server:8000 read reqs requirements.txt
```

```
docker compose run cli python /app/cli.py --naming-url http://naming_server:8000 size reqs
```

```
docker compose run cli python /app/cli.py --naming-url http://naming_server:8000 delete reqs
```
