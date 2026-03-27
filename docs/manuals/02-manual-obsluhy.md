# Uživatelský manuál obsluhy

## Účel dokumentu

Tento manuál je určen pro obsluhu akce, trenéry nebo pořadatele, kteří budou aplikaci běžně používat při tréninku, prezentaci nebo závodě.

## Co aplikace umí

- dva hráči závodí současně
- volba tratě 500 m, 1000 m nebo 2000 m
- ghost režim
- intervalový režim
- leaderboard a historie jízd
- export výsledků do CSV

## Popis obrazovky

### Levý panel

- jméno Hráč 1
- jméno Hráč 2
- výběr tratě
- výběr režimu
- výběr tématu
- volba mock PM3
- tlačítka Start a Reset

### Střed obrazovky

- animovaná vodní trať
- dvě lodě podle aktuálního postupu
- countdown před startem
- cílová čára

### Pravý panel

- leaderboard
- poslední jízdy
- export CSV
- diagnostický stav PM3

## Běžný postup obsluhy

### Spuštění aplikace

1. Zapněte Raspberry Pi a monitor.
2. Otevřete aplikaci nebo počkejte na kiosk režim.
3. Ověřte, že se zobrazuje hlavní stránka.

### Nastavení závodu

1. Zadejte jméno obou hráčů.
2. Vyberte délku tratě.
3. Vyberte režim závodu.
4. Pokud jsou připojené reálné PM3, vypněte `Mock PM3`.
5. Stiskněte `Start`.

### Během závodu

Obsluha sleduje:

- zda obě dráhy přijímají data
- jestli se mění metry, tempo a stroke rate
- zda countdown proběhne korektně

### Po dokončení závodu

- zkontrolujte pořadí
- zkontrolujte finální časy
- případně exportujte výsledky do CSV
- před dalším závodem použijte `Reset`

## Režimy aplikace

Výběr režimu určuje, jak aplikace vyhodnocuje jízdu, co se zobrazuje na obrazovce a jaký typ srovnání hráči dostanou.

### Realtime

Standardní přímý souboj dvou hráčů podle aktuálních dat z ergometru.

Co tento režim znamená:

- oba hráči závodí současně proti sobě
- každá loď se pohybuje podle skutečné vzdálenosti z příslušného PM3
- výsledkem je přímé pořadí v cíli

Co ovlivňuje:

- zobrazení obou živých lodí na trati
- průběžný náskok mezi hráči
- finální pořadí a výsledný čas obou drah

Kdy režim použít:

- při klasickém souboji dvou lidí
- na veřejných akcích a prezentacích
- když chcete jednoduchý a srozumitelný závodní formát

### Ghost

Hráč závodí proti předchozímu výkonu nebo osobnímu rekordu.

Co tento režim znamená:

- jedna loď je živý hráč a druhá je referenční ghost loď
- ghost loď nečte živá data z druhého ergometru, ale jede podle uloženého výkonu
- ghost může představovat předchozí jízdu nebo osobní rekord

Co ovlivňuje:

- na obrazovce se zobrazuje srovnání hráče s historickým výkonem
- výsledkem není přímý souboj dvou živých soupeřů, ale porovnání proti cílovému tempu
- ghost pomáhá udržet rytmus a odhadnout, zda hráč zrychluje nebo ztrácí

Kdy režim použít:

- při individuálním tréninku
- když chcete motivovat hráče k překonání vlastního maxima
- když máte k dispozici jen jednoho aktivního závodníka

Na co dát pozor:

- ghost je závislý na tom, zda je v historii uložen vhodný předchozí výsledek
- bez uložených dat se použije náhradní referenční tempo

### Interval

Používá se pro tréninkové jednotky se střídáním sprintu a odpočinku.

Co tento režim znamená:

- závodní trať není hlavní cíl, důležité je střídání pracovních a odpočinkových úseků
- aplikace zobrazuje fázi sprint nebo odpočinek podle nastaveného intervalu
- tento režim je vhodný hlavně pro organizovaný trénink, ne pro čisté závodní pořadí

Co ovlivňuje:

- zobrazování aktuální fáze intervalu
- chování countdownu a orientaci obsluhy během série opakování
- interpretaci výsledku, protože důraz je na rytmus tréninku, ne pouze na čas v cíli

Kdy režim použít:

- při klubovém tréninku
- při kondičním bloku sprint a pauza
- když chce trenér řídit intenzitu a strukturu jednotky

Na co dát pozor:

- před startem je potřeba jasně sdělit délku sprintu, délku odpočinku a počet opakování
- tento režim je vhodné hodnotit odděleně od klasického závodu na čas

## Co mění volba tratě

Volba tratě ovlivňuje několik věcí současně:

- délku závodu nebo cílovou vzdálenost
- délku zobrazeného postupu na trati
- vhodnost režimu pro typ akce
- interpretaci výsledků v leaderboardu

Doporučení:

- 500 m: krátký a atraktivní sprint pro veřejnost
- 1000 m: vyvážený formát pro většinu akcí
- 2000 m: výkonnostní nebo klubové srovnání

## Co znamenají údaje na obrazovce

### Vzdálenost

Udává, kolik metrů už hráč na trenažéru absolvoval. Je to hlavní údaj pro pohyb lodě po trati.

Co ovlivňuje:

- pozici lodě na obrazovce
- pořadí během závodu
- určení cíle a dokončení jízdy

### Tempo nebo split

Tempo ukazuje, za jaký čas by hráč urazil 500 metrů při aktuálním výkonu. Čím nižší čas, tím rychlejší jízda.

Příklad:

- `1:55 / 500 m` je rychlejší než `2:10 / 500 m`

Co ovlivňuje:

- průběžné hodnocení výkonu
- možnost sledovat, zda hráč drží rovnoměrné tempo
- bonusy za cílové nebo stabilní tempo

### Stroke rate

Stroke rate, často zkráceně SPM, znamená počet záběrů za minutu.

Co ovlivňuje:

- styl a rytmus jízdy
- orientační hodnocení intenzity výkonu
- některé bonusové body za vhodný rozsah frekvence

Poznámka:

- vyšší SPM nemusí vždy znamenat lepší výkon, důležité je spojení rytmu a síly záběru

### Watts

Watts vyjadřují aktuální výkon. Pokud je PM3 poskytuje, aplikace je může zobrazovat jako doplňkový údaj.

Co ovlivňují:

- detailnější pohled na sílu výkonu
- tréninkové vyhodnocení, zejména pro pokročilejší použití

### Náskok

Náskok ukazuje rozdíl mezi vedoucí lodí a soupeřem nebo referenční ghost lodí.

Co ovlivňuje:

- okamžitou orientaci, kdo vede
- motivaci závodníků v průběhu jízdy

## Jak číst výsledky po závodě

Po dokončení jízdy se na obrazovce a v historii objevují údaje, které je vhodné číst v tomto pořadí:

### 1. Pořadí

Pořadí říká, kdo dokončil zvolenou trať dříve. V režimu Realtime jde o hlavní závodní výsledek.

### 2. Finální čas

Finální čas ukazuje skutečný čas potřebný k dokončení trati. Tento údaj je rozhodující pro leaderboard a porovnání mezi jízdami.

### 3. Rozdíl mezi hráči

Rozdíl ukazuje, o kolik byl vítěz rychlejší nebo jak velký byl odstup v cíli.

### 4. Bonusové body

Bonusové body nejsou hlavním závodním výsledkem, ale doplňují hodnocení o styl a průběh jízdy.

### 5. Achievementy

Achievementy slouží jako motivační vrstva. Informují například o osobním rekordu nebo dosažení určitého počtu jízd.

### Jak interpretovat výsledek podle režimu

- Realtime: rozhodující je pořadí a čas v cíli
- Ghost: důležité je, zda hráč překonal referenční výkon
- Interval: důležitější je dodržení struktury tréninku než čisté pořadí

## Doporučená obsluha při veřejné akci

- před prvním startem vyzkoušejte jeden zkušební závod v mock režimu
- před každou jízdou ověřte správně zadaná jména
- po každém závodě použijte `Reset`
- při větší návštěvnosti exportujte výsledky průběžně

## Export výsledků

### Historie jízd

- tlačítko `Export CSV` exportuje historii výsledků
- export lze filtrovat podle nastavené tratě a jména hráče v poli Hráč 1

### Leaderboard

- tlačítko `Leaderboard CSV` exportuje aktuální žebříček

## Kdy použít Reset

Reset použijte vždy, když:

- končí jedna jízda a začíná další
- měníte režim nebo délku tratě
- došlo k chybě startu
- mění se dvojice hráčů

## Bezpečnost a provozní pravidla

- obsluha nesmí manipulovat s kabely během jízdy
- mokré ruce a otevřené konektory představují riziko
- nenechávejte kabely volně přes prostor pohybu hráčů
- Raspberry Pi i TV musí být stabilně umístěné

## Kdy volat servis nebo administrátora

- pokud jeden z PM3 zmizí ze systému
- pokud se opakovaně zobrazuje chyba připojení
- pokud aplikace přijímá data jen z jedné dráhy
- pokud jsou zjevně nesmyslné hodnoty tempa nebo vzdálenosti