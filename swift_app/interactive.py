import sys
from .cli import WRIS_BASINS

def prompt(question, default=""):
    """Simple prompt helper."""
    prompt_str = f"{question} [{default}]: " if default else f"{question}: "
    val = input(prompt_str).strip()
    return val if val else default

def run_interactive(args):
    print("\n" + "="*50)
    print(" Welcome to HydroSwift Interactive Mode!")
    print("="*50 + "\n")
    
    print("Select a data source:")
    print("  [1] NWDP (State/Theme-wise Data Portal)")
    print("  [2] WRIS (Basin-wise Hydrological Data)")
    print("  [3] CWC (Flood Forecasting Stations)")
    print("  [4] Exit")
    
    choice = prompt("Enter your choice (1-4)", "1")
    
    if choice == "4":
        print("Goodbye!")
        sys.exit(0)
        
    elif choice == "1":
        print("\n--- NWDP Data Download ---")
        state = prompt("Enter State or Organization name (e.g., Karnataka GW)")
        query = prompt("Enter search query (e.g., Ground Water, or leave empty)")
        if not state and not query:
            print("Error: You must provide at least a state or a query.")
            return 1
            
        from .nwdp import nwdp_download
        nwdp_download(
            query=query if query else None,
            org=state if state else None,
            output_dir=args.output_dir,
            quiet=args.quiet
        )
        print("\nDownload complete! Check your output directory.")
        return 0
        
    elif choice == "2":
        print("\n--- WRIS Data Download ---")
        print("Available Basins:")
        for num, name in WRIS_BASINS.items():
            print(f"  [{num}] {name}")
            
        basin_num = prompt("Select Basin number (1-17)")
        if basin_num not in WRIS_BASINS:
            print("Invalid basin number.")
            return 1
            
        args.basin = basin_num
        
        print("\nAvailable Variables:")
        print("  [1] Discharge (q)")
        print("  [2] Water Level (wl)")
        print("  [3] Rainfall (rf)")
        print("  [4] All of the above")
        
        var_choice = prompt("Select variable (1-4)", "4")
        if "1" in var_choice or var_choice == "4": args.q = True
        if "2" in var_choice or var_choice == "4": args.wl = True
        if "3" in var_choice or var_choice == "4": args.rf = True
        
        args.merge = prompt("Merge into GeoPackage? (y/n)", "y").lower() == "y"
        
        from .wris import run_wris_download
        print(f"\nStarting WRIS download for {WRIS_BASINS[basin_num]}...")
        
        from .wris_client import WrisClient
        client = WrisClient(delay=args.delay)
        if not client.check_api():
            return 1
        basin_code = client.get_basin_code(WRIS_BASINS[basin_num])
        
        from .cli import DATASETS
        selected = {k: v for k, v in DATASETS.items() if getattr(args, k, False)}
        
        return run_wris_download(args, selected, client, basin_code)
        
    elif choice == "3":
        print("\n--- CWC Data Download ---")
        basin = prompt("Enter CWC Basin name (e.g., Godavari, Krishna)")
        if not basin:
            print("Basin name required.")
            return 1
            
        args.cwc_basin_filter = [basin]
        args.cwc = True
        
        from .cwc import run_cwc_download
        print(f"\nStarting CWC download for {basin}...")
        return run_cwc_download(args)
        
    else:
        print("Invalid choice.")
        return 1
