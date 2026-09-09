# TURTO – technické prvky

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.2.8**

TURTO je lokální Windows aplikace pro jednu společnou **AKCI** a více produktových oblastí. Aktuálně jsou aktivní:

- **Izolační nosníky** – Dekodér / Návrh / Záměny
- **Smykové trny** – Dekodér / Návrh / Záměny

## Aktuální funkce

### Izolační nosníky
- dekódování katalogových označení,
- hromadné vložení z výkazu,
- návrh Leviat HIT,
- katalogové záměny s kontrolou geometrie, krytí, výšky, betonu, tlakového přenosu a únosností,
- bezpečné rozlišení geometrických variant OU / OD.

### Smykové trny
- Ancon / Leviat,
- Schöck Stacon + podporované historické Schöck Dorn,
- PohlCon HED / JDSD / JDSDQ,
- MAX FRANK Egcodorn / Egcodubel,
- jednosměrné a obousměrné varianty,
- Dekodér / Návrh / Záměny se společným ovládáním a hromadným vložením z výkazu.

### Společná AKCE
Dekódované prvky, návrhy a záměny obou produktových oblastí se ukládají společně v centrální AKCI. Databáze `actions.sqlite3` je při online aktualizacích chráněná a není součástí release manifestu.

## PDF

Od TURTO 2.2.8 používá hlavní tlačítko **Export PDF…** výběr rozsahu. Lze exportovat:

- celou AKCI,
- všechny Izolační nosníky,
- Izolační nosníky → Dekodér / Návrh / Záměny,
- všechny Smykové trny,
- Smykové trny → Dekodér / Návrh / Záměny.

Obecné vysvětlivky jsou soustředěné v **Nápovědě**, aby nezabíraly pracovní plochu. Technické údaje, katalogové zdroje, stavy a varování zůstávají v detailech a výsledcích.

## Online aktualizace

V běžně funkční aplikaci použijte **Aktualizace**. Aktualizátor:

1. načte `update_manifest.json` přednostně přes GitHub API,
2. odmítne chráněné cíle včetně `actions.sqlite3`,
3. stáhne soubory z adres připnutých na konkrétní commit a ověří SHA-256,
4. vytvoří zálohu měněných souborů v `.update_backup`,
5. nahradí soubory transakčně,
6. při chybě provede rollback,
7. po úspěchu zapíše verzi/runtime marker a program znovu spustí.

Průběh aktualizace se zapisuje do `update_apply.log`.

## Když se TURTO nespustí

V kořeni repozitáře je nouzová cesta:

- `OPRAVIT_TURTO.bat`
- `OPRAVIT_TURTO.ps1`

Nouzová oprava obnovuje ověřený bootstrap a updater, ale nemění databázi AKCÍ. Diagnostika je v `recovery.log`; chyba následného startu v `startup.log`.

## Vývoj a kontrola vydání

Aktivní CI je pouze:

```text
.github/workflows/ci.yml
```

Kontroluje mimo jiné:

- release manifest, SHA-256 a připnuté commit URL,
- bootstrap / runtime installer / recovery,
- ochranu `actions.sqlite3`,
- směr pohybu smykových trnů a historické Q varianty,
- záměny Schöck Isokorb a geometrii OU/OD,
- PohlCon a MAX FRANK,
- jednotné tabulky a ovládání,
- rozsah PDF exportu,
- Windows PowerShell recovery.

Hlavní dokumentace:

- `docs/ARCHITECTURE.md`
- `docs/RELEASE_PROCESS.md`
- `updates/<verze>/RELEASE_NOTES.txt`

Historické migrační nástroje jsou oddělené v `legacy/` a pro současné instalace 2.x se nepoužívají.

## Důležité upozornění

TURTO je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
