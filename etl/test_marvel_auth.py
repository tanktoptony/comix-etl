import os, time, hashlib, requests
from dotenv import load_dotenv

load_dotenv()

pub = os.getenv("MARVEL_PUBLIC_KEY")
priv = os.getenv("MARVEL_PRIVATE_KEY")

def build_auth():
    ts = str(time.time())
    raw = ts + priv + pub
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return {"ts": ts, "apikey": pub, "hash": h}

def try_request():
    auth = build_auth()

    url = "https://gateway.marvel.com/v1/public/series"
    params = {
        **auth,
        "limit": 1,
        "offset": 0,
        "orderBy": "title",
    }

    # bump timeout from 10 → 30 seconds
    r = requests.get(url, params=params, timeout=30)
    return r

def main():
    # sanity check: do we even have keys loaded?
    print("PUBLIC KEY START:", pub[:4] if pub else None, "(not printing full key)")
    print("PRIVATE KEY START:", priv[:4] if priv else None)

    if not pub or not priv:
        print("⛔ MARVEL_PUBLIC_KEY or MARVEL_PRIVATE_KEY is missing from environment.")
        print("   Make sure .env has them and load_dotenv() runs before imports.")
        return

    # up to 3 tries with small sleep
    last_exc = None
    for attempt in range(1, 4):
        print(f"\nAttempt {attempt}...")
        try:
            r = try_request()
            print("HTTP status:", r.status_code)

            data = r.json()
            print("Message:", data.get("status") or data.get("message"))

            if "data" in data:
                print("Count:", data["data"].get("count"))
                results = data["data"].get("results") or []
                if results:
                    first = results[0]
                    print("First series title:", first.get("title"))
            break

        except requests.exceptions.ReadTimeout:
            print("Timed out waiting for Marvel (ReadTimeout).")
            last_exc = "timeout"
            time.sleep(2)

        except Exception as e:
            print("Other error:", repr(e))
            last_exc = repr(e)
            break

    if last_exc:
        print("\nFinal result:", last_exc)

if __name__ == "__main__":
    main()
