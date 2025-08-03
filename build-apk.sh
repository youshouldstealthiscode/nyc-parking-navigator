#!/bin/bash
# NYC Parking Navigator - APK Build Script

echo "🚀 Building NYC Parking Navigator APK..."
echo "======================================="

cd android

# Clean previous builds
echo "🧹 Cleaning previous builds..."
./gradlew clean

# Build release APK
echo "🔨 Building release APK..."
./gradlew assembleRelease

# Check if build was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    
    # Find the APK
    APK_PATH="app/build/outputs/apk/release/app-release.apk"
    
    if [ -f "$APK_PATH" ]; then
        # Get APK size
        APK_SIZE=$(ls -lh "$APK_PATH" | awk '{print $5}')
        
        # Copy to root directory with friendly name
        cp "$APK_PATH" "../NYC-Parking-Navigator.apk"
        
        echo "📱 APK Details:"
        echo "   Location: NYC-Parking-Navigator.apk"
        echo "   Size: $APK_SIZE"
        echo ""
        echo "📲 Installation Instructions:"
        echo "   1. Transfer NYC-Parking-Navigator.apk to your Samsung Galaxy S20 FE"
        echo "   2. On your phone, go to Settings > Security"
        echo "   3. Enable 'Install from Unknown Sources' or 'Install unknown apps'"
        echo "   4. Use a file manager to locate and tap the APK file"
        echo "   5. Follow the installation prompts"
        echo ""
        echo "⚠️  Note: This is a demo APK signed with debug keys."
        echo "   For production use, sign with your own release keys."
    else
        echo "❌ APK not found at expected location"
    fi
else
    echo "❌ Build failed! Check the error messages above."
fi