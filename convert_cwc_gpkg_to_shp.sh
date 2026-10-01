#!/bin/bash
# Run this after the CWC download finishes to convert the new GPKGs to SHP
eval "$(conda shell.bash hook)"
conda activate carbform

echo "Converting CWC GPKGs to SHP..."
for gpkg in output/cwc/*.gpkg; do
    if [ -f "$gpkg" ]; then
        filename=$(basename -- "$gpkg")
        name="${filename%.*}"
        ogr2ogr -f "ESRI Shapefile" "output/cwc/${name}.shp" "$gpkg"
        echo "Converted $name.shp"
    fi
done
echo "Done!"
