# TURTO HIT – návrh HIT-HP/SP MVX

První funkční verze: **0.1.0**

## Co umí
- vstup: řada HP/SP, výška desky h, krytí cnom 30/35/50 mm, beton C20/25–C30/37, MEd a VEd,
- automaticky používá tabulkovou výšku `h - cnom`,
- sestaví skutečné označení nosníku doplněním výšky a krytí,
- kontroluje podmínku `|MEd| / |VEd| >= 0,15 m`,
- používá zjednodušenou lineární interakci mezi body `(MRd,1; VRd,1)` a `(MRd,2; VRd,2)`,
- seřadí vyhovující prvky od nejlépe využitého,
- zobrazuje zdrojovou stranu DoP,
- umí 1000 / 500 / 250 mm varianty a volitelně OD/OU/WD/WU.

## První spuštění
Spusťte `HIT_INSTALOVAT.bat` z kořene repozitáře. Program se nainstaluje do `%LOCALAPPDATA%\TURTO\HIT` a vytvoří zástupce `TURTO HIT` na ploše.

Při prvním spuštění vyberte originální soubor `CONF-DOP_HIT-HP_SP_07-23-E.pdf`. Program z něj lokálně vytvoří komprimovanou databázi `hit_mvx_2023.json.gz.b64`. Zdrojové PDF se nekopíruje do GitHubu.

## Aktualizace
Tlačítko **Aktualizace** čte `hit/update_manifest.json`, kontroluje SHA-256 a stahuje jen změněné soubory. Lokálně vytvořená databáze z DoP se při běžné aktualizaci nemaže.

## Poznámka
Tato verze je návrhový modul pro Annex 1 – HIT-HP/SP MVX. Další rodiny se přidají samostatnými verzemi, aby bylo možné jejich logiku ověřovat po částech.
