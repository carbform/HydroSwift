import sys
import pytest
import pandas as pd
from types import SimpleNamespace
from swift_app.api import _normalize_dataset_flags

def _get_cwc_engine_module():
    """Return the actual swift_app.cwc *module* (not the namespace object).

    ``swift_app.__init__`` exports ``cwc = _CwcNamespace()``, which shadows
    the ``swift_app.cwc`` submodule as a package attribute.  Tests that need
    to monkeypatch the engine module (e.g. ``PACKAGED_CSV``) must retrieve
    the module object from ``sys.modules`` instead.
    """
    import swift_app
    return sys.modules['swift_app.cwc']

def test_dataset_aliases_cover_cli_style_and_python_style_names():
    flags = _normalize_dataset_flags(['discharge', 'atm_pressure', 'solar_radiation', 'groundwater_level'])
    assert flags == ['q', 'atm', 'solar', 'gwl']

def test_unknown_dataset_error_is_actionable():
    with pytest.raises(ValueError, match='Supported values'):
        _normalize_dataset_flags(['bogus_dataset'])

def test_cwc_stations_refresh_uses_live_fetch(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    fresh = pd.DataFrame([{'code': 'AAA001', 'name': 'Station A'}, {'code': 'BBB001', 'name': 'Station B'}])
    monkeypatch.setattr(cwc_mod, 'fetch_cwc_station_metadata', lambda: fresh)
    monkeypatch.setattr(cwc_mod, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'cwc_meta.csv')
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        out = api_mod.cwc_ns.stations(refresh=True)
    assert list(out['code']) == ['AAA001', 'BBB001']

def test_cwc_stations_refresh_applies_basin_filter_after_live_fetch(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    fresh = pd.DataFrame([{'code': 'AAA001', 'name': 'A', 'basin': 'Krishna'}, {'code': 'BBB001', 'name': 'B', 'basin': 'Godavari'}, {'code': 'CCC001', 'name': 'C', 'basin': 'Mahanadi'}])
    monkeypatch.setattr(cwc_mod, 'fetch_cwc_station_metadata', lambda: fresh)
    monkeypatch.setattr(cwc_mod, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'cwc_meta.csv')
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        out = api_mod.cwc_ns.stations(basin='Krishna', refresh=True)
    assert len(out) == 1
    assert out.iloc[0]['code'] == 'AAA001'

def test_cwc_stations_refresh_falls_back_when_live_unavailable(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    monkeypatch.setattr(cwc_mod, 'fetch_cwc_station_metadata', lambda: pd.DataFrame())
    monkeypatch.setattr(cwc_mod, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'nonexistent_cache.csv')
    fallback = tmp_path / 'packaged.csv'
    fallback.write_text('code,name\n040-CDJAPR,Parwan pick-up Weir\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', fallback)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        out = api_mod.cwc_ns.stations(refresh=True)
    assert len(out) == 1
    assert out.iloc[0]['code'] == '040-CDJAPR'

def test_cwc_stations_default_uses_packaged_csv(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    local_csv = tmp_path / 'local.csv'
    local_csv.write_text('code,name\nLOC001,Local Station\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', local_csv)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'nonexistent.csv')
    out = api_mod.cwc_ns.stations()
    assert len(out) == 1
    assert out.iloc[0]['code'] == 'LOC001'

def test_cwc_stations_prefers_cache_over_packaged(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    cache_csv = tmp_path / 'cwc_meta.csv'
    cache_csv.write_text('code,name\nCACHE01,Cached Station\n')
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', cache_csv)
    packaged = tmp_path / 'packaged.csv'
    packaged.write_text('code,name\nPKG001,Packaged Station\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', packaged)
    out = api_mod.cwc_ns.stations()
    assert len(out) == 1
    assert out.iloc[0]['code'] == 'CACHE01'

def test_cwc_stations_station_filter(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    csv = tmp_path / 'meta.csv'
    csv.write_text('code,name\n001-AAA,Alpha\n002-BBB,Beta\n003-CCC,Gamma\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', csv)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'nonexistent.csv')
    out = api_mod.cwc_ns.stations(station='002-BBB')
    assert len(out) == 1
    assert out.iloc[0]['code'] == '002-BBB'

def test_cwc_namespace_download_rejects_station_table_input(monkeypatch):
    import swift_app.api as api_mod
    stations = api_mod.SwiftTable(pd.DataFrame({'code': ['040-CDJAPR', '032-LGDHYD'], 'name': ['A', 'B']}))
    with pytest.raises(TypeError, match='use swift.fetch'):
        api_mod.cwc_ns.download(station=stations, quiet=True)

def test_cwc_namespace_download_dispatches(monkeypatch):
    """swift.cwc.download() should delegate to the CWC engine."""
    import swift_app.api as api_mod
    calls = {}

    def fake_run_cwc_download(args):
        calls['cwc'] = args.cwc
        calls['stations'] = args.cwc_station
    monkeypatch.setattr(api_mod, 'run_cwc_download', fake_run_cwc_download)
    api_mod.cwc_ns.download(station=['040-CDJAPR'], quiet=True)
    assert calls['cwc'] is True
    assert calls['stations'] == ['040-CDJAPR']

def test_cwc_namespace_download_accepts_variable_kwarg(monkeypatch):
    """swift.cwc.download(..., variable=...) should pass through to get_cwc_data."""
    import swift_app.api as api_mod
    calls = {}

    def fake_get_cwc_data(**kwargs):
        calls['var'] = kwargs.get('var')
        calls['station'] = kwargs.get('station')
        return None
    monkeypatch.setattr(api_mod, 'get_cwc_data', fake_get_cwc_data)
    api_mod.cwc_ns.download(station=['040-CDJAPR'], variable='discharge', quiet=True)
    assert calls['station'] == ['040-CDJAPR']
    assert calls['var'] == 'discharge'

def test_cwc_namespace_download_accepts_rc_discharge_toggle(monkeypatch):
    import swift_app.api as api_mod
    calls = {}

    def fake_get_cwc_data(**kwargs):
        calls['rc_discharge'] = kwargs.get('rc_discharge')
        return None
    monkeypatch.setattr(api_mod, 'get_cwc_data', fake_get_cwc_data)
    api_mod.cwc_ns.download(station=['040-CDJAPR'], rc_discharge=False, quiet=True)
    assert calls['rc_discharge'] is False

def test_cwc_namespace_download_basin_filter(monkeypatch):
    import swift_app.api as api_mod
    calls = {}

    def fake_run_cwc_download(args):
        calls['cwc'] = args.cwc
        calls['stations'] = args.cwc_station
        calls['basin_filter'] = args.cwc_basin_filter
    monkeypatch.setattr(api_mod, 'run_cwc_download', fake_run_cwc_download)
    api_mod.cwc_ns.download(basin=['Krishna', 'Godavari'], quiet=True)
    assert calls['cwc'] is True
    assert calls['basin_filter'] == ['Krishna', 'Godavari']

def test_cwc_namespace_download_rejects_basin_table_input(monkeypatch):
    import swift_app.api as api_mod
    basin_table = api_mod.SwiftTable(pd.DataFrame({'basin': ['Krishna', 'Godavari', 'Mahanadi'], 'station_count': [10, 20, 30]}))
    with pytest.raises(TypeError, match='use swift.fetch'):
        api_mod.cwc_ns.download(basin=basin_table.iloc[0:2], quiet=True)

def test_cwc_namespace_refresh_metadata_exposes_appended_count(monkeypatch):
    import swift_app.api as api_mod
    merged = pd.DataFrame([{'code': '001-AAA', 'name': 'A'}])
    appended = pd.DataFrame([{'code': '001-AAA', 'name': 'A'}])
    monkeypatch.setattr(api_mod, 'repopulate_cwc_metadata_from_name_code', lambda write_packaged=False: (merged, appended))
    out = api_mod.cwc_ns.refresh_metadata(write=False)
    assert len(out) == 1
    assert out.attrs['appended_count'] == 1

def test_cwc_namespace_stations(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    csv = tmp_path / 'meta.csv'
    csv.write_text('code,name\n040-CDJAPR,Parwan pick-up Weir\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', csv)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'nonexistent.csv')
    out = api_mod.cwc_ns.stations(station='040-CDJAPR')
    assert len(out) == 1
    assert out.iloc[0]['code'] == '040-CDJAPR'

def test_fetch_dispatches_to_cwc(monkeypatch):
    import swift_app.api as api_mod
    calls = {}

    def fake_run_cwc_download(args):
        calls['cwc'] = args.cwc
        calls['stations'] = args.cwc_station
    monkeypatch.setattr(api_mod, 'run_cwc_download', fake_run_cwc_download)
    stations = api_mod.SwiftTable(pd.DataFrame({'code': ['040-CDJAPR']}))
    stations.attrs['source'] = 'cwc'
    api_mod.fetch(stations, quiet=True)
    assert calls['cwc'] is True
    assert calls['stations'] == ['040-CDJAPR']

def test_get_cwc_data_accepts_discharge_var_without_warning(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    import warnings
    monkeypatch.setattr(api_mod, 'run_cwc_download', lambda args: None)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter('always')
        api_mod.get_cwc_data(station=['040-CDJAPR'], var=['water_level', 'discharge', 'q'], output_dir=tmp_path, merge=False, quiet=True)
    msgs = [str(w.message) for w in rec]
    assert not any(('Ignoring unsupported variable' in m for m in msgs))

def test_get_cwc_data_merge_sets_discharge_units_when_present(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    monkeypatch.setattr(api_mod, 'run_cwc_download', lambda args: None)
    cwc_root = tmp_path / 'cwc'
    cwc_root.mkdir(parents=True, exist_ok=True)
    gpkg = cwc_root / 'cwc_waterlevel_all_stations_2024-01-01_2024-01-02.gpkg'
    gpkg.write_text('placeholder')
    fake_gpd = SimpleNamespace(read_file=lambda _p: pd.DataFrame({'station_code': ['S1'], 'time': ['2024-01-01'], 'wse': [10.0], 'q': [123.0]}))
    monkeypatch.setitem(sys.modules, 'geopandas', fake_gpd)
    out = api_mod.get_cwc_data(station=['S1'], start_date='2024-01-01', end_date='2024-01-02', output_dir=tmp_path, merge=True, quiet=True)
    assert out is not None
    assert out.attrs['units']['water_level'] == 'm'
    assert out.attrs['units']['q'] == 'm3/s'
    assert out.attrs['units']['discharge'] == 'm3/s'

def test_fetch_invalid_input_type_raises():
    import swift_app.api as api_mod
    with pytest.raises(TypeError, match='expects a pandas DataFrame'):
        api_mod.fetch('invalid_source')

def test_fetch_cwc_missing_code_column_raises():
    import swift_app.api as api_mod
    stations = api_mod.SwiftTable(pd.DataFrame({'station_code': ['ST001']}))
    stations.attrs['source'] = 'cwc'
    with pytest.raises(ValueError, match="must include 'code' column"):
        api_mod.fetch(stations)

def test_merge_only_with_mode_derives_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    calls = {}

    def fake_run_merge_only(args):
        calls['input_dir'] = args.input_dir
    monkeypatch.setattr(api_mod, 'run_merge_only', fake_run_merge_only)
    api_mod.merge_only(mode='wris', output_dir=str(tmp_path))
    assert calls['input_dir'] == str(tmp_path)

def test_merge_only_discovers_basins_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    (tmp_path / 'wris' / 'godavari').mkdir(parents=True)
    calls = []

    def fake_run_merge_only(args):
        calls.append(args.input_dir)
    monkeypatch.setattr(api_mod, 'run_merge_only', fake_run_merge_only)
    api_mod.merge_only(input_dir=str(tmp_path), variable=['solar'], output_dir=str(tmp_path / 'merged'))
    assert calls == [str(tmp_path)]

def test_merge_only_cwc_no_basin_warning(monkeypatch, tmp_path):
    """merge_only(mode='cwc') runs once with no basin/datasets warning."""
    import swift_app.api as api_mod
    (tmp_path / 'cwc' / 'godavari' / 'stations').mkdir(parents=True)
    calls = []

    def fake_run_merge_only(args):
        calls.append((args.input_dir, getattr(args, 'cwc', False)))
    monkeypatch.setattr(api_mod, 'run_merge_only', fake_run_merge_only)
    api_mod.merge_only(mode='cwc', input_dir=str(tmp_path), output_dir=str(tmp_path))
    assert len(calls) == 1
    assert calls[0][0] == str(tmp_path)
    assert calls[0][1] is True

def test_plot_only_with_mode_derives_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    calls = {}

    def fake_run_plot_only(args):
        calls['input_dir'] = args.input_dir
        calls['cwc'] = args.cwc
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(mode='wris', output_dir=str(tmp_path))
    assert calls['input_dir'] == str(tmp_path)
    assert calls['cwc'] is False

def test_plot_only_discovers_basins_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    (tmp_path / 'wris' / 'godavari').mkdir(parents=True)
    calls = []

    def fake_run_plot_only(args):
        calls.append(args.input_dir)
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(input_dir=str(tmp_path), variable=['solar', 'sediment'], output_dir=str(tmp_path / 'plots'))
    assert calls == [str(tmp_path)]

def test_plot_only_cwc_discovers_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'cwc' / 'godavari' / 'stations').mkdir(parents=True)
    calls = []

    def fake_run_plot_only(args):
        calls.append(args.input_dir)
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(mode='cwc', input_dir=str(tmp_path), output_dir=str(tmp_path))
    assert calls == [str(tmp_path)]

def test_plot_only_cwc_mode_sets_cwc_flag(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    calls = {}

    def fake_run_plot_only(args):
        calls['cwc'] = args.cwc
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(mode='cwc', output_dir=str(tmp_path))
    assert calls['cwc'] is True

def test_plot_only_input_dir_must_exist(tmp_path):
    import swift_app.api as api_mod
    missing = tmp_path / 'nonexistent'
    assert not missing.exists()
    with pytest.raises(ValueError, match='input_dir does not exist'):
        api_mod.plot_only(input_dir=str(missing), output_dir=str(tmp_path / 'plots'))

def test_plot_only_prefers_window_aliases(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    calls = {}

    def fake_run_plot_only(args):
        calls['plot_moving_average_window'] = getattr(args, 'plot_moving_average_window', None)
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(mode='wris', output_dir=str(tmp_path), moving_average=True, window=30)
    assert calls['plot_moving_average_window'] == 30

def test_plot_only_bool_moving_average_defaults_to_30(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    (tmp_path / 'wris' / 'krishna').mkdir(parents=True)
    calls = {}

    def fake_run_plot_only(args):
        calls['plot_moving_average_window'] = getattr(args, 'plot_moving_average_window', None)
    monkeypatch.setattr(api_mod, 'run_plot_only', fake_run_plot_only)
    api_mod.plot_only(mode='wris', output_dir=str(tmp_path), moving_average=True)
    assert calls['plot_moving_average_window'] == 30

def test_package_exposes_cwc_namespace():
    import swift_app
    assert hasattr(swift_app, 'cwc')
    assert hasattr(swift_app.cwc, 'download')
    assert hasattr(swift_app.cwc, 'stations')

def test_package_exposes_fetch():
    import swift_app
    assert hasattr(swift_app, 'fetch')
    assert callable(swift_app.fetch)

def test_package_exposes_merge_only_and_plot_only():
    import swift_app
    assert hasattr(swift_app, 'merge_only')
    assert callable(swift_app.merge_only)
    assert hasattr(swift_app, 'plot_only')
    assert callable(swift_app.plot_only)

def test_package_does_not_expose_removed_merge_plot_aliases():
    import swift_app
    merge_attr = getattr(swift_app, 'merge', None)
    plot_attr = getattr(swift_app, 'plot', None)
    assert not callable(merge_attr)
    assert not callable(plot_attr)

def test_package_does_not_expose_legacy_datasets_basins():
    import swift_app
    assert not hasattr(swift_app, 'datasets')
    assert not hasattr(swift_app, 'basins')

def test_cwc_namespace_exposes_basins(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()
    csv = tmp_path / 'meta.csv'
    csv.write_text('code,name,basin\n001-AAA,Alpha,Godavari\n002-BBB,Beta,Krishna\n003-CCC,Gamma,Godavari\n')
    monkeypatch.setattr(cwc_mod, 'PACKAGED_CSV', csv)
    monkeypatch.setattr(cwc_mod, 'CACHE_FILE', tmp_path / 'nonexistent.csv')
    out = api_mod.cwc_ns.basins()
    assert {'basin', 'station_count'}.issubset(out.columns)
    counts = dict(zip(out['basin'], out['station_count']))
    assert counts['Godavari'] == 2
    assert counts['Krishna'] == 1

def test_package_help_prints_python_api_menu(capsys):
    import swift_app
    swift_app.help()
    out = capsys.readouterr().out
    assert 'HydroSwift Python API help' in out
    assert 'swift.wris.download' in out
    assert 'swift.fetch(table, ...)' in out
    assert 'swift.cli_help()' in out

def test_cwc_download_basin_all_downloads_all_stations(monkeypatch):
    import swift_app.api as api_mod
    captured = {}

    def fake_get_cwc_data(**kwargs):
        captured.update(kwargs)
        return None
    monkeypatch.setattr(api_mod, 'get_cwc_data', fake_get_cwc_data)
    api_mod.cwc_ns.download(basin='all')
    assert captured.get('basin') is None

def test_cwc_stations_basin_all_returns_all(monkeypatch):
    import swift_app.api as api_mod
    captured = {}

    def fake_cwc_stations(**kwargs):
        captured.update(kwargs)
        import pandas as pd
        return pd.DataFrame()
    monkeypatch.setattr(api_mod, 'cwc_stations', fake_cwc_stations)
    api_mod.cwc_ns.stations(basin='all')
    assert captured.get('basin') is None