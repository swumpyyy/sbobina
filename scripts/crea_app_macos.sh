#!/bin/zsh
# Crea Sbobina.app (icona nel Dock, doppio clic per aprire) e la installa in ~/Applications.
# shortcut: l'app avvia il .venv di questa cartella, quindi non va spostata; per distribuirla ai compagni serve un bundle autonomo (py2app/briefcase).
set -euo pipefail

PROGETTO="${0:A:h:h}"
APP="$HOME/Applications/Sbobina.app"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAVORO="$(mktemp -d)"
trap 'rm -rf "$LAVORO"' EXIT

[[ -x "$PROGETTO/.venv/bin/sbobina" ]] || { echo "Manca $PROGETTO/.venv: crea prima l'ambiente (vedi README)."; exit 1; }
"$PROGETTO/.venv/bin/python" -c "import webview" 2>/dev/null || "$PROGETTO/.venv/bin/pip" install -q -e "$PROGETTO[app,locale]"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Icona: la manopola del pannello hi-fi, resa da scripts/icona.html.
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000 \
  --window-size=1024,1024 --screenshot="$LAVORO/icona.png" "file://$PROGETTO/scripts/icona.html" 2>/dev/null
mkdir "$LAVORO/Sbobina.iconset"
for lato in 16 32 128 256 512; do
  sips -z $lato $lato "$LAVORO/icona.png" --out "$LAVORO/Sbobina.iconset/icon_${lato}x${lato}.png" >/dev/null
  sips -z $((lato * 2)) $((lato * 2)) "$LAVORO/icona.png" --out "$LAVORO/Sbobina.iconset/icon_${lato}x${lato}@2x.png" >/dev/null
done
iconutil -c icns "$LAVORO/Sbobina.iconset" -o "$APP/Contents/Resources/Sbobina.icns"
cp "$LAVORO/icona.png" "$APP/Contents/Resources/icona.png"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Sbobina</string>
  <key>CFBundleDisplayName</key><string>Sbobina</string>
  <key>CFBundleIdentifier</key><string>it.sbobina.app</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Sbobina</string>
  <key>CFBundleIconFile</key><string>Sbobina</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>LSRequiresNativeExecution</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.education</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/Sbobina" <<LANCIO
#!/bin/zsh
# ffmpeg/ffprobe sono nel .venv (static-ffmpeg): va messo nel PATH.
cd "$PROGETTO"
export PATH="$PROGETTO/.venv/bin:\$PATH" SBOBINA_ICONA="\${0:A:h:h}/Resources/icona.png"
mkdir -p "\$HOME/Library/Logs"
export __PYVENV_LAUNCHER__="$PROGETTO/.venv/bin/python"
exec /usr/bin/arch -arm64 "\${0:A:h}/python" -m sbobina.cli app >>"\$HOME/Library/Logs/Sbobina.log" 2>&1
LANCIO
chmod +x "$APP/Contents/MacOS/Sbobina"

# Copia dell'interprete dentro il bundle: così macOS vede il processo come "Sbobina" (nome e icona nel Dock)
# invece di "Python". __PYVENV_LAUNCHER__ gli fa usare comunque il .venv del progetto.
PYAPP="$("$PROGETTO/.venv/bin/python" -c 'import sys; print(sys.base_prefix)')/Resources/Python.app/Contents/MacOS/Python"
cp "$PYAPP" "$APP/Contents/MacOS/python"
# La firma originale non vale fuori da Python.app (macOS lo ucciderebbe): firma ad hoc locale.
codesign --force --sign - "$APP/Contents/MacOS/python" 2>/dev/null

touch "$APP"
echo "Creata $APP: aprila dal Launchpad o trascinala nel Dock."
