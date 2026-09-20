"""Fetch many Prokerala responses at once, one worker per app.

The free tier's five-requests-per-minute ceiling is counted per app, not per
IP, so five apps give five independent budgets. A single-threaded sweep at the
safe 14-second spacing does about four calls a minute; this does about twenty
three, which turns a two-hour sweep into ten minutes.

Each worker owns one app: its own token, its own spacing clock, its own
backoff. Nothing is shared but the cache directory, and the cache key is the
same one `against_prokerala.fetch` uses, so a job fetched here is free there
and the other way round.

Jobs that fail are returned as exceptions rather than killing the sweep -- a
144-call table is worth keeping even if one cell 500s.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, ".")
from validation.against_prokerala import (  # noqa: E402
    BASE_URL, CACHE, TOKEN_URL, _credentials, _is_quota_error, _is_rate_limit,
)

# Five per sixty seconds per app. Thirteen seconds leaves a little room for
# clock drift between us and their counter.
SECONDS_PER_APP = 13.0
RATE_LIMIT_BACKOFF_SECONDS = 70.0
MAX_ATTEMPTS = 4

_print_lock = threading.Lock()


def _say(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


def cache_path(endpoint: str, params: dict) -> Path:
    import hashlib

    key = hashlib.sha256(
        f"{endpoint}{json.dumps(params, sort_keys=True)}".encode()
    ).hexdigest()[:20]
    return CACHE / f"{endpoint.replace('/', '--')}-{key}.json"


class Worker:
    """One Prokerala app, with its own token and its own minute."""

    def __init__(self, index: int, client_id: str, secret: str):
        self.index = index
        self.client_id = client_id
        self.secret = secret
        self.token_value = ""
        self.token_expiry = 0.0
        self.last_call = 0.0
        self.alive = True
        self.done = 0

    def token(self) -> str:
        if self.token_value and self.token_expiry > time.time() + 60:
            return self.token_value
        response = httpx.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials",
                  "client_id": self.client_id, "client_secret": self.secret},
            timeout=30.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"app #{self.index} token {response.status_code}")
        payload = response.json()
        self.token_value = payload["access_token"]
        self.token_expiry = time.time() + payload["expires_in"]
        return self.token_value

    def get(self, endpoint: str, params: dict) -> dict:
        wait = SECONDS_PER_APP - (time.time() - self.last_call)
        if wait > 0:
            time.sleep(wait)

        attempts = 0
        while True:
            try:
                response = httpx.get(
                    f"{BASE_URL}/{endpoint}", params=params,
                    headers={"Authorization": f"Bearer {self.token()}"},
                    timeout=90.0,
                )
            except httpx.TimeoutException:
                attempts += 1
                if attempts >= MAX_ATTEMPTS:
                    raise
                self.last_call = time.time()
                time.sleep(SECONDS_PER_APP)
                continue
            self.last_call = time.time()
            payload = response.json()
            if payload.get("status") == "ok":
                return payload
            if _is_rate_limit(payload):
                attempts += 1
                if attempts >= MAX_ATTEMPTS:
                    raise RuntimeError(f"app #{self.index} still rate limited")
                _say(f"  app #{self.index} throttled, waiting "
                     f"{RATE_LIMIT_BACKOFF_SECONDS:.0f}s")
                time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                continue
            if _is_quota_error(payload):
                self.alive = False
                raise RuntimeError(f"app #{self.index} out of credits")
            raise RuntimeError(
                f"{endpoint}: {json.dumps(payload.get('errors', payload))[:200]}")


def live_workers() -> list[Worker]:
    """Every configured app whose credentials still authenticate."""
    workers = []
    for index, (client_id, secret) in enumerate(_credentials(), start=1):
        worker = Worker(index, client_id, secret)
        try:
            worker.token()
        except Exception as exc:                        # noqa: BLE001
            _say(f"  app #{index} unusable: {str(exc)[:80]}")
            continue
        workers.append(worker)
    return workers


def run(jobs: list[tuple[str, dict]], label: str = "") -> list[dict | Exception]:
    """Fetch every job, cached ones for free, the rest spread across the apps.

    Results come back in the order the jobs were given. A job that failed
    holds its exception instead of a payload.
    """
    results: list[dict | Exception | None] = [None] * len(jobs)
    pending: queue.Queue[int] = queue.Queue()

    for position, (endpoint, params) in enumerate(jobs):
        path = cache_path(endpoint, params)
        if path.exists():
            results[position] = json.loads(path.read_text(encoding="utf-8"))
        else:
            pending.put(position)

    remaining = pending.qsize()
    cached = len(jobs) - remaining
    if remaining == 0:
        _say(f"{label}: all {len(jobs)} responses already cached")
        return results                                   # type: ignore[return-value]

    workers = live_workers()
    if not workers:
        raise SystemExit("no usable Prokerala apps")

    minutes = remaining * SECONDS_PER_APP / len(workers) / 60
    _say(f"{label}: {cached} cached, {remaining} to fetch across "
         f"{len(workers)} apps (~{minutes:.0f} min, "
         f"{remaining * 50} credits)")

    CACHE.mkdir(parents=True, exist_ok=True)
    started = time.time()

    def drain(worker: Worker) -> None:
        while worker.alive:
            try:
                position = pending.get_nowait()
            except queue.Empty:
                return
            endpoint, params = jobs[position]
            try:
                payload = worker.get(endpoint, params)
            except Exception as exc:                     # noqa: BLE001
                results[position] = exc
                if not worker.alive:
                    # Its credits ran out mid-job; someone else should retry.
                    results[position] = None
                    pending.put(position)
                    _say(f"  app #{worker.index} exhausted, "
                         f"{pending.qsize()} jobs left")
                    return
                _say(f"  {endpoint} failed: {str(exc)[:100]}")
                continue
            cache_path(endpoint, params).write_text(
                json.dumps(payload), encoding="utf-8")
            results[position] = payload
            worker.done += 1
            finished = sum(r is not None for r in results)
            if finished % 10 == 0 or finished == len(jobs):
                rate = (finished - cached) / max(time.time() - started, 1) * 60
                _say(f"  {finished}/{len(jobs)} ({rate:.0f}/min)")

    # An app that runs out mid-sweep re-queues its job and stops, which can
    # strand work if the other threads have already drained the queue. So keep
    # starting rounds until either nothing is left or nobody can still fetch.
    while not pending.empty() and any(w.alive for w in workers):
        threads = [threading.Thread(target=drain, args=(w,), daemon=True)
                   for w in workers if w.alive]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    leftover = [i for i, r in enumerate(results) if r is None]
    for position in leftover:
        results[position] = RuntimeError("no app had credits left")

    spent = sum(w.done for w in workers)
    _say(f"{label}: done in {(time.time() - started) / 60:.1f} min, "
         f"{spent} calls, {spent * 50} credits, "
         f"{sum(isinstance(r, Exception) for r in results)} failed")
    return results                                       # type: ignore[return-value]
