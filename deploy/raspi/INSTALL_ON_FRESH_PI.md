# Instalace na čerstvě nainstalované Raspberry Pi

## Doporučený přístup

Pro tento projekt je lepší použít dvoukrokový postup:

1. připravit SD kartu přes Raspberry Pi Imager
2. po prvním bootu spustit bootstrap skript z projektu

To je praktičtější než vyrábět vlastní image SD karty hned na začátku.

Důvod:

- Raspberry Pi Imager už umí přednastavit SSH, Wi‑Fi, hostname, uživatele a lokalizaci
- bootstrap skript se jednoduše udržuje v repozitáři
- když se změní projekt nebo závislosti, upraví se jen skript, ne celá image
- vlastní image dává smysl až ve chvíli, kdy budeš nasazovat více stejných kusů Raspberry Pi

## Kdy dává smysl vlastní image SD karty

Vlastní image je vhodná, pokud:

- budeš připravovat více zařízení najednou
- chceš úplně bezobslužné nasazení
- potřebuješ jednotný firemní nebo klubový build

V takové chvíli má smysl řešit:

- Raspberry Pi Imager s vlastním post-install postupem
- cloud-init nebo first-boot provisioning
- pi-gen nebo jiný nástroj pro stavbu vlastního OS image

## Doporučená základní image

Použij:

- Raspberry Pi OS Bookworm
- varianta s Desktopem

Desktop varianta je vhodnější, protože projekt počítá s kiosk režimem v Chromium.

## Co nastavit už v Raspberry Pi Imageru

Před zapsáním SD karty nastav v Imageru:

- hostname
- uživatele `pi` nebo jiného, pokud tomu upravíš service soubory
- SSH
- Wi‑Fi, pokud chceš vzdálenou správu
- locale a časové pásmo
- klávesnici

## Instalace po prvním bootu

Pokud už je repozitář v Raspberry Pi lokálně:

```bash
cd /home/pi/letohry-lode
chmod +x deploy/raspi/bootstrap-fresh-pi.sh
./deploy/raspi/bootstrap-fresh-pi.sh /home/pi/letohry-lode
```

Pokud repozitář na Raspberry Pi ještě není:

```bash
git clone https://github.com/sten-stulda/letohry-lode.git /home/pi/letohry-lode
cd /home/pi/letohry-lode
chmod +x deploy/raspi/bootstrap-fresh-pi.sh
./deploy/raspi/bootstrap-fresh-pi.sh /home/pi/letohry-lode
```

Nebo jedním krokem, pokud chceš bootstrapu rovnou předat URL repozitáře:

```bash
bash deploy/raspi/bootstrap-fresh-pi.sh /home/pi/letohry-lode https://github.com/sten-stulda/letohry-lode.git main
```

Bootstrap umí použít i proměnné prostředí, takže můžeš mít URL a branch připravené předem:

```bash
export LETOHRY_REPO_URL=https://github.com/sten-stulda/letohry-lode.git
export LETOHRY_REPO_BRANCH=main
./deploy/raspi/bootstrap-fresh-pi.sh /home/pi/letohry-lode
```

Pokud `LETOHRY_REPO_URL` nenastavíš, bootstrap použije jako výchozí adresu právě `https://github.com/sten-stulda/letohry-lode.git`.

## Co bootstrap skript udělá

- nainstaluje systémové balíčky
- připraví desktop autologin pro kiosk režim
- vytvoří virtualenv
- nainstaluje Python závislosti
- nastaví spustitelnost pomocných skriptů
- nainstaluje a zapne systemd služby

Systemd služby se při instalaci vyrenderují podle skutečné cesty projektu a aktuálního uživatele. Nejsou tedy napevno vázané jen na `/home/pi/letohry-lode`.

## Lokální konfigurace mimo GitHub

Pro trvalé lokální nastavení, které nechceš držet v repozitáři, použij:

```bash
sudo cp /home/pi/letohry-lode/deploy/raspi/letohry-lode.env.example /etc/letohry-lode.env
sudo nano /etc/letohry-lode.env
sudo systemctl restart letohry-lode.service
```

Typicky sem patří:

- pevně nastavené PM3 porty
- změna portu aplikace
- vypnutí nebo zesílení diagnostiky
- jiné lokální runtime override

## Aktualizace z GitHubu

Jakmile je projekt na Raspberry Pi jednou nasazený, další update můžeš dělat tímto skriptem:

```bash
cd /home/pi/letohry-lode
chmod +x deploy/raspi/update-from-github.sh
./deploy/raspi/update-from-github.sh /home/pi/letohry-lode
```

Volitelně:

```bash
INSTALL_DEV_REQUIREMENTS=1 RUN_TESTS=1 ./deploy/raspi/update-from-github.sh /home/pi/letohry-lode main
```

Skript udělá:

- `git fetch` a `git pull --ff-only`
- aktualizaci Python závislostí
- volitelně testy
- znovunasazení systemd jednotek a restart služeb

## Co ověřit po instalaci

```bash
systemctl status letohry-lode.service
systemctl status letohry-lode-kiosk.service
curl http://127.0.0.1:8000/api/status
curl http://127.0.0.1:8000/api/diagnostics/status
```

## Doporučení pro první reálné nasazení

- nejdřív ověř kiosk a mock režim bez PM3
- až potom připoj oba PM3
- při prvním připojení použij [PM3_FIRST_RUN_CHECKLIST.md](/home/stulda/projekty/letohry-lode/PM3_FIRST_RUN_CHECKLIST.md)

## Shrnutí

Nejlepší varianta pro tento projekt teď je:

- SD kartu připravit přes Raspberry Pi Imager
- projekt nasadit z GitHubu a dokonfigurovat bootstrap skriptem
- průběžné změny tahat update skriptem přímo z repozitáře

To je nejrychlejší, nejméně křehké a zároveň snadno opakovatelné řešení.