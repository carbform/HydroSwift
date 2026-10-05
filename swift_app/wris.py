import warnings
import pandas as pd

warnings.warn(
    "hydroswift.wris is deprecated and has been merged with NWDP. "
    "Please use the unified hydroswift.search() and hydroswift.fetch() API instead.",
    DeprecationWarning,
    stacklevel=2
)

def variables():
    """Legacy WRIS variables mapping."""
    return ["rainfall", "water_level", "discharge", "temperature", "humidity", "solar", "atm_pressure", "sediment", "groundwater"]

def basins(variable=None):
    """Legacy WRIS basins method. Now just redirects to Unified Search for all locations."""
    warnings.warn("WRIS basins() is deprecated. Please use hydroswift.search(location='...') instead.", DeprecationWarning, stacklevel=2)
    return pd.DataFrame()

def stations(basin, variable=None):
    """Legacy WRIS stations method. Now routes to unified search."""
    from .api import search
    return search(query=variable, location=basin)

def download(basin=None, variables=None, output_dir="output", format="csv", overwrite=False, merge=False, plot=False, quiet=False):
    """
    Legacy WRIS downloader. 
    Routes to the new Unified API using NWDP and CWC backends.
    """
    from .api import search, fetch
    if variables is None:
        variables = ["Rainfall"]
    if isinstance(variables, str):
        variables = [variables]
        
    for var in variables:
        df = search(query=var, location=basin)
        if df is not None and not df.empty:
            fetch(df, output_dir=output_dir, format=format, overwrite=overwrite, plot=plot, quiet=quiet)

def build_metadata(meta_dict, dataset=None, source="WRIS"):
    """Legacy metadata builder for CWC module compatibility."""
    res = {}
    for k, v in meta_dict.items():
        res[k] = str(v)
    return res
