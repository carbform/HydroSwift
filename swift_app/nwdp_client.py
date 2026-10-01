import time
import requests
import json

class NwdpClient:
    """API client for NWDP CKAN DataStore."""

    BASE = "https://nwdp.nwic.gov.in"
    SEARCH_API = f"{BASE}/api/3/action/package_search"
    ORG_API = f"{BASE}/api/3/action/organization_list"
    GROUP_API = f"{BASE}/api/3/action/group_list"
    DATASTORE_API = f"{BASE}/api/3/action/datastore_search"

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False

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

    def search_datasets(self, query: str = None, org: str | list[str] = None, group: str | list[str] = None, limit: int = 1000) -> list[dict]:
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
        
        params = {
            "rows": limit
        }
        if query:
            params["q"] = query
        if fq:
            params["fq"] = " AND ".join(fq)

        try:
            r = self.session.get(self.SEARCH_API, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    packages = data["result"].get("results", [])
                    for pkg in packages:
                        org_title = pkg.get("organization", {}).get("title", "")
                        org_name = pkg.get("organization", {}).get("name", "")
                        for res in pkg.get("resources", []):
                            size = res.get("size")
                            if size is not None and isinstance(size, int) and size <= 300:
                                continue  # Skip empty datasets (likely just headers)
                                
                            results.append({
                                "dataset_title": pkg.get("title"),
                                "organization": org_title,
                                "org_id": org_name,
                                "resource_name": res.get("name"),
                                "resource_id": res.get("id"),
                                "format": res.get("format"),
                                "description": pkg.get("notes", "")[:100] + "..." if pkg.get("notes") else ""
                            })
        except Exception as e:
            print(f"Request failed: {e}")
            
        return results

    def fetch_records(self, resource_id: str, filters: dict = None, limit: int = 10000) -> list[dict]:
        records = []
        offset = 0
        while True:
            params = {
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset
            }
            if filters:
                params["filters"] = json.dumps(filters)
                
            try:
                r = self.session.get(self.DATASTORE_API, params=params, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success"):
                        batch = data["result"].get("records", [])
                        if not batch:
                            break
                        records.extend(batch)
                        offset += len(batch)
                        if len(batch) < limit:
                            break
                    else:
                        print(f"API Error: {data.get('error')}")
                        break
                else:
                    print(f"HTTP {r.status_code}: {r.text[:200]}")
                    break
            except Exception as e:
                print(f"Request failed: {e}")
                break
        return records
