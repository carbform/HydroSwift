"""HydroSwift command line: search -> get -> show / merge / plot.

    hyswift search rainfall --where Karnataka --period 2020:2022 --save cat.json
    hyswift get --from cat.json --rows 1,3 --period 2020:2022 --out output
    hyswift show output            # tidy summary of what was fetched
    hyswift merge output all.parquet
    hyswift plot output plots/
    hyswift                        # guided prompts
"""

from __future__ import annotations

import argparse
import time

from . import APP_NAME, APP_TAGLINE, VERSION


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hyswift",
        description=f"{APP_NAME} - {APP_TAGLINE}\n\nWorkflow: search -> get -> show / merge / plot (run `hyswift` alone for guided mode).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"HydroSwift {VERSION}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("search", help="Find datasets/stations across sources")
    s.add_argument("query", nargs="?", help="variable or keyword, e.g. rainfall, discharge")
    s.add_argument("--where", dest="location", help="substring of organization/basin/state/district/river")
    s.add_argument("--basin", help="exact CWC basin name")
    s.add_argument("--state", help="exact CWC state name")
    s.add_argument("--ids", help="comma-separated catalog IDs (exact)")
    s.add_argument("--source", action="append", dest="sources", choices=["NWDP", "CWC", "CWC-RSMS"],
                   help="restrict to a source (repeatable)")
    s.add_argument("--period", help="YYYY:YYYY or YYYY-MM-DD:YYYY-MM-DD")
    s.add_argument("--estimate", action="store_true", help="add record counts (NWDP only; one request per row)")
    s.add_argument("--save", help="write the catalog + provenance to this JSON file")
    s.add_argument("--limit", type=int, default=40, help="rows to print (default 40)")

    g = sub.add_parser("get", help="Download rows of a saved catalog")
    g.add_argument("--from", dest="catalog", required=True, help="catalog JSON from `search --save`")
    g.add_argument("--rows", help="row numbers to download, e.g. 0,2,5 (default: all)")
    g.add_argument("--period", help="YYYY:YYYY or YYYY-MM-DD:YYYY-MM-DD")
    g.add_argument("--out", default="output", help="output directory")
    g.add_argument("--format", choices=["csv", "xlsx", "json"], default="csv")
    g.add_argument("--overwrite", action="store_true")
    g.add_argument("--no-rc-discharge", action="store_true", help="CWC: stage only, no rating-curve discharge")

    sh = sub.add_parser("show", help="Summarise fetched data (tidy view)")
    sh.add_argument("path", help="output directory or manifest*.json")

    m = sub.add_parser("merge", help="Merge fetched data into one csv/parquet/gpkg")
    m.add_argument("path")
    m.add_argument("output")

    pl = sub.add_parser("plot", help="Plot fetched data")
    pl.add_argument("path")
    pl.add_argument("output_dir", nargs="?", default="output/plots")
    pl.add_argument("--variable")

    r = sub.add_parser("rsms", help="CWC reservoir tools (RSMS)")
    rs = r.add_subparsers(dest="rsms_command", required=True)
    d = rs.add_parser("daily", help="Latest-day storage snapshot for all monitored reservoirs")
    d.add_argument("--out", default="output/cwc_rsms/daily_snapshot.csv", help="CSV to create or append to")
    b = rs.add_parser("backfill", help="Download and parse historical weekly bulletins")
    b.add_argument("--start", default="2025-05-15")
    b.add_argument("--end")
    b.add_argument("--out", default="output/cwc_rsms/bulletin_backfill.csv")
    b.add_argument("--bulletin-dir", default="output/cwc_rsms/bulletins")
    bd = rs.add_parser("build", help="Build unified SWOT + in-situ reservoir database")
    bd.add_argument("--reservoir-shp", required=True)
    bd.add_argument("--swot-db", required=True)
    bd.add_argument("--gauge-cache", required=True)
    bd.add_argument("--out-dir", default="output/reservoir_geodb")

    sub.add_parser("cite", help="Show citation")
    sub.add_parser("coffee", help="Take a coffee break")
    return p


def _print_catalog(df, limit):
    import pandas as pd
    cols = ["Source", "Title", "Location", "Variable", "Resolution", "CoverageStart", "CoverageEnd", "ID"]
    cols += [c for c in ("EstRecords",) if c in df.columns]
    with pd.option_context("display.width", 200, "display.max_colwidth", 48):
        print(df[cols].head(limit).to_string())
    if len(df) > limit:
        print(f"... {len(df) - limit} more rows (use --save to keep all)")


def print_status(df):
    for st in df.attrs.get("source_status", []):
        bits = []
        if not st["ok"]:
            bits.append(f"FAILED: {st['error']}")
        elif not st["complete"]:
            bits.append(f"PARTIAL: {st['error']}")
        else:
            bits.append(f"ok, {st['rows']} rows")
        if st.get("dropped"):
            bits.append("dropped " + ", ".join(f"{k}={v}" for k, v in st["dropped"].items()))
        if st.get("note"):
            bits.append(st["note"])
        print(f"  {st['source']:9s} " + " | ".join(bits))
    if df.attrs.get("partial"):
        print("  !! the listing is PARTIAL; some sources failed or were truncated")


def _rows(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    bad = [i for i in out if i < 0 or i >= n]
    if bad:
        raise SystemExit(f"row(s) {bad} out of range (catalog has {n} rows, numbered from 0)")
    return out


def run(args) -> int:
    from . import api

    cmd = args.command
    if cmd == "search":
        ids = [x for x in (args.ids or "").split(",") if x.strip()] or None
        df = api.search(args.query, args.location, sources=args.sources, period=args.period,
                        ids=ids, basin=args.basin, state=args.state)
        if args.estimate:
            df = api.estimate(df)
        print("Sources:")
        print_status(df)
        if df.empty:
            print("No rows.")
        else:
            _print_catalog(df, args.limit)
            n_inf = int(df["Inferred"].astype(str).ne("").sum())
            print(f"\n{len(df)} rows. 'Inferred' fields (not stated by the source) are listed per row in the saved catalog; {n_inf} rows have some.")
        if args.save:
            print("Saved:", api.save_catalog(df, args.save))
        return 1 if (df.empty and df.attrs.get("partial")) else 0

    if cmd == "get":
        cat = api.load_catalog(args.catalog)
        sel = cat.iloc[_rows(args.rows, len(cat))]
        sel.attrs.update(cat.attrs)

        def progress(e):
            if e["event"] == "item_start":
                print(f"[{e['index']}/{e['total']}] {e['source']}: {e['title']}")
            elif e["event"] == "item_done":
                print(f"    -> {e['status']} ({e['records']} records)")
        res = api.fetch(sel, output_dir=args.out, period=args.period, format=args.format,
                        overwrite=args.overwrite, rc_discharge=not args.no_rc_discharge, progress=progress)
        print("Manifest:", res.attrs.get("manifest"))
        return 1 if (res["status"] == "error").any() else 0

    if cmd == "show":
        df = api.load(args.path)
        if df.empty:
            print("No tidy data.")
        else:
            g = df.groupby(["source", "variable", "unit", "method"], dropna=False).agg(
                rows=("value", "size"), stations=("station_id", "nunique"),
                start=("time", "min"), end=("time", "max"))
            print(g.to_string())
        for u in df.attrs.get("unmapped", []):
            print(f"UNMAPPED {u['file']}: {u['reason']}")
        return 0

    if cmd == "merge":
        df = api.merge(args.path, args.output)
        print(f"Wrote {len(df)} rows to {args.output}")
        return 0

    if cmd == "plot":
        paths = api.plot(args.path, args.output_dir, variable=args.variable)
        print(f"Wrote {len(paths)} figures to {args.output_dir}")
        return 0

    if cmd == "rsms":
        c = args.rsms_command
        if c == "daily":
            df = api.rsms.daily(output_path=args.out)
            print(f"{len(df)} reservoirs -> {args.out}")
        elif c == "backfill":
            df = api.rsms.backfill(start_date=args.start, end_date=args.end,
                                   output_csv=args.out, bulletin_dir=args.bulletin_dir)
            print(f"{len(df)} rows -> {args.out}")
        else:
            from pathlib import Path
            o = Path(args.out_dir)
            o.mkdir(parents=True, exist_ok=True)
            res = api.rsms.build_database(
                reservoir_shp=args.reservoir_shp, swot_observations=args.swot_db,
                gauge_source=args.gauge_cache,
                output_gpkg=o / "unified_reservoir_swot_gauge.gpkg",
                output_sqlite=o / "unified_reservoir_swot_gauge.sqlite",
                output_parquet=o / "unified_reservoir_timeseries.parquet")
            print(res)
        return 0

    if cmd == "cite":
        api.cite()
        return 0
    if cmd == "coffee":
        api.coffee()
        return 0
    return 2


def guided() -> int:
    """Interactive Find -> Review -> Get, asking for the data first and the source never."""
    from . import api
    print("HydroSwift guided mode (press Enter to skip a question)")
    q = input("Variable (e.g. rainfall, discharge, groundwater): ").strip() or None
    loc = input("Place (state, basin, organization): ").strip() or None
    per = input("Period (YYYY:YYYY): ").strip() or None
    df = api.search(q, loc, period=per)
    print("Sources:")
    print_status(df)
    if df.empty:
        print("Nothing found.")
        return 1
    _print_catalog(df, 40)
    pick = input("Rows to download (e.g. 0,2-4; Enter for none): ").strip()
    if not pick:
        return 0
    sel = df.iloc[_rows(pick, len(df))]
    sel.attrs.update(df.attrs)
    out = input("Output directory [output]: ").strip() or "output"
    res = api.fetch(sel, output_dir=out, period=per)
    print(res[["source", "title", "status", "records", "start", "end"]].to_string())
    print("Manifest:", res.attrs.get("manifest"))
    return 0


def main(argv=None) -> int:
    import sys
    parser = build_parser()
    raw = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-h", "--help", "--version") for a in raw[:1]) or not raw or raw[:1] == ["cite"]:
        from .banner import print_wish_banner
        print_wish_banner()
    args = parser.parse_args(argv)
    if not args.command:
        import sys
        if sys.stdin.isatty():
            return guided()
        parser.print_help()
        return 0
    return run(args)
