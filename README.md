# TURTO – technické prvky

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.2.2**

TURTO je lokální Windows aplikace pro jednu společnou **AKCI** a více produktových oblastí. Aktuálně jsou aktivní:

- **Izolační nosníky** – Dekodér / Návrh / Záměny
- **Smykové trny** – Dekodér / Návrh / Záměny

## TURTO 2.2.2

2.2.2 sjednocuje práci s posuvností smykových trnů v Dekodéru, Návrhu, Záměnách, importu z výkazu i PDF.

- **jednosměrný** = podélný posun ve směru osy trnu,
- **obousměrný** = podélný + příčný posun,
- Schöck `SLD` / `LD` jsou vedeny jako jednosměrné a `SLD-Q` / `LD-Q` jako obousměrné,
- historické zápisy `SLD-Q 40`, `SLD Q 40` i `SLD 40 Q` se interpretují stejně,
- Ancon / Leviat `ESDQ`, `HLDQ`, `DSDQ`, `DSDSQ` jsou obousměrné; varianty bez Q jednosměrné,
- neověřená varianta `E-HLDQ` se už automaticky nevytváří,
- záměna zachovává požadovanou posuvnost zdrojového trnu,
- nový regresní test pohybu běží v Linux i Windows CI.

Tabulkové únosnosti, statická pravidla a databáze AKCÍ se touto verzí nemění.

## TURTO 2.2.1

2.2.1 pokračuje v technickém úklidu 2.2.0 a soustředí se na **spouštění, recovery a bezpečnost aktualizací**. Statická pravidla, katalogové hodnoty ani data AKCÍ se nemění.

- `app.pyw` je obecný aktuální bootstrap; nouzová cesta už není svázaná s označením 2.1.2,
- aktuální runtime používá marker `.turto_runtime_current.ok` a obecný diagnostický log `startup.log`,
- `OPRAVIT_TURTO` obnovuje stejný ověřený bootstrap a updater jako online release,
- recovery zapisuje do `recovery.log` a před změnou spouštěcí vrstvy vytváří vlastní zálohu,
- updater nejprve ověří a zazálohuje všechny měněné soubory a při chybě provede rollback,
- `actions.sqlite3` je výslovně chráněný soubor a release manifest jej nesmí aktualizovat,
- CI kontroluje vazbu manifest → bootstrap → runtime installer → recovery včetně SHA-256.

## Co přinesla verze 2.2.0

2.2.0 zahájila stabilizaci a úklid repozitáře:

- aktuální runtime dostal stabilní vstupní moduly místo dalších přímých vazeb na hotfix verze,
- z aktivní větve byly odstraněny staré build workflowy a dočasné balíčkové fragmenty,
- historické migrační nástroje byly odděleny do `legacy/`,
- vznikl jediný aktivní CI workflow a automatická kontrola release manifestu,
- byla zdokumentována architektura a pravidla vydávání.

Podrobnosti: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) a [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## Online aktualizace

V běžně funkční aplikaci použijte tlačítko **Aktualizace**. Aktualizátor:

1. načte `update_manifest.json` přednostně přes GitHub API,
2. zkontroluje cílové cesty a odmítne chráněné `actions.sqlite3`,
3. stáhne soubory z adres připnutých na konkrétní commit a ověří SHA-256,
4. vytvoří časově označenou zálohu všech měněných souborů v `.update_backup`,
5. nahradí programové soubory přes dočasné soubory,
6. při chybě obnoví předchozí stav z připravené zálohy,
7. po úspěchu zapíše verzi/runtime marker a TURTO znovu spustí.

Průběh samotné aplikace aktualizace se zapisuje do `update_apply.log`.

## Když se TURTO nespustí

V kořeni repozitáře je nouzová cesta:

- `OPRAVIT_TURTO.bat`
- `OPRAVIT_TURTO.ps1`

Používá se pouze tehdy, když aplikace spadne ještě před dosažením běžného tlačítka **Aktualizace**. Oprava:

1. vybere nebo rozpozná instalační složku TURTO,
2. zazálohuje stávající spouštěcí soubory,
3. stáhne a SHA-256 ověří aktuální `app.pyw` a `updater.py`,
4. vynutí kontrolovanou obnovu runtime při následujícím startu,
5. pokusí se TURTO znovu spustit.

Nouzová oprava nemění databázi AKCÍ. Diagnostika je v `recovery.log`; pokud selže následný start aplikace, podrobnosti jsou v `startup.log`.

## Historický převod v0.4.0 / v0.5.0

Kořenový `00_INSTALOVAT_TURTO.bat` zůstává jako kompatibilní spouštěč původního jednorázového převodu na verzi 0.5.1. Vlastní historická logika a payload jsou v `legacy/migration_v051/`.

Pro současné instalace 2.x tento převod nepoužívejte.

## Vývoj a kontrola vydání

Aktuální větev používá jediný CI workflow:

```text
.github/workflows/ci.yml
```

Kontrolu lze spustit i lokálně:

```text
python tools/verify_release.py
python tools/verify_shear_movement.py
```

Kontrola odmítne mimo jiné:

- release URL odkazující na `main` místo konkrétního commitu,
- nesouhlas SHA-256,
- duplicitní nebo nebezpečné cílové cesty,
- pokus zahrnout `actions.sqlite3` do online aktualizace,
- rozpor mezi manifestem, bootstrapem, runtime installerem a recovery,
- chybnou interpretaci Q variant a neověřenou E-HLDQ,
- syntakticky neplatný modul aktuálního release,
- návrat historických build artefaktů do kořene repozitáře.

## Důležité upozornění

TURTO je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
