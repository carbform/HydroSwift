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
    
    # Try resolving org title to name
    if org:
        all_orgs = client.get_organizations()
        org_name = org
        for o in all_orgs:
            if o.get("title", "").lower() == org.lower() or o.get("name", "").lower() == org.lower():
                org_name = o.get("name")
                break
        org = org_name
        
    # Try resolving group title to name
    if group:
        all_groups = client.get_groups()
        group_name = group
        for g in all_groups:
            if g.get("title", "").lower() == group.lower() or g.get("name", "").lower() == group.lower():
                group_name = g.get("name")
                break
        group = group_name

    results = client.search_datasets(query=query, org=org, group=group)
    df = pd.DataFrame(results)
    if not df.empty:
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
        
        out_path = out_dir / f"{safe_res_name}.{format}"
        
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
            
            out_path = out_dir / f"{safe_res_name}.{format}"
            
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
