# Rychlý tahák pro obsluhu

## Před jízdou

- zapnout Raspberry Pi a monitor
- ověřit otevření aplikace
- zkontrolovat oba PM3
- vypnout `Mock PM3`, pokud jedete na reálných ergometrech

## Start závodu

1. zadejte jména hráčů
2. vyberte trať
3. vyberte režim
4. stiskněte `Start`

## Během jízdy

- sledujte pohyb obou lodí
- kontrolujte metry, tempo a stroke rate
- při chybě závod přerušte a zkontrolujte připojení

## Po dojetí

- potvrdit výsledek
- případně exportovat CSV
- stisknout `Reset`

## Když je problém

- kabely PM3
- mock režim vs. reálný hardware
- `GET /api/diagnostics/status`
- export `GET /api/diagnostics/export`

## Adresa aplikace

- `http://127.0.0.1:8000`