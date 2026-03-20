"""Run SWIFT app package as: python -m swift_app"""

from .main import main


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