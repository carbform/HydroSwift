#!/bin/bash
echo "Waiting for CWC update to finish..."
# Wait for the python process running hydroswift to finish
while pgrep -f "python hydroswift.py --cwc" > /dev/null; do
    sleep 5
done
echo "Converting new GPKGs to SHP..."
eval "$(conda shell.bash hook)"
conda activate carbform
for gpkg in output_new/cwc/*.gpkg; do
    if [ -f "$gpkg" ]; then
        filename=$(basename -- "$gpkg")
        name="${filename%.*}"
        ogr2ogr -f "ESRI Shapefile" "output_new/cwc/${name}.shp" "$gpkg"
        echo "Converted $name.shp"
    fi
done
echo "All done!"
