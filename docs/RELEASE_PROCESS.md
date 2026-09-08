# Release proces TURTO

Tento postup je povinný pro online vydání od 2.2.0.

## 1. Pracovní větev

Změny se připravují mimo `main`, typicky `release/X.Y.Z` nebo `cleanup/X.Y.Z`.

## 2. Zmrazit obsah release

Nejdříve se dokončí všechny zdrojové soubory v `updates/X.Y.Z/`. Po zmrazení se už soubory, na které bude odkazovat manifest, nesmí měnit bez nového výpočtu hashů a nového pinned commitu.

## 3. Syntax a statické kontroly

Spustit `python tools/verify_release.py`. Tato kontrola nenahrazuje praktické spuštění aplikace.

## 4. Commit-pinned URL

Každá URL programového souboru v manifestu musí mít tvar:

`https://raw.githubusercontent.com/<owner>/<repo>/<40-char-commit>/<path>`

Zakázáno je `/main/`, jiná větev, pohyblivý tag nebo URL bez konkrétního SHA.

## 5. SHA-256

SHA-256 se počítá z **přesných bajtů souboru v připnutém commitu**. Nikdy se nesmí kombinovat URL ze staršího commitu a SHA-256 z novější pracovní kopie. Právě tato kombinace způsobila chybu aktualizace u 2.1.3.

## 6. Manifest je poslední změna release obsahu

`update_manifest.json` se připraví až poté, co jsou zdrojové soubory zmrazené. Potom musí `tools/verify_release.py` projít bez chyby.

## 7. Pull request / CI

PR do `main` musí projít jediným workflow `.github/workflows/ci.yml`.

CI kontroluje strukturu manifestu, commit-pinned URL, SHA-256, syntax aktuální release vrstvy a základní hygienu repozitáře.

## 8. Praktický smoke test

Před zveřejněním uživateli ověřit na Windows: start programu, novou/uloženou AKCI, obě produktové oblasti, hromadný import z výkazu, záměny, export PDF AKCE a online aktualizaci.

## 9. Databáze

Běžný release nesmí obsahovat `actions.sqlite3`. Pokud verze skutečně potřebuje databázovou migraci, musí mít samostatně zdokumentovaný migrační krok a rollback.
