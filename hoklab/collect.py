"""Rate-limited collector for public Tencent aggregates and authorized camp data."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "https://prod.comp.smoba.qq.com/leaguesite"

def now():
    return datetime.now(timezone.utc).isoformat()

def fetch(key, url, *, refresh=False, payload=None, headers=None):
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{key}.json"
    meta_path = RAW / f"{key}.meta.json"
    if path.exists() and meta_path.exists() and not refresh:
        body = path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if hashlib.sha256(body).hexdigest() != meta["sha256"]:
            raise ValueError(f"Raw snapshot hash mismatch: {key}")
        return json.loads(body), meta
    req_headers = {"User-Agent": "HoK-MetaLab/1.0 academic-research", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = json.dumps(payload).encode() if payload is not None else None
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=req_headers), timeout=25) as r:
                body = r.read()
                status = r.status
            obj = json.loads(body)
            if isinstance(obj, dict) and obj.get("code", 200) not in (0, 200):
                raise ValueError(f"Upstream code {obj.get('code')}")
            if isinstance(obj, dict) and obj.get("returnCode", 0) != 0:
                raise PermissionError(f"Upstream rejected request: {obj.get('returnCode')}")
            meta = {"key": key, "url": url, "retrieved_at": now(), "sha256": hashlib.sha256(body).hexdigest(), "http_status": status, "request_body": payload, "bytes": len(body), "provider": "Tencent public aggregate" if "prod.comp" in url or "pvp.qq" in url else "Tencent camp authorized aggregate"}
            # Preserve refresh history; the top-level file is the latest pointer.
            archive = RAW / "archive" / key
            archive.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            version = f"{stamp}_{meta['sha256'][:12]}"
            (archive / f"{version}.json").write_bytes(body)
            (archive / f"{version}.meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(body)
            tmp.replace(path)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(0.6)
            return obj, meta
        except (urllib.error.HTTPError, PermissionError) as exc:
            if isinstance(exc, PermissionError) or exc.code in (401, 403):
                raise
            last_error = exc
        except (OSError, ValueError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{key}: {last_error}")

def collect(refresh=False, since=2019, camp=False):
    statuses = []
    heroes, _ = fetch("heroes", "https://pvp.qq.com/web201605/js/herolist.json", refresh=refresh)
    catalog, _ = fetch("leagues", f"{BASE}/leagues/open", refresh=refresh)
    leagues = catalog.get("results", [])
    if not isinstance(leagues, list) or not leagues:
        raise ValueError("Empty league catalog")
    for league in leagues:
        if int(league["year"]) < since:
            continue
        league_id = str(league["league_id"])
        try:
            obj, meta = fetch(f"league_{league_id}", f"{BASE}/league/hero/settle_list/open?league_id={league_id}", refresh=refresh)
            rows = obj.get("data", [])
            if not isinstance(rows, list):
                raise ValueError("hero data must be an array")
            statuses.append({"id": league_id, "name": league["league_name"], "status": "ok" if rows else "empty", "rows": len(rows), "retrieved_at": meta["retrieved_at"]})
            print(f"{league_id}: {len(rows)} hero observations", flush=True)
        except Exception as exc:
            statuses.append({"id": league_id, "name": league["league_name"], "status": "failed", "error": str(exc)})
            print(f"{league_id}: failed ({type(exc).__name__})", flush=True)
            if isinstance(exc, PermissionError) or isinstance(exc, urllib.error.HTTPError) and exc.code in (401,403):
                raise
    if camp:
        auth = os.environ.get("HOK_CAMP_HEADERS_JSON")
        if not auth:
            auth_file = Path(os.environ.get("HOK_CAMP_HEADERS_FILE", str(ROOT / "private/camp_headers.json")))
            if auth_file.is_file():
                auth = auth_file.read_text(encoding="utf-8-sig")
        if not auth:
            raise PermissionError("Configure local camp headers first; use only your authorized account headers")
        auth_headers = json.loads(auth)
        if not isinstance(auth_headers, dict) or not auth_headers or any(not isinstance(k,str) or not isinstance(v,str) or '\r' in k+v or '\n' in k+v for k,v in auth_headers.items()):
            raise ValueError("Invalid authorized headers; values are not logged")
        auth_headers = {k:v for k,v in auth_headers.items() if not k.startswith(':') and k.lower() not in ('host','content-length','connection','accept-encoding')}
        for segment, name in [(1, "all"), (3, "peak1350"), (4, "top")]:
            payload = {"bottomTab": "", "rankId": 0, "segment": segment, "position": 0, "recommendPrivacy": 0}
            obj, meta = fetch(f"camp_{name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}", "https://kohcamp.qq.com/hero/getdetailranklistbyid", refresh=refresh, payload=payload, headers=auth_headers)
            if not obj.get("data", {}).get("list"):
                raise ValueError(f"Empty camp response: {name}")
            statuses.append({"id": f"camp_{name}", "status": "ok", "rows": len(obj["data"]["list"])})
    (ROOT / "data" / "collection_status.json").write_text(json.dumps({"collected_at": now(), "leagues": statuses, "camp": "authorized snapshots present" if list(RAW.glob('camp_*.json')) else "missing_authorization", "notes": "No historic rank snapshots were invented. API is an aggregate, not individual matches."}, ensure_ascii=False, indent=2), encoding="utf-8")
    return statuses

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refresh all public snapshots; default uses validated cache")
    parser.add_argument("--since", type=int, default=2019)
    parser.add_argument("--camp", action="store_true", help="Collect current rank strata with user-provided authorized headers")
    args = parser.parse_args()
    collect(args.refresh, args.since, args.camp)
