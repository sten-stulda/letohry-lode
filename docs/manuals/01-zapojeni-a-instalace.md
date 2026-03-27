# Manuál zapojení a instalace

## Účel dokumentu

Tento manuál popisuje fyzické zapojení sestavy, přípravu Raspberry Pi, první spuštění aplikace a základní kontrolu funkčnosti před ostrým provozem.

## Potřebné komponenty

- 2x veslařský trenažér Concept2 Model D nebo podobný model
- 2x monitor PM3
- 2x USB-B kabel pro připojení PM3
- 1x Raspberry Pi 4 nebo 5
- 1x HDMI monitor nebo TV
- napájení pro Raspberry Pi
- síťové připojení pouze pro servisní zásah nebo vzdálenou správu, provoz aplikace je offline

## Doporučené umístění

- Raspberry Pi umístěte mimo dosah potu, vody a mechanického kontaktu s obsluhou nebo závodníky.
- Kabely veďte po straně tak, aby nekřížily nástupní a výstupní prostor u trenažérů.
- Monitor nebo TV umístěte tak, aby na něj oba hráči viděli bez výrazného otáčení hlavy.
- Zajistěte dostatečné chlazení Raspberry Pi, zejména při delším provozu v kiosk režimu.

## Fyzické zapojení

### Krok 1: obrazovka

- Připojte Raspberry Pi k monitoru nebo TV přes HDMI.
- Zapněte monitor nebo TV a ověřte vstupní zdroj obrazu.

### Krok 2: PM3 monitory

- Každý PM3 připojte samostatným USB-B kabelem do Raspberry Pi.
- Nepoužívejte nekvalitní nebo příliš dlouhé kabely.
- Pokud je potřeba více portů nebo je napájení nestabilní, použijte napájený USB hub.

### Krok 3: napájení

- Připojte napájení Raspberry Pi.
- Počkejte na naběhnutí systému.

## Instalace aplikace

```bash
cd /home/pi/letohry-lode
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## První spuštění

```bash
cd /home/pi/letohry-lode
source .venv/bin/activate
python run.py
```

V prohlížeči otevřete:

```text
http://127.0.0.1:8000
```

## Kontrola, že systém vidí PM3

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
python - <<'PY'
from serial.tools import list_ports
for port in list_ports.comports():
    print(port.device, port.description, port.manufacturer, port.product, port.hwid)
PY
```

Pokud porty nevidíte:

- zkontrolujte kabely
- vyzkoušejte jiný USB port
- vyzkoušejte napájený USB hub
- restartujte Raspberry Pi

## Ruční nastavení portů

Pokud autodetekce nezafunguje, nastavte porty ručně:

```bash
export ROWING_PORT_1=/dev/ttyUSB0
export ROWING_PORT_2=/dev/ttyUSB1
export ROWING_DIAGNOSTICS_ENABLED=1
python run.py
```

## Kontrolní seznam před prvním reálným závodem

- aplikace se otevře v prohlížeči
- mock režim funguje
- oba PM3 jsou připojené a viditelné v systému
- `GET /api/status` vrací `200`
- `GET /api/diagnostics/status` vrací `enabled: true`

## Automatické spouštění na Raspberry Pi

Pro kiosk provoz použijte připravený skript:

```bash
cd /home/pi/letohry-lode
chmod +x deploy/systemd/install-kiosk.sh deploy/kiosk/start-kiosk.sh
./deploy/systemd/install-kiosk.sh /home/pi/letohry-lode
```

## Nejčastější problémy

### PM3 není nalezen

- zkontrolujte USB kabel
- zkontrolujte `ROWING_PORT_1` a `ROWING_PORT_2`
- projděte diagnostický log

### Zobrazení se neotevře ve fullscreen režimu

- ověřte, že je nainstalovaný `chromium` nebo `chromium-browser`
- zkontrolujte stav `letohry-lode-kiosk.service`

### Závod nejde spustit

- v UI ověřte, že není vypnutý mock režim bez připojeného PM3
- zkontrolujte text chyby a diagnostiku