# TURTO 2.0 – architektura

## Hierarchie

AKCE
→ produktová oblast
→ Dekodér / Návrh / Záměny
→ výrobce (u Návrhu a Záměn)
→ katalogový adaptér
→ konkrétní typ výrobku

## Produktové oblasti

- `thermal_breaks` – Izolační nosníky, aktivní.
- `shear_dowels` – Smykové trny, připravený rámec.
- `stair_acoustics` – Akustika schodiště, připravený rámec.

## Výrobci

Výrobci jsou registrováni po produktových oblastech. Aktivní adaptér 2.0.0:

- Izolační nosníky → Leviat → `leviat_hit`.

Další výrobce se přidává registrací výrobce a jeho návrhového/záměnového adaptéru. UI a databáze AKCE se kvůli tomu nemění.

## Výstupy

PDF je na úrovni AKCE a používá registry report providerů podle produktových oblastí. V 2.0.0 je aktivní provider pro Izolační nosníky. Další produktové oblasti se do stejného výstupu doplní vlastními providery.

## Kompatibilita

Výpočtová a katalogová data 1.1.x se nepřepisují do nového formátu. `platform_state` pouze doplňuje stabilní ID produktové oblasti a zvolených výrobců. Stávající `hit_design`, `aux_design`, `wt_design` a stav záměn zůstávají beze změny.
