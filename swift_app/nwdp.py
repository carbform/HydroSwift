import os
import json
import time
from pathlib import Path
import pandas as pd
from .nwdp_client import NwdpClient

def nwdp_organizations():
    """Fetch a table of all organizations (states/agencies) available on the NWDP portal."""
    client = NwdpClient()
    orgs = client.get_organizations()
    if not orgs:
        return pd.DataFrame()
    return pd.DataFrame(orgs)[["title", "name"]]

def nwdp_groups():
    """Fetch a table of all groups (themes) available on the NWDP portal."""
    client = NwdpClient()
    groups = client.get_groups()
    if not groups:
        return pd.DataFrame()
    df = pd.DataFrame(groups)
    if "title" in df.columns and "name" in df.columns:
        df = df[["title", "name", "package_count"]]
    return df

def nwdp_datasets(query: str = None, org: str = None, group: str = None):
    """
    Search for NWDP datasets.
    
    Parameters
    ----------
    query : str, optional
        Search term (e.g., 'Ground Water').
    org : str, optional
        Organization ID or title to filter by (e.g., 'karnataka-gw').
    group : str, optional
        Group ID or title to filter by (e.g., 'water-quantity').
        
    Returns
    -------
    pd.DataFrame
        Table of available datasets and their resource_ids.
    """
    client = NwdpClient()
    
    # Try resolving org title to name (fuzzy match)
    if org:
        all_orgs = client.get_organizations()
        matched_orgs = []
        for o in all_orgs:
            title = o.get("title", "").lower()
            name = o.get("name", "").lower()
            query_lower = org.lower()
            if query_lower in title or query_lower in name:
                matched_orgs.append(o.get("name"))
        
        if matched_orgs:
            org = matched_orgs  # Pass list of matched org names
        # if not matched, we just pass the original string
        
    # Try resolving group title to name (fuzzy match)
    if group:
        all_groups = client.get_groups()
        matched_groups = []
        for g in all_groups:
            title = g.get("title", "").lower()
            name = g.get("name", "").lower()
            query_lower = group.lower()
            if query_lower in title or query_lower in name:
                matched_groups.append(g.get("name"))
                
        if matched_groups:
            group = matched_groups

    results = client.search_datasets(query=query, org=org, group=group)
    df = pd.DataFrame(results)
    if not df.empty:
        df[["variable", "resolution"]] = df["dataset_title"].apply(lambda x: pd.Series(_parse_nwdp_title(x)))
        df.attrs["source"] = "nwdp"
    return df

def nwdp_download(resource_id: str = None, query: str = None, org: str = None, group: str = None, filters: dict = None, output_dir: str = "output", format: str = "csv", quiet: bool = False, res_name: str = None, org_name: str = None):
    """
    Downloads data from NWDP CKAN API, either by specific resource_id or by searching.
    If search terms (query, org, group) are provided, it downloads all matching datasets.
    """
    if resource_id:
        # Download single resource
        client = NwdpClient()
        
        safe_res_name = resource_id
        if res_name:
            safe_res_name = "".join([c if c.isalnum() else "_" for c in res_name]).strip("_")
            safe_res_name = " ".join(safe_res_name.split("_")).title().replace(" ", "_")
            
        final_org_name = org_name if org_name else "unknown"
        
        if not quiet:
            if res_name:
                print(f"Downloading: {final_org_name} -> {safe_res_name}")
            else:
                print(f"Downloading NWDP resource: {resource_id}")
                
        records = client.fetch_records(resource_id, filters=filters)
        
        if not records:
            print(f"No records found for resource_id: {resource_id}")
            return None
            
        df = pd.DataFrame(records)
        
        if res_name and org_name:
            out_dir = Path(output_dir) / "nwdp" / final_org_name
        else:
            out_dir = Path(output_dir) / "nwdp"
            
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate time range
        time_range = ""
        date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower() or "monitoring" in c.lower()]
        if date_cols:
            s = pd.to_datetime(df[date_cols[0]], errors="coerce").dropna()
            if not s.empty:
                time_range = f"_{s.min().strftime('%Y%m%d')}_{s.max().strftime('%Y%m%d')}"
                
        out_path = out_dir / f"NWDP_{final_org_name}_{safe_res_name}{time_range}.{format}"
        
        if format.lower() == "csv":
            df.to_csv(out_path, index=False)
        elif format.lower() == "json":
            df.to_json(out_path, orient="records", indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
        if not quiet:
            print(f"Downloaded {len(df)} records to {out_path}")
            
        return df
    else:
        # Search and bulk download
        datasets = nwdp_datasets(query=query, org=org, group=group)
        if datasets.empty:
            if not quiet:
                print("No datasets matched the NWDP search criteria.")
            return None
            
        if not quiet:
            print(f"Found {len(datasets)} NWDP datasets. Starting systematic download...")
            
        client = NwdpClient()
        res_dfs = []
        for _, row in datasets.iterrows():
            rid = row.get("resource_id")
            org_name = row.get("org_id", "unknown_state")
            res_name = row.get("dataset_title", rid)
            
            # Clean filename
            safe_res_name = "".join([c if c.isalnum() else "_" for c in res_name]).strip("_")
            safe_res_name = " ".join(safe_res_name.split("_")).title().replace(" ", "_")
            
            if not quiet:
                print(f"Downloading: {org_name} -> {safe_res_name}")
                
            records = client.fetch_records(rid, filters=filters)
            if not records:
                continue
                
            df = pd.DataFrame(records)
            
            # Organize folder by state/org
            out_dir = Path(output_dir) / "nwdp" / org_name
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # Calculate time range
            time_range = ""
            date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower() or "monitoring" in c.lower()]
            if date_cols:
                s = pd.to_datetime(df[date_cols[0]], errors="coerce").dropna()
                if not s.empty:
                    time_range = f"_{s.min().strftime('%Y%m%d')}_{s.max().strftime('%Y%m%d')}"
                    
            out_path = out_dir / f"NWDP_{org_name}_{safe_res_name}{time_range}.{format}"
            
            if format.lower() == "csv":
                df.to_csv(out_path, index=False)
            elif format.lower() == "json":
                df.to_json(out_path, orient="records", indent=2)
                
            res_dfs.append(df)
            
        if res_dfs:
            return pd.concat(res_dfs, ignore_index=True)
        return None

class _NwdpNamespace:
    """``swift.nwdp`` namespace for NWDP CKAN API operations."""
    
    @staticmethod
    def organizations():
        """List available organizations (e.g., States, Agencies)."""
        return nwdp_organizations()
        
    @staticmethod
    def groups():
        """List available groups/themes (e.g., Water Quality, Climate)."""
        return nwdp_groups()

    @staticmethod
    def datasets(query: str = None, org: str = None, group: str = None):
        """Search datasets and retrieve their resource IDs."""
        return nwdp_datasets(query=query, org=org, group=group)
        
    @staticmethod
    def download(resource_id: str = None, query: str = None, org: str = None, group: str = None, filters: dict = None, output_dir="output", format="csv", quiet=False):
        """Download NWDP datasets by search criteria or resource ID."""
        return nwdp_download(resource_id=resource_id, query=query, org=org, group=group, filters=filters, output_dir=output_dir, format=format, quiet=quiet)
import re

def _parse_nwdp_title(title):
    title = str(title).replace("(", " ").replace(")", " ").replace(",", " ")
    
    # Resolution extraction
    resolution = "Unknown"
    lower_title = title.lower()
    if "hourly" in lower_title:
        resolution = "Hourly"
    elif "daily" in lower_title:
        resolution = "Daily"
    elif "monthly" in lower_title:
        resolution = "Monthly"
    elif "quarterly" in lower_title:
        resolution = "Quarterly"
    elif "yearly" in lower_title or "annual" in lower_title:
        resolution = "Yearly"
        
    # Variable extraction
    var = title
    for kw in ["Telemetry", "Manual", "CWC", "CGWB", "Department", "202"]:
        idx = var.find(kw)
        if idx > 0:
            var = var[:idx]
    
    var = var.strip(" -()[],")
    if "Rainfall" in var: var = "Rainfall"
    if "Ground Water Level" in var: var = "Ground Water Level"
    if "River Water Level" in var or "Surface Water Level" in var: var = "Surface Water Level"
    if "Wind Speed" in var: var = "Wind Speed"
    if "Temperature" in var: var = "Temperature"
    if "Discharge" in var: var = "Discharge"
    
    return var, resolution
