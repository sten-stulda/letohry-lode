Jsi senior fullstack developer a expert na Python, realtime komunikaci a vizualizaci dat.

Navrhni a vytvoř kompletní open-source projekt pro Raspberry Pi, který propojí 2 veslařské trenažéry Concept2 s monitorem PM3 přes USB a zobrazí realtime závod dvou lodí na obrazovce.

Cíl aplikace:
Motivující soutěžní aplikace pro indoor rowing, která bude zobrazovat dvě virtuální lodě pohybující se po trati 500–2000 m podle skutečných dat z trenažérů.

Hardware:
- 2× Concept2 Model D nebo podobný
- monitor PM3
- připojení přes USB-B kabel
- Raspberry Pi 4 nebo 5
- 1 monitor nebo TV přes HDMI

Funkční požadavky:

1. Realtime závod
- 2 hráči současně
- délka tratě:
  - 500 m
  - 1000 m
  - 2000 m
- lodě se pohybují podle distance z PM3
- zobraz:
  - pozici lodí
  - vzdálenost v metrech
  - tempo (split)
  - stroke rate
  - aktuální náskok
  - čas závodu
- po dokončení zobraz:
  - pořadí
  - finální čas
  - rozdíl mezi hráči

2. Ghost režim
- možnost závodit proti:
  - předchozímu výkonu
  - osobnímu rekordu
- ghost loďka jede podle uložených dat

3. Interval režim
- intervaly typu:
  - 30s sprint / 30s pauza
  - 1 min sprint / 1 min pauza
- countdown timer
- vizuální indikace fáze

4. Gamifikace
- bonusové body za:
  - konstantní tempo
  - sprint v posledních 100 m
  - dosažení cílového tempa
- achievement systém:
  - první závod
  - osobní rekord
  - 10 závodů
  - 10000 m celkem

5. Leaderboard
- lokální databáze SQLite nebo PostgreSQL
- ukládání:
  - jméno hráče
  - čas
  - datum
  - délka tratě
- top 10 výsledků

6. Uživatelské rozhraní
- fullscreen režim vhodný pro TV
- jednoduché ovládání:
  - start
  - reset
  - výběr tratě
- velké prvky UI
- čitelné na vzdálenost 2–3 m

7. Vizuální styl
- animace lodí na vodě
- progress track
- cílová čára
- jednoduchá grafika
- minimální nároky na GPU
- možnost změnit téma:
  - řeka
  - jezero
  - noc

8. Zvuky
- start signal
- finish sound
- countdown

Technické požadavky:

Komunikace s PM3:
- použij CSAFE protokol
- komunikace přes USB serial
- čti:
  - elapsed time
  - distance
  - pace
  - stroke rate
  - watts pokud dostupné
- polling minimálně 4× za sekundu

Backend:
- Python 3.11+
- FastAPI nebo Flask
- websocket pro realtime data
- struktura projektu:
  backend/
  frontend/
  data/

Frontend:
- HTML5 canvas nebo SVG
- jednoduchá animace lodí
- realtime update přes websocket
- žádný heavy framework
- můžeš použít:
  vanilla JS
  nebo Vue
  nebo React (lightweight)

Databáze:
- SQLite default
- možnost PostgreSQL
- ukládat historii jízd

API endpointy:
GET /api/status
GET /api/race
POST /api/start
POST /api/reset
GET /api/history

Architektura:
- oddělit:
  modul pro čtení PM3
  modul pro logiku závodu
  modul pro vizualizaci
- připravit tak, aby šlo přidat další trenažéry

Výstup:
1. struktura projektu
2. seznam závislostí
3. instalační kroky pro Raspberry Pi
4. ukázkový kód pro čtení PM3
5. backend server
6. websocket komunikace
7. frontend vizualizace závodu
8. jednoduchá grafika lodí
9. ukládání výsledků
10. README.md

Důležité:
- aplikace musí fungovat offline
- jednoduché spuštění jedním příkazem
- optimalizované pro Raspberry Pi
- minimální latence
- robustní komunikace s USB

Bonus:
navrhni i rozšíření:
- multiplayer přes LAN
- mobilní ovládání
- export CSV
- REST API pro integraci

Výsledek napiš jako kompletní projekt připravený k implementaci.