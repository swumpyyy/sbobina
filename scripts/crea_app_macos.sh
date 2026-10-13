#!/bin/zsh
# Crea Sbobina.app (icona nel Dock, doppio clic per aprire).
#   senza argomenti: app di sviluppo in ~/Applications che avvia il .venv di questa cartella (non va spostata).
#   --dmg: app autonoma (Python, ffmpeg e i motori MLX dentro il bundle) in dist/Sbobina.dmg, da dare a chiunque.
set -euo pipefail

PROGETTO="${0:A:h:h}"
DMG=0; [[ "${1:-}" == "--dmg" ]] && DMG=1
APP="$HOME/Applications/Sbobina.app"; (( DMG )) && APP="$PROGETTO/dist/Sbobina.app"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAVORO="$(mktemp -d)"
trap 'rm -rf "$LAVORO"' EXIT

# Ingredienti del bundle autonomo, scaricati una volta sola e verificati (sha256).
CACHE="$HOME/Library/Caches/sbobina-build"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.14.8+20261009-aarch64-apple-darwin-install_only.tar.gz"
PY_SHA="ff8e1ddc02a9df3190b62d5af475cb642a02cfc77901ef780f9826cc23b51934"

scarica() {  # url sha destinazione
  [[ -f "$3" ]] || curl -fL --progress-bar -o "$3.part" "$1"
  [[ -f "$3" ]] || mv "$3.part" "$3"
  [[ "$(shasum -a 256 "$3" | cut -c1-64)" == "$2" ]] || { echo "Checksum errato per $3: cancellalo e riprova."; exit 1; }
}

[[ -x "$PROGETTO/.venv/bin/sbobina" ]] || { echo "Manca $PROGETTO/.venv: crea prima l'ambiente (vedi README)."; exit 1; }
(( DMG )) || "$PROGETTO/.venv/bin/python" -c "import webview" 2>/dev/null || "$PROGETTO/.venv/bin/pip" install -q -e "${PROGETTO}[app,locale]"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Icona: il marchio di Sbobina, reso da scripts/icona.html.
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
  <key>NSMicrophoneUsageDescription</key><string>Sbobina registra la lezione dal microfono per trascriverla e scriverne gli appunti. L'audio resta sul tuo Mac.</string>
</dict></plist>
PLIST

if (( DMG )); then
  R="$APP/Contents/Resources"
  mkdir -p "$CACHE" "$R/bin"
  scarica "$PY_URL" "$PY_SHA" "$CACHE/python.tar.gz"
  tar xzf "$CACHE/python.tar.gz" -C "$R"
  # ffmpeg statico già usato in sviluppo (pacchetto static-ffmpeg del .venv).
  cp "${PROGETTO}/.venv/bin/ffmpeg"(:A) "${PROGETTO}/.venv/bin/ffprobe"(:A) "$R/bin/"
  PIP=("$R/python/bin/python3" -m pip install -q --no-compile --disable-pip-version-check)
  "${PIP[@]}" "${PROGETTO}[app]"
  # mlx-whisper senza torch (serve solo a convertire modelli, non a trascrivere): ~1 GB in meno.
  "${PIP[@]}" --no-deps "mlx-whisper>=0.4"
  "${PIP[@]}" huggingface_hub mlx more-itertools numba numpy scipy tiktoken tqdm "mlx-lm>=0.28"
  "$R/python/bin/python3" -c "import sbobina.app, mlx_whisper, mlx_lm, webview, Vision" || { echo "Import fallito nel bundle"; exit 1; }

  cat > "$APP/Contents/MacOS/Sbobina" <<'LANCIO'
#!/bin/zsh
# Tutto dal bundle; i dati dello studente in Application Support (il bundle è di sola lettura).
R="${0:A:h:h}/Resources"
SUPPORTO="$HOME/Library/Application Support/Sbobina"
export PATH="$R/bin:$PATH" SBOBINA_ICONA="$R/icona.png" SBOBINA_DATI="$SUPPORTO/dati"
mkdir -p "$SBOBINA_DATI" "$HOME/Library/Logs"
cd "$SUPPORTO"
exec "$R/python/bin/python3" -m sbobina.cli app >>"$HOME/Library/Logs/Sbobina.log" 2>&1
LANCIO
  chmod +x "$APP/Contents/MacOS/Sbobina"
  # Firma ad hoc di tutto il bundle: senza, macOS su Apple Silicon rifiuta i binari copiati.
  codesign --force --deep --sign - "$APP"

  rm -rf "$LAVORO/dmg" "$PROGETTO/dist/Sbobina.dmg"
  mkdir "$LAVORO/dmg"
  cp -R "$APP" "$LAVORO/dmg/"
  ln -s /Applications "$LAVORO/dmg/Applicazioni"
  cat > "$LAVORO/dmg/LEGGIMI.txt" <<'TESTO'
Installare Sbobina

1. Trascina Sbobina nella cartella Applicazioni.
2. Apri Sbobina dalla cartella Applicazioni.
3. Se macOS dice che non può verificare lo sviluppatore:
   Impostazioni di Sistema → Privacy e sicurezza → in fondo, "Apri comunque".
   Serve solo la prima volta.
4. Al primo avvio Sbobina scarica l'AI per gli appunti (circa 8 GB) e Whisper (1,6 GB).
   Poi funziona anche offline.

Requisiti: Mac con chip Apple (M1 o successivi), macOS 12 o successivo, 16 GB di RAM consigliati.
TESTO
  hdiutil create -quiet -volname Sbobina -srcfolder "$LAVORO/dmg" -ov -format ULFO "$PROGETTO/dist/Sbobina.dmg"
  echo "Creato $PROGETTO/dist/Sbobina.dmg ($(du -h "$PROGETTO/dist/Sbobina.dmg" | cut -f1))"
  exit 0
fi

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
