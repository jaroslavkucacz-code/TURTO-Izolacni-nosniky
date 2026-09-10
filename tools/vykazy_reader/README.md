# TURTO – Výkazy izolačních prvků · online aktualizace

Samostatný aktualizační kanál pro program **TURTO – Výkazy izolačních prvků**.
Nejde o runtime hlavní aplikace TURTO 2.x; soubory jsou záměrně oddělené pod `tools/vykazy_reader`.

Aktualizátor mění pouze soubory uvedené v `update_manifest.json`. Databáze akcí,
nastavení umístění databáze a archiv PDF jsou chráněné a nejsou součástí release.

Od verze 0.13.2 je kontrola online aktualizací přímo v aplikaci tlačítkem **Aktualizace**.
Pro přechod ze starší 0.13.1, která ještě updater neměla, slouží jednorázově
`AKTUALIZOVAT_ONLINE.bat`.
