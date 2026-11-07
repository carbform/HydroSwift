"""Names removed from the public API, with where to go instead."""

REMOVED = {
    "wris": "WRIS access was merged into NWDP. Use hydroswift.search(...) then hydroswift.fetch(...).",
    "cwc": "Use hydroswift.search(..., sources=['CWC'], basin=/state=/ids=) then hydroswift.fetch(...). Reservoirs: hydroswift.rsms.",
    "nwdp": "Use hydroswift.search(..., sources=['NWDP']) then hydroswift.fetch(...).",
    "get_wris_data": "Use hydroswift.search(...) then hydroswift.fetch(...).",
    "get_cwc_data": "Use hydroswift.search(..., sources=['CWC']) then hydroswift.fetch(...).",
    "merge_only": "Use hydroswift.merge(run, 'out.parquet'|'out.csv'|'out.gpkg').",
    "plot_only": "Use hydroswift.plot(run, 'plots/').",
    "swot_merge": "Removed with the WRIS/CWC folder layout it depended on. Use hydroswift.load(...) and hydroswift.merge(...); reservoirs: hydroswift.swot_reservoir_merge.",
    "datasets": "Variable names: see hydroswift.tidy.VARIABLES.",
    "basins": "Use hydroswift.search(..., basin='Krishna') for CWC.",
}




def make_getattr(module_name):
    def __getattr__(name: str):
        if name in REMOVED:
            raise AttributeError(f"`{name}` has been removed. {REMOVED[name]}")
        raise AttributeError(f"module '{module_name}' has no attribute {name!r}")
    return __getattr__
