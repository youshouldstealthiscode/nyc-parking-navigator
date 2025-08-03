#!/bin/bash
# Generate placeholder app icons

# Icon text - P for Parking
ICON_TEXT="P"

# Colors
BG_COLOR="#2196F3"  # Blue
TEXT_COLOR="#FFFFFF" # White

# Sizes for different densities
declare -A SIZES=(
    ["mdpi"]=48
    ["hdpi"]=72
    ["xhdpi"]=96
    ["xxhdpi"]=144
    ["xxxhdpi"]=192
)

# Create icons using ImageMagick (if available) or create placeholder files
for density in "${!SIZES[@]}"; do
    SIZE=${SIZES[$density]}
    OUTPUT_DIR="android/app/src/main/res/mipmap-$density"
    OUTPUT_FILE="$OUTPUT_DIR/ic_launcher.png"
    
    if command -v convert &> /dev/null; then
        # Use ImageMagick if available
        convert -size ${SIZE}x${SIZE} xc:"$BG_COLOR" \
                -gravity center \
                -pointsize $((SIZE/2)) \
                -fill "$TEXT_COLOR" \
                -font "Helvetica-Bold" \
                -annotate +0+0 "$ICON_TEXT" \
                "$OUTPUT_FILE"
        echo "Created icon: $OUTPUT_FILE (${SIZE}x${SIZE})"
    else
        # Create a placeholder file
        echo "P" > "$OUTPUT_FILE"
        echo "Created placeholder: $OUTPUT_FILE"
    fi
done

echo "✅ Icon placeholders created. For production, replace with proper app icons."