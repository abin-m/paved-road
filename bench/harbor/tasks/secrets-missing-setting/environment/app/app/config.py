import os
import pathlib


def read_env(path=".env"):
    values = {}
    p = pathlib.Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def load():
    env = {**read_env(), **os.environ}
    return {"database_url": env["DATABASE_URL"], "api_key": env["API_KEY"]}
