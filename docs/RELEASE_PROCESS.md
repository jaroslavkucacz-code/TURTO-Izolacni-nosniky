# Release proces TURTO

Tento postup je povinný pro online vydání od 2.2.0.

## 1. Pracovní větev

Změny se připravují mimo `main`, typicky `release/X.Y.Z` nebo `cleanup/X.Y.Z`.

## 2. Zmrazit obsah release

Nejdříve se dokončí všechny zdrojové soubory v `updates/X.Y.Z/`. Po zmrazení se už soubory, na které bude odkazovat manifest nebo bootstrap, nesmí měnit bez nového výpočtu hashů a nového pinned commitu.

Bootstrap `app.pyw` musí mít vlastní připnutý `INSTALLER_COMMIT` a `INSTALLER_SHA256` pro `runtime_installer.py`. Pokud se runtime installer změní, musí se přepočítat jeho SHA, aktualizovat bootstrap a bootstrap následně znovu zmrazit v novém commitu.

## 3. Syntax a statické kontroly

Spustit `python tools/verify_release.py`. Tato kontrola ověřuje:

- shodu `CURRENT_VERSION` a manifestu,
- strukturu a bezpečné cílové cesty manifestu,
- zákaz aktualizace `actions.sqlite3`,
- commit-pinned URL,
- SHA-256 zdrojových souborů,
- shodu manifestu s bootstrapem,
- shodu bootstrapu s `runtime_installer.py`,
- shodu recovery s `app.pyw` a `updater.py` z manifestu,
- přítomnost transakční zálohy/rollbacku v updateru,
- syntaxi Python souborů aktuálního release,
- základní hygienu repozitáře.

## 4. Commit-pinned URL

Každá URL programového souboru v manifestu musí mít tvar:

`https://raw.githubusercontent.com/<owner>/<repo>/<40-char-commit>/<path>`

Zakázáno je `/main/`, jiná větev, pohyblivý tag nebo URL bez konkrétního SHA.

Stejný princip platí pro `INSTALLER_COMMIT` bootstrapu a pro zdroje používané recovery/runtime installerem.

## 5. SHA-256

SHA-256 se počítá z **přesných bajtů souboru v připnutém commitu**. Nikdy se nesmí kombinovat URL ze staršího commitu a SHA-256 z novější pracovní kopie.

Pokud CI hlásí rozdíl mezi očekávaným a lokálním SHA-256, release se nesmí zveřejnit. Nejdříve se musí sjednotit připnutý commit, obsah souboru a hash.

## 6. Runtime layout

Manifest od 2.2.1 obsahuje `runtime_layout`. Stejnou hodnotu musí mít `RUNTIME_LAYOUT` v `app.pyw`.

Číslo layoutu se nemění s každým vydáním. Zvýší se pouze tehdy, když stávající lokální runtime už nelze považovat za kompletní pro nový bootstrap a je potřeba vynutit jeho obnovu.

## 7. Manifest je poslední změna release obsahu

`update_manifest.json` se připraví až poté, co jsou zdrojové soubory zmrazené. Potom musí `tools/verify_release.py` projít bez chyby.

Pokud se po vytvoření manifestu změní některý zdrojový soubor, musí se znovu připnout jeho nový commit, přepočítat SHA-256 a zopakovat kontrola.

## 8. Transakční aktualizace

Updater musí před změnou instalace:

1. validovat celý manifest,
2. stáhnout a ověřit všechny soubory,
3. zazálohovat všechny existující cíle do časově označené `.update_backup`,
4. měnit soubory přes dočasný soubor a atomické nahrazení,
5. při chybě obnovit předchozí stav,
6. až po úspěchu zapsat verzi a runtime marker.

`actions.sqlite3` musí zůstat chráněný cíl i při případné chybě manifestu.

## 9. Recovery

`OPRAVIT_TURTO.ps1` musí odkazovat na stejný commit a SHA-256 `app.pyw` a `updater.py`, jaké jsou v aktuálním manifestu. CI tuto shodu kontroluje.

Recovery používá obecné:

- `.turto_runtime_current.ok`,
- `startup.log`,
- `recovery.log`.

Historické markery/logy mohou být pouze zálohovány a uklizeny; nesmí řídit současný start.

## 10. Pull request / CI

PR do `main` musí projít jediným workflow `.github/workflows/ci.yml`.

CI je poslední automatická brána před merge. Merge se nesmí provést s neúspěšnou kontrolou.

Protože release URL používají konkrétní mezilehlé commity z pracovní větve, pro release PR se používá běžný **merge commit**, ne squash. Tím zůstanou pinned commity součástí historie `main`.

## 11. Praktický smoke test

Před označením vydání za prakticky ověřené na Windows zkontrolovat:

- start programu,
- novou a uloženou AKCI,
- Izolační nosníky i Smykové trny,
- hromadný import z výkazu,
- Záměny,
- export PDF AKCE,
- online aktualizaci,
- nouzový `OPRAVIT_TURTO.bat` na testovací instalaci,
- že `actions.sqlite3` zůstane beze změny.

Automatický CI tuto uživatelskou kontrolu UI nenahrazuje.

## 12. Databáze

Běžný release nesmí obsahovat `actions.sqlite3`. Pokud verze skutečně potřebuje databázovou migraci, musí mít samostatně zdokumentovaný migrační krok, zálohu a rollback. Taková migrace nesmí být skrytá uvnitř běžné aktualizace programových souborů.
