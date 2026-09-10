# TURTO – Výkazy kladecích plánů · online aktualizace

Samostatný aktualizační kanál pro program **TURTO – Výkazy kladecích plánů**.
Nejde o runtime hlavní aplikace TURTO 2.x; soubory jsou záměrně oddělené pod `tools/vykazy_reader`.

Aktualizátor mění pouze soubory uvedené v `update_manifest.json`. Databáze akcí,
nastavení umístění databáze a archiv PDF jsou chráněné a nejsou součástí release.

Od verze 0.13.2 je kontrola online aktualizací přímo v aplikaci tlačítkem **Aktualizace**.
Pro přechod ze starší 0.13.1, která ještě updater neměla, slouží jednorázově
`AKTUALIZOVAT_ONLINE.bat`.

## v0.13.4

- Stav akce: **Rozpracováno / Ke kontrole / Zkontrolováno / Exportováno**.
- Excel profily: **Kontrolní (kompletní)** a **Výkaz pro objednávku**.
- Výkaz pro objednávku obsahuje pouze `Označení | Množství | MJ` a stejné prvky sčítá za celou akci.
- Po analýze se automaticky zobrazí přehled počtu načtených položek, jednoznačných položek,
  položek k ruční kontrole, kontrolních rozdílů a upozornění PDF.
- Nové dekódování nastaví stav podle výsledku kontroly; úspěšný Excel export nastaví stav **Exportováno**.
