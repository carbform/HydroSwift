# India-WRIS API for Future versions

The official India-WRIS APIs (`https://indiawris.gov.in/swagger-ui/index.html`) are still UI-based, need some time to corrcetly integrate them into HydroSwift. 

It is intended as a roadmap for future v1.x or v2.0 upgrades.

## 1. Missing Time Series Variables

HydroSwift currently supports 9 core hydrological and meteorological parameters (discharge, water level, rainfall, temperature, humidity, solar radiation, sediment, atmospheric pressure, groundwater). 

The WRIS internal APIs expose 4 additional variables that can be integrated using the exact same `/CommonDataSetMasterAPI/getCommonDataSetByStationCode` pipeline currently powering HydroSwift:

| Parameter | WRIS Dataset Code | Recommended CLI Flag |
|---|---|---|
| Snowfall | `SNOWFALL` | `-snow` |
| Wind Direction | `WIND_DIR` | `-wind` |
| Evapotranspiration | `EVAPTRAN` | `-et` |
| Soil Moisture | `SOILMOIS` | `-sm` |

Requires adding these codes to `swift_app/cli.py` (`DATASETS`) and `swift_app/api.py` (`DATASET_ALIAS`, `WRIS_UNITS`), ensuring argument parsers map them correctly.

## 2. Master Administrative APIs (States & Districts)

HydroSwift's current WRIS discovery workflow exclusively uses the **Basin -> Tributary -> River -> Agency** hierarchy to find stations. 

The WRIS API also exposes Master Administrative endpoints that allow navigation by geopolitical bounds instead of hydrological bounds:

* `/masterState/StateList` - Retrieves all Indian States and their IDs.
* `/masterDistrict/getDistrictbyState` - Retrieves all Districts given a State ID.

 The current `wris_client.py` is fully capable of hitting these endpoints (via simple `POST` requests). However, wiring them up into `wris.stations()` and `wris.download()` to support filters like `state="Gujarat"` requires adapting the primary discovery loop to support an administrative constraint. (A similar feature is already implemented native to the CWC module!).

## 3. Public WRIS Developer APIs vs Internal Portal APIs

Currently, `wris_client.py` scrapes its data from the semi-undocumented endpoints powering the `indiawris.gov.in` web portal (`/v2/` / CommonDataSetMasterAPI). 

The WRIS portal also recently released official Public Developer APIs (`https://indiawris.gov.in/v3/api-docs` / Telemetry Data Service). 

**Future consideration:**

* **Pros of migrating to public v3 API:** Stable contracts, proper swagger documentation.
* **Cons of migrating:** The public APIs have different shapes, stricter rate limits, and sometimes mandate authentication/API tokens which ruins the zero-config nature of HydroSwift. 
