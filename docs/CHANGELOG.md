# Changelog

## 2.2.5

Další sjednocení hierarchie záložek a kontextových akcí bez změny výpočtů.

- Dekodér / Návrh / Záměny používají podobnou pracovní hierarchii,
- dvojklik na řádek je sjednocen na **Detail prvku / Detail záměny**,
- u smykových trnů je převod Dekodér → Záměny pouze explicitním tlačítkem,
- akce nad řádky se aktivují podle aktuálního výběru,
- Delete používá standardní mazání vybraných řádků tam, kde je tato akce dostupná,
- Záměny izolačních nosníků mají explicitně přestavěnou lištu bez kolize tlačítka **Sloupce…**,
- vnitřní PDF export Záměn izolačních nosníků je skryt ve prospěch společného **Export PDF AKCE**,
- názvy výstupů jsou sjednocené na **Kopírovat pro Excel** a **Export Excel…**,
- servisní **Složka katalogů** a **Kontrola katalogů** byly přesunuty z hlavní hlavičky do **Nápověda > Data a zdroje**,
- přidána samostatná Linux/Windows regresní kontrola hierarchie a kontextových akcí.

Výpočtové jádro, katalogové hodnoty a databáze `actions.sqlite3` se nemění.

## 2.2.4

Sjednocení tabulek a pracovních záložek Izolační nosníky / Smykové trny.

- datové tabulky používají jednotné řazení kliknutím na záhlaví,
- pravé tlačítko v záhlaví nabízí řazení, posun, automatickou šířku, skrytí a správu sloupců,
- dialog **Sloupce…** ukládá pořadí, viditelnost a šířky,
- stejné ovládání se automaticky připojuje také k tabulkám v otevřených dialogových oknech,
- Smykové trny dostaly **Sloupce…**, přímý **Export Excel…** a jednotné **Kopírovat pro Excel**,
- z Dekodéru a Záměn smykových trnů odstraněno destruktivní **Vymazat vše**; v samostatném Návrhu zůstává,
- z Dekodéru izolačních nosníků skryt nadbytečný CSV export,
- ze Záměn izolačních nosníků odstraněn redundantní ruční refresh stejné společné AKCE,
- servisní akce HIT přesunuty z hlavního Návrhu do **Nápověda > Data a zdroje**,
- další dlouhé provozní vysvětlivky Záměn přesunuty do hromadné Nápovědy.

Výpočtové jádro, katalogové únosnosti a databáze `actions.sqlite3` se nemění.

## 2.2.3

Úklid hlavního rozhraní, našeptávač smykových trnů a oprava převodu Schöck Isokorb KL-O do záměn za HIT.

- dlouhé provozní popisky a vysvětlivky přesunuty do společné **Nápovědy** vpravo nahoře,
- technické zdroje, strany a katalogové hodnoty zůstávají v Detailu prvku,
- Smykové trny mají plovoucí našeptávač v Dekodéru i při ručním zadání zdrojového trnu v Záměnách,
- našeptávač zahrnuje Ancon / Leviat, současný Schöck Stacon a podporovaný archiv Schöck Dorn,
- pro ověřenou rodinu Schöck Isokorb T/XT KL-O se `CV1` překládá na 35 mm a `CV2` na 50 mm,
- KL-O se pro záměnu vyhodnocuje jako provedení s tlakovými ložisky HTE-Compact®,
- staré odvozené chyby záměny kvůli neznámému krytí/tlakovému přenosu se bezpečně resetují k novému přepočtu,
- přidán samostatný regresní test UI, autocomplete a Schöck KL-O na Linux i Windows.

Tabulkové únosnosti, katalogová data a databáze `actions.sqlite3` se nemění.

## 2.2.2

Kontrola a sjednocení posuvnosti smykových trnů bez změny tabulkových únosností.

- jednotné pojmy **Jednosměrný – podélný posun** a **Obousměrný – podélný + příčný posun**,
- Schöck SLD/LD = jednosměrné, SLD-Q/LD-Q = obousměrné,
- historické zápisy `SLD-Q 40`, `SLD Q 40` i `SLD 40 Q` se dekódují stejně,
- Ancon / Leviat ESDQ/HLDQ/DSDQ/DSDSQ = obousměrné, varianty bez Q = jednosměrné,
- TURTO už nevytváří neověřenou variantu `E-HLDQ`,
- import výkazu rozpoznává jednosměrný/obousměrný/dvousměrný/1-směr/2-směr/2D,
- posuvnost se sjednotila v Dekodéru, Návrhu, Záměnách a PDF,
- přidán samostatný regresní test pohybu pro Linux i Windows CI.

## 2.2.1

Pokračování technického úklidu bez změny statických pravidel, katalogových hodnot nebo dat AKCÍ.

- obecný aktuální bootstrap místo recovery navázané na verzi 2.1.2,
- obecné diagnostické soubory `startup.log` a `recovery.log`,
- aktuální runtime marker `.turto_runtime_current.ok`,
- recovery používá stejný commit-pinned `app.pyw` a `updater.py` jako online manifest,
- updater nejprve vytvoří úplnou zálohu měněných souborů a při chybě provede rollback,
- `actions.sqlite3` je explicitně chráněný cíl,
- CI kontroluje manifest, bootstrap, runtime installer, recovery, rollback, SHA-256 a syntaxi.

## 2.2.0

Technický úklid a stabilizace bez změny statických pravidel nebo katalogových dat.

- stabilní vstupní hranice pro smykové trny a Schöck Dorn,
- jeden aktuální CI workflow,
- automatická validace release manifestu,
- odstranění historických build artefaktů z aktuální větve,
- přesun starého převodu v0.4/v0.5 do `legacy/`,
- zjednodušená dokumentace architektury a release procesu.

## 2.1.5

- archivní VRd pro historické Schöck Dorn SLD/SLD-Q a kompletní LD/LD-Q,
- odstranění `cnom Schöck` z Dekodéru,
- archivní VRd lze použít jako požadavek záměny za Ancon nebo současný Schöck Stacon.

## 2.1.4

- sjednocení workflow smykových trnů s izolačními nosníky,
- hromadné vložení z výkazu,
- společné akce nad řádky,
- hromadné Záměny z Dekodéru.

## 2.1.3

- návrh HIT začíná bez automatického prázdného řádku,
- převod vybraného smykového trnu z Dekodéru do Záměn,
- opravený updater používající GitHub API pro načtení manifestu.

## 2.1.2

Stabilizační startovací základ po regresi 2.1.1.
