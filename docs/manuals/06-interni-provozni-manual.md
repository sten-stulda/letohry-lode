# Interní provozní manuál

## Účel dokumentu

Tento dokument je určen pro interní obsluhu, správce akce a technický dohled. Shrnuje provozní minimum potřebné pro hladké spuštění, obsluhu během závodu a řešení závad.

## Před otevřením akce

- zkontrolujte zapojení HDMI, napájení a USB kabelů PM3
- spusťte aplikaci a ověřte otevření hlavní stránky
- proveďte jeden krátký test v mock režimu
- ověřte export CSV a dostupnost diagnostiky

## Během akce

- zadávejte správná jména hráčů
- po každé jízdě potvrďte výsledek a dejte `Reset`
- sledujte, zda obě dráhy hlásí data
- při chybě nejprve zkontrolujte kabely a stav PM3

## Po skončení bloku jízd

- exportujte historii do CSV
- exportujte leaderboard do CSV
- při technických potížích stáhněte diagnostický log PM3

## Kdy použít diagnostiku

- když jedna dráha neposílá data
- když se objevují nesmyslné hodnoty vzdálenosti nebo tempa
- když start bez mock režimu selže
- když dochází k náhodnému odpojování zařízení

## Kritické provozní body

- nikdo nesmí během závodu manipulovat s kabeláží
- Raspberry Pi musí být umístěné mimo dosah účastníků
- po každé změně tratě nebo režimu proveďte reset stavu

## Doporučený archiv po akci

- historie výsledků CSV
- leaderboard CSV
- případný PM3 diagnostický log
- stručná poznámka o vzniklých technických problémech