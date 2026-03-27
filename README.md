# LetoHry Lode

[![Tests](https://github.com/sten-stulda/letohry-lode/actions/workflows/tests.yml/badge.svg)](https://github.com/sten-stulda/letohry-lode/actions/workflows/tests.yml)
[![Shell Checks](https://github.com/sten-stulda/letohry-lode/actions/workflows/shell-checks.yml/badge.svg)](https://github.com/sten-stulda/letohry-lode/actions/workflows/shell-checks.yml)
[![Release](https://img.shields.io/github/v/release/sten-stulda/letohry-lode?cacheSeconds=60)](https://github.com/sten-stulda/letohry-lode/releases/tag/v0.1.0)

Open-source aplikace pro Raspberry Pi, ktera pripoji dva veslarske trenazery Concept2 s monitorem PM3 pres USB a zobrazi realtime zavod dvou virtualnich lodi na jedne obrazovce.

Repozitář: https://github.com/sten-stulda/letohry-lode

Licence: MIT, viz [LICENSE](/home/stulda/projekty/letohry-lode/LICENSE)

Aktuální verze: `0.1.0`, viz [VERSION](/home/stulda/projekty/letohry-lode/VERSION) a [CHANGELOG.md](/home/stulda/projekty/letohry-lode/CHANGELOG.md)

Automatické testy při pushi a pull requestech běží přes GitHub Actions v [tests.yml](/home/stulda/projekty/letohry-lode/.github/workflows/tests.yml).
Kontrola shell skriptů běží v [shell-checks.yml](/home/stulda/projekty/letohry-lode/.github/workflows/shell-checks.yml) a release workflow je připravené v [release.yml](/home/stulda/projekty/letohry-lode/.github/workflows/release.yml).

## Co projekt umi

- realtime zavod dvou hracu na 500 m, 1000 m a 2000 m
- ghost rezim proti poslednimu vykonu nebo osobnimu rekordu
- intervalovy rezim 30/30 a 60/60 s countdownem a zobrazenim faze
- lokalni SQLite historii jizd a top 10 leaderboard
- bonusove body a achievementy
- lehky fullscreen frontend v HTML5 Canvas bez heavy frameworku
- websocket stream s minimem latence pro Raspberry Pi
- offline provoz v jedne sluzbe bez nutnosti internetu

## Struktura projektu

```text
backend/
  api/
  core/
  pm3/
frontend/
data/
run.py
requirements.txt
README.md
```

## Architektura

- [backend/main.py](/home/stulda/projekty/letohry-lode/backend/main.py) spousti FastAPI, staticky frontend a websocket endpoint.
- [backend/core/race_manager.py](/home/stulda/projekty/letohry-lode/backend/core/race_manager.py) drzi stav zavodu, countdown, gamifikaci, ghost lod a polling PM3.
- [backend/pm3/device.py](/home/stulda/projekty/letohry-lode/backend/pm3/device.py) oddeluje mock a realne PM3 zariizeni pres CSAFE over USB serial.
- [backend/storage.py](/home/stulda/projekty/letohry-lode/backend/storage.py) uklada vysledky, leaderboard a historii do SQLite.
- [frontend/app.js](/home/stulda/projekty/letohry-lode/frontend/app.js) obsluhuje API, websocket a canvas vykreslovani lodi.

## API

- `GET /api/status`
- `GET /api/race`
- `POST /api/start`
- `POST /api/reset`
- `GET /api/history`
- `GET /api/history/export`
- `GET /api/leaderboard/export`
- `GET /api/diagnostics/status`
- `GET /api/diagnostics/events`
- `GET /api/diagnostics/export`
- `GET /ws/race`

### Priklad startu zavodu

```bash
curl -X POST http://127.0.0.1:8000/api/start \
  -H 'Content-Type: application/json' \
  -d '{
    "player_names": ["Alice", "Bob"],
    "distance_m": 1000,
    "mode": "realtime",
    "theme": "river",
    "ghost_source": "none",
    "use_mock_devices": true
  }'
```

## Instalace na Raspberry Pi

Pro nové Raspberry Pi je doporučený postup popsaný i v [deploy/raspi/INSTALL_ON_FRESH_PI.md](/home/stulda/projekty/letohry-lode/deploy/raspi/INSTALL_ON_FRESH_PI.md). Prakticky je lepší použít Raspberry Pi Imager pro základní systém a pak spustit bootstrap skript [deploy/raspi/bootstrap-fresh-pi.sh](/home/stulda/projekty/letohry-lode/deploy/raspi/bootstrap-fresh-pi.sh), než hned vyrábět vlastní image SD karty.

Pokud bude projekt uložený na GitHubu, bootstrap umí repozitář rovnou naklonovat a další změny pak může Raspberry Pi tahat skriptem [deploy/raspi/update-from-github.sh](/home/stulda/projekty/letohry-lode/deploy/raspi/update-from-github.sh).

Ve výchozím stavu bootstrap používá repozitář `https://github.com/sten-stulda/letohry-lode.git`, takže na čistém Raspberry Pi často stačí jen spustit samotný bootstrap bez dalšího doplňování URL.

1. Nainstaluj systemove balicky:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip libatlas-base-dev
```

2. Vytvor virtualni prostredi a nainstaluj zavislosti:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Pro lokalni testy a smoke testy dopln i vyvojove zavislosti:

```bash
pip install -r requirements-dev.txt
```

3. Pripoj PM3 monitory pres USB-B kabely a over porty:

```bash
ls /dev/ttyUSB*
```

4. Nastav porty, pokud nepouzivas mock rezim:

```bash
export ROWING_PORT_1=/dev/ttyUSB0
export ROWING_PORT_2=/dev/ttyUSB1
```

Pokud promene nenastavis, backend se pri realnem zavodu pokusi PM3 sam najit podle USB descriptoru a fallbackne na `/dev/ttyUSB0` a `/dev/ttyUSB1`.

5. Spust aplikaci jednim prikazem:

```bash
python run.py
```

6. Otevri na Raspberry Pi fullscreen browser na `http://127.0.0.1:8000`.

### Automatizace pro ciste Raspberry Pi

Po prvnim bootu lze pouzit bootstrap skript:

```bash
cd /home/stulda/letohry-lode
chmod +x deploy/raspi/bootstrap-fresh-pi.sh
./deploy/raspi/bootstrap-fresh-pi.sh /home/stulda/letohry-lode
```

Pokud repozitar jeste neni na Raspberry Pi naklonovany, je vhodne ho nejdriv naklonovat nebo bootstrap skriptu predat URL repozitare. Prakticky postup je rozepsany v [deploy/raspi/INSTALL_ON_FRESH_PI.md](/home/stulda/projekty/letohry-lode/deploy/raspi/INSTALL_ON_FRESH_PI.md).

Pro opakovane aktualizace z GitHubu:

```bash
cd /home/pi/letohry-lode
chmod +x deploy/raspi/update-from-github.sh
./deploy/raspi/update-from-github.sh /home/pi/letohry-lode
```

Kdyz chces drzet lokalni nastaveni mimo repozitar, priprav si `/etc/letohry-lode.env` podle vzoru [deploy/raspi/letohry-lode.env.example](/home/stulda/projekty/letohry-lode/deploy/raspi/letohry-lode.env.example).

Pro kiosk Chromium lze v tomtez souboru nastavit i GPU rezim:

```bash
ROWING_KIOSK_GPU_MODE=auto
```

Podporovane hodnoty:

- `auto`: na Raspberry Pi 4 a 5 zkusi GPU akceleraci zapnout, jinde ji radsi vypne
- `on`: GPU akceleraci v kiosku vynuti
- `off`: GPU akceleraci v kiosku vypne kvuli stabilite

Pokud bude na Raspberry Pi obraz plynulejsi s GPU, nastav `ROWING_KIOSK_GPU_MODE=on` a restartuj kiosk sluzbu. Pokud bude Chromium padat nebo zamrzat, vrat se na `off`.

Pri kazdem pushi do `main` a pri kazdem pull requestu se na GitHubu automaticky spusti pytest workflow. To pomuze zachytit rozbite API, websockety nebo exporty driv, nez zmeny dotahnou na Raspberry Pi.

## Testy bez hardware

Mock rezim lze otestovat kompletne bez PM3:

```bash
pytest
```

Testy overuji:

- start, countdown, finish a reset zavodu
- ukladani vysledku do SQLite historie
- websocket stream pro realtime frontend
- CSAFE framing a zakladni autodetekci portu
- CSV export historie vysledku
- leaderboard export a PM3 diagnostiku

Pokud zkusis vypnout mock rezim bez pripojenych ergometru, API vrati cistou chybu `400` s vysvetlenim misto interní chyby serveru.

## PM3 a CSAFE

Projekt obsahuje pripravenou transportni vrstvu pro CSAFE framing a serial komunikaci:

- [backend/pm3/csafe.py](/home/stulda/projekty/letohry-lode/backend/pm3/csafe.py) vytvari a dekoduje CSAFE ramecky.
- [backend/pm3/device.py](/home/stulda/projekty/letohry-lode/backend/pm3/device.py) posila pozadavek `GET_WORKOUT_DATA` a mapuje odpoved na elapsed time, distance, split, stroke rate a watts.

Poznamka: konkretni PM3 firmware muze vracet ruzne varianty payloadu. Realny adapter je proto oddeleny od zbytku aplikace a parser lze rozsirit bez zasahu do frontendove nebo race logiky.

Pro pripravu na skutecny hardware backend navic:

- zkousi autodetekci PM3 portu podle USB descriptoru
- podporuje opakovane pokusy o pripojeni pres `ROWING_SERIAL_CONNECT_RETRIES`
- umoznuje explicitni override portu pres `ROWING_PORT_1` a `ROWING_PORT_2`
- drzi mock rychlost a countdown konfigurovatelne, aby sla aplikace rozumne testovat i bez ergometru
- umi logovat surove PM3 ramecky do [data/pm3-diagnostics.log](/home/stulda/projekty/letohry-lode/data)

## Frontend

- canvas vykresluje tri drahy, pohyb lodi a cilovou caru
- scoreboard ukazuje metry, split, SPM, cas, naskok a bonusove body
- tema `river`, `lake` a `night`
- zvuky jsou generovane v prohlizeci pres Web Audio API, takze aplikace zustava offline a bez asset pipeline
- historie vysledku jde stahnout jako CSV jednim tlacitkem z UI
- leaderboard i PM3 diagnosticky log jdou stahnout jednim tlacitkem z UI

## Offline provoz

- backend a frontend bez cloudovych zavislosti
- SQLite jako defaultni uloziste v [data/race_history.db](/home/stulda/projekty/letohry-lode/data)
- pro vyvoj bez hardware lze vse spustit s mock PM3 adapterem

## Rozsireni

- multiplayer pres LAN: sdilet websocket stav a synchronizovat start mezi vice Raspberry Pi
- mobilni ovladani: pridat jednoduchy ovladaci pohled nad stavajici REST API
- integracni REST API: autentizace a webhooky pro externi sportovni systemy

## CSV export

Historii vysledku lze exportovat i mimo UI:

```bash
curl -L "http://127.0.0.1:8000/api/history/export?distance_m=1000&player_name=Alice" -o race-history.csv
```

Podporovane filtry:

- `distance_m`
- `player_name`

Leaderboard lze exportovat samostatne:

```bash
curl -L "http://127.0.0.1:8000/api/leaderboard/export?distance_m=1000&limit=10" -o leaderboard.csv
```

## PM3 diagnostika

Diagnosticky rezim je zapnuty defaultne a zapisuje JSONL log surovych PM3 udalosti do [data/pm3-diagnostics.log](/home/stulda/projekty/letohry-lode/data).

Pouzitelne endpointy:

- `GET /api/diagnostics/status`
- `GET /api/diagnostics/events?limit=50`
- `GET /api/diagnostics/export`

V pripade potreby ho vypnes pres:

```bash
export ROWING_DIAGNOSTICS_ENABLED=0
```

Pro prvni zapojeni PM3 je pripraveny detailni checklist v [PM3_FIRST_RUN_CHECKLIST.md](/home/stulda/projekty/letohry-lode/PM3_FIRST_RUN_CHECKLIST.md) a sberovy skript v [scripts/collect_pm3_diagnostics.sh](/home/stulda/projekty/letohry-lode/scripts/collect_pm3_diagnostics.sh).

Automaticky sber diagnostiky:

```bash
chmod +x scripts/collect_pm3_diagnostics.sh
./scripts/collect_pm3_diagnostics.sh
```

## systemd a kiosk na Raspberry Pi

Pripravil jsem hotove soubory v [deploy/systemd/letohry-lode.service](/home/stulda/projekty/letohry-lode/deploy/systemd/letohry-lode.service), [deploy/systemd/letohry-lode-kiosk.service](/home/stulda/projekty/letohry-lode/deploy/systemd/letohry-lode-kiosk.service), [deploy/systemd/install-kiosk.sh](/home/stulda/projekty/letohry-lode/deploy/systemd/install-kiosk.sh) a [deploy/kiosk/start-kiosk.sh](/home/stulda/projekty/letohry-lode/deploy/kiosk/start-kiosk.sh).

Predpoklady:

- projekt je naklonovany v ceste, kterou predas instalacnimu skriptu
- virtualenv je v dane slozce projektu v `.venv`
- instalacni skript vyrenderuje spravneho uzivatele i domovsky adresar podle aktualniho prostredi
- v systemu je nainstalovany `chromium` nebo `chromium-browser`

Instalace sluzeb:

```bash
cd /home/pi/letohry-lode
chmod +x deploy/systemd/install-kiosk.sh deploy/kiosk/start-kiosk.sh
./deploy/systemd/install-kiosk.sh /home/pi/letohry-lode
```

Kontrola:

```bash
systemctl status letohry-lode.service
systemctl status letohry-lode-kiosk.service
journalctl -u letohry-lode.service -f
```

## Manualy k obsluze

Pripravil jsem samostatne zdrojove manualy v [docs/manuals/01-zapojeni-a-instalace.md](/home/stulda/projekty/letohry-lode/docs/manuals/01-zapojeni-a-instalace.md), [docs/manuals/02-manual-obsluhy.md](/home/stulda/projekty/letohry-lode/docs/manuals/02-manual-obsluhy.md), [docs/manuals/03-pravidla-zavodu.md](/home/stulda/projekty/letohry-lode/docs/manuals/03-pravidla-zavodu.md), [docs/manuals/04-rychly-tahak-obsluhy.md](/home/stulda/projekty/letohry-lode/docs/manuals/04-rychly-tahak-obsluhy.md), [docs/manuals/05-manual-pro-verejnost.md](/home/stulda/projekty/letohry-lode/docs/manuals/05-manual-pro-verejnost.md), [docs/manuals/06-interni-provozni-manual.md](/home/stulda/projekty/letohry-lode/docs/manuals/06-interni-provozni-manual.md) a [docs/manuals/07-manual-pro-navstevniky-jednoduse.md](/home/stulda/projekty/letohry-lode/docs/manuals/07-manual-pro-navstevniky-jednoduse.md).

PDF soubory se generuji skriptem [scripts/generate_manual_pdfs.py](/home/stulda/projekty/letohry-lode/scripts/generate_manual_pdfs.py):

```bash
source .venv/bin/activate
python scripts/generate_manual_pdfs.py
```

Vystup je ulozen do slozky `docs/pdf/`.

Generator pouziva vlozene Unicode fonty pro cestinu a pokud je v koreni projektu dostupne [logo.svg](/home/stulda/projekty/letohry-lode/logo.svg), prevede ho lokalne do PNG a prida ho na titulni stranu PDF manualu.

Titulni metadata akce lze menit v [docs/manuals/manual-metadata.json](/home/stulda/projekty/letohry-lode/docs/manuals/manual-metadata.json).

Generator vytvari i specialni varianty:

- verejna varianta v `docs/pdf/10-manual-pro-verejnost.pdf`
- interni varianta v `docs/pdf/11-interni-provozni-manual.pdf`
- jednorankovy tiskovy tahak v `docs/pdf/04-rychly-tahak-obsluhy.pdf`
- jednoducha navstevnicka varianta v `docs/pdf/12-jednoduchy-manual-pro-navstevniky.pdf`

## Dalsi kroky pro realny hardware

1. Doladit `GET_WORKOUT_DATA` parser podle konkretniho PM3/CSAFE dumpu.
2. Doplnit rozpoznani PM3 podle konkretniho USB VID/PID, az budou znama data z realneho hardware.
3. Po pripojeni ergometru zkontrolovat obsah [data/pm3-diagnostics.log](/home/stulda/projekty/letohry-lode/data) a doladit parser odpovedi.