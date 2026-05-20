# PM3 First Run Checklist

Tento checklist je urceny pro prvni realne pripojeni dvou Concept2 PM3 monitoru k aplikaci.

## 1. Pred pripojenim hardware

Over, ze projekt bezi bez hardware:

```bash
cd /home/stulda/projekty/letohry-lode
source .venv/bin/activate
pytest
python run.py
```

Ocekavany stav:

- aplikace nabehne na `http://127.0.0.1:8000`
- mock zavod lze spustit z UI
- `GET /api/status` vraci `200`

## 2. Pripojeni PM3 pres USB

Pripoj oba PM3 monitory pres USB-B kabely a zkontroluj, ze je Linux vidi:

Pokud bezis ve WSL na Windows, PM3 se v Linuxu samy neobjevi. Nejdriv je pripoj do WSL pres `usbipd-win` z Windows terminalu s admin pravy:

```powershell
usbipd list
usbipd bind --busid X-Y
usbipd attach --wsl --busid X-Y
```

Praktictejsi varianta je pouzit pripraveny skript (Windows PowerShell jako Administrator):

```powershell
./scripts/attach_pm3_to_wsl.ps1
```

To same proved pro oba PM3. Teprve potom ma smysl kontrolovat `hidraw` nebo spoustet backend ve WSL.

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
python - <<'PY'
from serial.tools import list_ports
for port in list_ports.comports():
    print(port.device, port.description, port.manufacturer, port.product, port.hwid)
PY
```

Poznamenej si:

- nazvy portu
- popis zarizeni
- USB VID/PID, pokud jsou videt v `hwid`
- pokud bezis ve WSL a nic nevidis, zkontroluj znovu `usbipd list` na Windows hostu

## 3. Spusteni bez mock rezimu

Pokud autodetekce nenajde porty sama, nastav je rucne:

```bash
export ROWING_PORT_1=/dev/ttyUSB0
export ROWING_PORT_2=/dev/ttyUSB1
export ROWING_DIAGNOSTICS_ENABLED=1
python run.py
```

Pak over stav:

```bash
curl http://127.0.0.1:8000/api/status
curl http://127.0.0.1:8000/api/diagnostics/status
curl http://127.0.0.1:8000/api/diagnostics/events?limit=20
```

Ocekavany stav:

- `serial_ports` obsahuji skutecne porty PM3
- diagnostika je `enabled: true`
- po pokusu o start se objevi prvni udalosti v diagnostice

## 4. Prvni realny pokus o zavod

V UI:

- vypni `Mock PM3`
- vyber `500 m`
- zadej dve jmena
- spust zavod

Pokud se zavod nerozbehne, zkontroluj:

- text chyby v UI
- obsah `GET /api/diagnostics/events?limit=50`
- obsah [data/pm3-diagnostics.log](/home/stulda/projekty/letohry-lode/data)

## 5. Stazeni diagnostiky pro ladeni parseru

Pouzij pripraveny skript:

```bash
./scripts/collect_pm3_diagnostics.sh
```

Nebo z Windows PowerShellu:

```powershell
./scripts/collect_pm3_diagnostics.ps1
```

Nebo rucne:

```bash
curl -L http://127.0.0.1:8000/api/diagnostics/export -o pm3-diagnostics.log
curl -L http://127.0.0.1:8000/api/diagnostics/events?limit=200 -o pm3-events.json
```

## 6. Co zkontrolovat v logu

Zajimaji te hlavne tyto typy udalosti:

- `connect`
- `tx`
- `rx`
- `rx_parsed`
- `rx_invalid`
- `rx_empty`
- `connect_error`

Interpretace:

- `connect_error`: problem s portem nebo opravnenim
- `rx_empty`: PM3 nevraci zadna data nebo je spatny polling/baudrate
- `rx_invalid`: data prisla, ale parser nebo framing neodpovida realnemu payloadu
- `rx_parsed`: komunikace funguje, je potreba jen potvrdit mapovani hodnot

## 7. Co mi poslat pro dalsi doladeni

Pokud bude potreba doladit parser, nejuzitecnejsi jsou:

- vystup `python - <<'PY' ... list_ports ... PY`
- prvnich 20-50 radku z `pm3-diagnostics.log`
- jestli monitor odpovida konzistentne nebo jen obcas
- ktere hodnoty v UI davaji smysl a ktere ne

## 8. Pravdepodobne dalsi upravy po prvnim pripojeni

- zpresnit rozpoznani PM3 podle konkretniho USB VID/PID
- upravit parser v [backend/pm3/device.py](/home/stulda/projekty/letohry-lode/backend/pm3/device.py) podle realne struktury payloadu
- pripadne upravit baudrate nebo timeouty