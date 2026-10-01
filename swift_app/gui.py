import sys
import os
from pathlib import Path

def launch_gui():
    try:
        import streamlit
    except ImportError:
        print("Streamlit is not installed. Please install it using 'pip install streamlit'.")
        return 1
        
    app_path = Path(__file__).parent.parent / "app.py"
    if not app_path.exists():
        print(f"Error: Could not find {app_path}")
        return 1
        
    # Use os.system to launch streamlit
    print("Launching HydroSwift GUI...")
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.system(f"{sys.executable} -m streamlit run {app_path}")
    return 0
