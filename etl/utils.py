# in etl/utils.py
import os
import time
import hashlib

class DummyLog:
    def info(self, msg, *args): print("INFO:", msg % args if args else msg)
    def warning(self, msg, *args): print("WARNING:", msg % args if args else msg)
    def error(self, msg, *args): print("ERROR:", msg % args if args else msg)

log = DummyLog()

def marvel_auth_params():
    ts = str(time.time())
    public_key = os.getenv("MARVEL_PUBLIC_KEY")
    private_key = os.getenv("MARVEL_PRIVATE_KEY")

    if not public_key or not private_key:
        raise RuntimeError("Missing MARVEL_PUBLIC_KEY or MARVEL_PRIVATE_KEY in env")

    m = hashlib.md5()
    m.update((ts + private_key + public_key).encode("utf-8"))
    digest = m.hexdigest()

    return {
        "ts": ts,
        "apikey": public_key,
        "hash": digest,
    }
