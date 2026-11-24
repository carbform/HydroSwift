import time
import requests
import json
from typing import Optional

class NwdpClient:
    """API client for NWDP CKAN DataStore."""

    BASE = "https://nwdp.nwic.gov.in"
    SEARCH_API = f"{BASE}/api/3/action/package_search"
    ORG_API = f"{BASE}/api/3/action/organization_list"
    GROUP_API = f"{BASE}/api/3/action/group_list"
    DATASTORE_API = f"{BASE}/api/3/action/datastore_search"

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # NWDP certificate chain is not trusted by default; recorded in manifests
        self.verify_tls = False
        self.last_search = None
        self.last_fetch = None

    def get_organizations(self) -> list[dict]:
        try:
            # First get all IDs/names
            r = self.session.get(self.ORG_API, params={"limit": 1000}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    names = data.get("result", [])
                    return [{"name": name, "title": name.replace("-", " ").title()} for name in names]
        except Exception as e:
            print(f"Request failed: {e}")
        return []

    def get_groups(self) -> list[dict]:
        try:
            r = self.session.get(self.GROUP_API, params={"all_fields": "true"}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("result", [])
        except Exception as e:
            print(f"Request failed: {e}")
        return []

    def search_datasets(self, query: str = None, org: str | list[str] = None, group: str | list[str] = None, limit: int = 1000, max_pages: int = 50) -> list[dict]:
        """Search CKAN packages, paging until every reported package is read.

        Outcome of the call (errors, server-reported count, rows dropped) is
        left in ``self.last_search`` so callers can surface it instead of
        mistaking a failure for "no data".
        """
        results = []
        fq = []

        if org:
            if isinstance(org, str):
                org = [org]
            org_queries = [f"organization:{o}" for o in org]
            fq.append("(" + " OR ".join(org_queries) + ")")

        if group:
            if isinstance(group, str):
                group = [group]
            group_queries = [f"groups:{g}" for g in group]
            fq.append("(" + " OR ".join(group_queries) + ")")

        base_params = {"rows": limit}
        if query:
            base_params["q"] = query
        if fq:
            base_params["fq"] = " AND ".join(fq)

        status = {
            "endpoint": self.SEARCH_API,
            "params": dict(base_params),
            "ok": True,
            "error": None,
            "packages_reported": None,
            "packages_read": 0,
            "resources_dropped_small": 0,
            "complete": True,
        }
        start = 0
        try:
            for _ in range(max_pages):
                params = dict(base_params, start=start)
                r = self.session.get(self.SEARCH_API, params=params, timeout=30)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                if not data.get("success"):
                    raise RuntimeError(f"CKAN error: {data.get('error')}")
                result = data["result"]
                status["packages_reported"] = result.get("count")
                packages = result.get("results", [])
                for pkg in packages:
                    org_title = (pkg.get("organization") or {}).get("title", "")
                    org_name = (pkg.get("organization") or {}).get("name", "")
                    for res in pkg.get("resources", []):
                        size = res.get("size")
                        if size is not None and isinstance(size, int) and size <= 300:
                            status["resources_dropped_small"] += 1
                            continue  # header-only / empty resource
                        results.append({
                            "dataset_title": pkg.get("title"),
                            "organization": org_title,
                            "org_id": org_name,
                            "resource_name": res.get("name"),
                            "resource_id": res.get("id"),
                            "format": res.get("format"),
                            "description": pkg.get("notes", "")[:100] + "..." if pkg.get("notes") else "",
                            "dataset_url": f"{self.BASE}/dataset/{pkg.get('name')}" if pkg.get("name") else "",
                        })
                status["packages_read"] += len(packages)
                start += len(packages)
                reported = status["packages_reported"]
                if not packages or reported is None or start >= reported:
                    break
            reported = status["packages_reported"]
            if reported is not None and status["packages_read"] < reported:
                status["complete"] = False
                status["error"] = (
                    f"truncated: read {status['packages_read']} of {reported} packages"
                )
        except Exception as e:
            status["ok"] = False
            status["complete"] = False
            status["error"] = str(e)
        self.last_search = status
        return results

    def count_records(self, resource_id: str) -> Optional[int]:
        """Total records in a resource from one cheap request (limit=0); None if unavailable."""
        try:
            r = self.session.get(self.DATASTORE_API, params={"resource_id": resource_id, "limit": 0}, timeout=30)
            if r.status_code == 200 and r.json().get("success"):
                return r.json()["result"].get("total")
        except Exception:
            pass
        return None

    def fetch_records(self, resource_id: str, filters: dict = None, limit: int = 10000,
                      progress=None, cancel=None) -> list[dict]:
        """Fetch every DataStore record; outcome is left in ``self.last_fetch``.

        ``progress(read, total)`` is called after each page; if the
        ``cancel`` event is set the loop stops and the result is marked incomplete.
        """
        records = []
        offset = 0
        status = {
            "endpoint": self.DATASTORE_API,
            "resource_id": resource_id,
            "ok": True,
            "error": None,
            "records_reported": None,
            "records_read": 0,
            "complete": True,
        }
        try:
            while True:
                params = {"resource_id": resource_id, "limit": limit, "offset": offset}
                if filters:
                    params["filters"] = json.dumps(filters)
                r = self.session.get(self.DATASTORE_API, params=params, timeout=30)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                data = r.json()
                if not data.get("success"):
                    raise RuntimeError(f"API error: {data.get('error')}")
                result = data["result"]
                if result.get("total") is not None:
                    status["records_reported"] = result["total"]
                batch = result.get("records", [])
                if not batch:
                    break
                records.extend(batch)
                offset += len(batch)
                if progress:
                    progress(len(records), status["records_reported"])
                if cancel is not None and cancel.is_set():
                    status["cancelled"] = True
                    raise RuntimeError("cancelled by user")
                if len(batch) < limit:
                    break
        except Exception as e:
            status["ok"] = False
            status["complete"] = False
            status["error"] = str(e)
        status["records_read"] = len(records)
        rep = status["records_reported"]
        if status["ok"] and rep is not None and len(records) < rep:
            status["complete"] = False
            status["error"] = f"truncated: read {len(records)} of {rep} records"
        self.last_fetch = status
        return records
