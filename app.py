import streamlit as st
import pandas as pd
import hydroswift
from hydroswift.cli import WRIS_BASINS

st.set_page_config(page_title="HydroSwift GUI", page_icon="🌊", layout="wide")

st.title("🌊 HydroSwift")
st.markdown("Fast, unified workflows for hydrological data from **CWC**, **WRIS**, and **NWDP**.")

st.sidebar.header("Data Source")
source = st.sidebar.radio("Select Source", ["NWDP (State/Theme)", "WRIS (Basin)", "CWC (Stations)"])

output_dir = st.sidebar.text_input("Output Directory", "output")
quiet = st.sidebar.checkbox("Quiet Mode", value=False)

if source == "NWDP (State/Theme)":
    st.header("NWDP Data Download")
    
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("Search Query", placeholder="e.g. Ground Water")
    with col2:
        org = st.text_input("State / Organization", placeholder="e.g. Karnataka GW")
        
    if st.button("Search NWDP"):
        if not query and not org:
            st.warning("Please provide a query or state.")
        else:
            with st.spinner("Searching..."):
                df = hydroswift.nwdp.datasets(query=query if query else None, org=org if org else None)
                if df.empty:
                    st.info("No datasets found.")
                else:
                    st.success(f"Found {len(df)} datasets!")
                    st.dataframe(df)
                    st.session_state["nwdp_df"] = df
                    
    if "nwdp_df" in st.session_state and not st.session_state["nwdp_df"].empty:
        if st.button("Download All Matching NWDP Data"):
            with st.spinner("Downloading..."):
                hydroswift.nwdp.download(query=query if query else None, org=org if org else None, output_dir=output_dir, quiet=quiet)
            st.success(f"Downloaded to `{output_dir}/nwdp/`")

elif source == "WRIS (Basin)":
    st.header("WRIS Data Download")
    
    basin_name = st.selectbox("Select Basin", list(WRIS_BASINS.values()))
    
    st.subheader("Variables")
    col1, col2, col3 = st.columns(3)
    with col1:
        q = st.checkbox("Discharge (q)", value=True)
    with col2:
        wl = st.checkbox("Water Level (wl)", value=True)
    with col3:
        rf = st.checkbox("Rainfall (rf)", value=True)
        
    merge = st.checkbox("Merge into GeoPackage?", value=True)
    
    if st.button("Download WRIS Data"):
        with st.spinner(f"Downloading WRIS data for {basin_name}..."):
            # We construct fake args since run_wris_download expects an argparse Namespace
            class Args:
                pass
            args = Args()
            args.basin = str(list(WRIS_BASINS.keys())[list(WRIS_BASINS.values()).index(basin_name)])
            args.q = q
            args.wl = wl
            args.rf = rf
            args.temp = args.rh = args.solar = args.sed = args.gwl = args.atm = False
            args.merge = merge
            args.output_dir = output_dir
            args.quiet = quiet
            args.delay = 0.25
            args.start_date = "1950-01-01"
            import time
            args.end_date = time.strftime("%Y-%m-%d")
            
            from hydroswift.cli import DATASETS
            selected = {k: v for k, v in DATASETS.items() if getattr(args, k, False)}
            
            from hydroswift.wris_client import WrisClient
            client = WrisClient(delay=args.delay)
            if client.check_api():
                basin_code = client.get_basin_code(basin_name)
                from hydroswift.wris import run_wris_download
                run_wris_download(args, selected, client, basin_code)
                st.success(f"Downloaded WRIS data for {basin_name} to `{output_dir}/`")
            else:
                st.error("WRIS API is currently down.")

elif source == "CWC (Stations)":
    st.header("CWC Data Download")
    cwc_basin = st.text_input("CWC Basin Filter", placeholder="e.g. Godavari")
    
    if st.button("Download CWC Data"):
        if not cwc_basin:
            st.warning("Please enter a basin filter.")
        else:
            with st.spinner(f"Downloading CWC data for {cwc_basin}..."):
                class Args:
                    pass
                args = Args()
                args.cwc = True
                args.cwc_basin_filter = [cwc_basin]
                args.cwc_station = None
                args.output_dir = output_dir
                args.quiet = quiet
                args.overwrite = False
                args.merge = True
                args.cwc_refresh = False
                args.cwc_rc_discharge = True
                args.metadata = False
                
                from hydroswift.cwc import run_cwc_download
                run_cwc_download(args)
                st.success(f"Downloaded CWC data to `{output_dir}/`")

