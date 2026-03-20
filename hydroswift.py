"""
HydroSwift legacy launcher for the modular HydroSwift package.

Allows execution without installation:

    python -m hydroswift -b Krishna -q
"""

from swift_app import APP_NAME, APP_ORG, __version__, __codename__
from swift_app.main import main


if __name__ == "__main__":

    try:

        raise SystemExit(main())

    except KeyboardInterrupt:

        print("\n\nExecution interrupted by user.")
        raise SystemExit(130)

    except Exception as exc:

        print("\nERROR: HydroSwift encountered an unexpected issue.")
        print("Reason:", str(exc))
        print("Try running again or check network/API status.")

        raise SystemExit(1)


