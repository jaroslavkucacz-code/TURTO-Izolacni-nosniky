# TURTO – technické prvky

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.2.0**

TURTO je lokální Windows aplikace pro jednu společnou **AKCI** a více produktových oblastí. Aktuálně jsou aktivní:

- **Izolační nosníky** – Dekodér / Návrh / Záměny
- **Smykové trny** – Dekodér / Návrh / Záměny

## Co znamená verze 2.2.0

2.2.0 je stabilizační a úklidové vydání. **Nemění statická pravidla, katalogové hodnoty ani databázi AKCÍ.** Hlavním cílem je zjednodušit další vývoj:

- aktuální runtime má stabilní vstupní moduly místo přímých vazeb na názvy jednotlivých hotfix verzí,
- z aktuální větve byly odstraněny staré build workflowy a dočasné balíčkové fragmenty,
- release proces má automatickou kontrolu syntaxe, SHA-256, commit-pinned URL a povinných souborů,
- historické migrační nástroje jsou oddělené v `legacy/`,
- technická architektura a pravidla vydávání jsou zdokumentovaná.

Podrobnosti: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) a [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## Online aktualizace

V běžně funkční aplikaci použijte tlačítko **Aktualizace**. Aktualizátor:

1. načte `update_manifest.json` přednostně přes GitHub API,
2. stahuje soubory z adres připnutých na konkrétní commit,
3. ověří každý soubor pomocí SHA-256,
4. vytvoří lokální zálohu měněných souborů v `.update_backup`,
5. nahradí pouze soubory uvedené v manifestu a TURTO znovu spustí.

`actions.sqlite3` se tímto mechanismem nepřepisuje.

## Když se TURTO nespustí

V kořeni repozitáře zůstává nouzová cesta:

- `OPRAVIT_TURTO.bat`
- `OPRAVIT_TURTO.ps1`

Je určena pouze pro situaci, kdy aplikace spadne ještě před dosažením běžného tlačítka **Aktualizace**. Nouzová oprava nemění databázi AKCÍ.

## Historický převod v0.4.0 / v0.5.0

Kořenový `00_INSTALOVAT_TURTO.bat` zůstává jako kompatibilní spouštěč původního jednorázového převodu na verzi 0.5.1. Vlastní historická logika a payload jsou přesunuty do `legacy/migration_v051/`.

Pro současné instalace 2.x tento převod nepoužívejte.

## Vývoj a kontrola vydání

Aktuální větev používá jediný CI workflow:

```text
.github/workflows/ci.yml
```

Kontrolu lze spustit i lokálně:

```text
python tools/verify_release.py
```

Kontrola odmítne mimo jiné:

- release URL odkazující na `main` místo konkrétního commitu,
- nesouhlas SHA-256,
- duplicitní nebo nebezpečné cílové cesty,
- syntakticky neplatný modul aktuálního release,
- návrat historických build artefaktů do kořene repozitáře.

## Důležité upozornění

TURTO je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
