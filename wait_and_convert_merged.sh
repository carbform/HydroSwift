#!/bin/bash
echo "Waiting for swot merge to finish..."
while pgrep -f "python hydroswift.py --swot-merge" > /dev/null; do
    sleep 2
done
echo "Converting wris_merged.gpkg to SHP..."
eval "$(conda shell.bash hook)"
conda activate carbform
ogr2ogr -f "ESRI Shapefile" output/wris_merged.shp output/wris_merged.gpkg -overwrite
mv output/cwc_waterlevel_brahmaputra_2020-01-01_2025-12-31.gpkg.bak output/cwc/cwc_waterlevel_brahmaputra_2020-01-01_2025-12-31.gpkg
echo "Done!"
