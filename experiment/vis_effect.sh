#!/bin/bash

# Efficiency Visualization Script - Anchors, Features, and Memory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Efficiency Visualization Tool"
echo ""

# Load effect configuration
EFFECT_CONFIG_FILE="effect_config.json"

if [ ! -f "$EFFECT_CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $EFFECT_CONFIG_FILE"
    exit 1
fi

# Get available configurations
echo "📋 Available configurations:"
CONFIGS=($(python -c "import json; config=json.load(open('$EFFECT_CONFIG_FILE')); print(' '.join(config.keys()))"))

for i in "${!CONFIGS[@]}"; do
    config_name="${CONFIGS[$i]}"
    desc=$(python -c "import json; config=json.load(open('$EFFECT_CONFIG_FILE')); print(config['$config_name'].get('description', 'No description'))")
    echo "  $((i+1)). $config_name - $desc"
done

echo ""
read -p "Select configuration (1-${#CONFIGS[@]}): " config_choice

if [[ ! "$config_choice" =~ ^[0-9]+$ ]] || [ "$config_choice" -lt 1 ] || [ "$config_choice" -gt "${#CONFIGS[@]}" ]; then
    echo "❌ Invalid configuration selection"
    exit 1
fi

SELECTED_CONFIG="${CONFIGS[$((config_choice-1))]}"
echo "✅ Selected configuration: $SELECTED_CONFIG"
echo ""

# Get configuration details
OUTPUT_FOLDER=$(python -c "import json; print(json.load(open('$EFFECT_CONFIG_FILE'))['$SELECTED_CONFIG']['output_folder'])")
METHOD_NAMES=($(python -c "import json; print(' '.join(json.load(open('$EFFECT_CONFIG_FILE'))['$SELECTED_CONFIG']['methods'].keys()))"))
METRICS=($(python -c "import json; print(' '.join(json.load(open('$EFFECT_CONFIG_FILE'))['$SELECTED_CONFIG']['metrics']))"))

# Validate files
echo "🔍 Checking data files..."
for method_name in "${METHOD_NAMES[@]}"; do
    file_path=$(python -c "import json; print(json.load(open('$EFFECT_CONFIG_FILE'))['$SELECTED_CONFIG']['methods']['$method_name']['path'])")
    
    if [ ! -f "$file_path" ]; then
        echo "❌ Missing file: $file_path"
        exit 1
    fi
    echo "✅ $method_name: $file_path"
done

echo ""
echo "🎯 Generating plots..."
echo "   Output folder: $OUTPUT_FOLDER"
echo "   Methods: ${METHOD_NAMES[@]}"
echo "   Metrics: ${METRICS[@]}"
echo ""

python vis_effect.py \
    --config "$SELECTED_CONFIG" \
    --figsize 10 10 \
    --dpi 420

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Done! Output plots saved in $OUTPUT_FOLDER/:"

    # List generated files
    for metric in "${METRICS[@]}"; do
        echo ""
        echo "   📊 $metric metric:"
        echo "      - comparison_${metric}_4x3.png (with numbers, 4:3)"
        echo "      - comparison_${metric}_clean_4x3.png (no numbers, 4:3)"
        echo "      - comparison_${metric}_16x9.png (with numbers, 16:9)"
        echo "      - comparison_${metric}_clean_16x9.png (no numbers, 16:9)"
    done
    
    if command -v xdg-open &> /dev/null; then
        echo ""
        echo "💡 Run 'xdg-open $OUTPUT_FOLDER/' to view all plots"
    fi
else
    echo "❌ Failed!"
    exit 1
fi
