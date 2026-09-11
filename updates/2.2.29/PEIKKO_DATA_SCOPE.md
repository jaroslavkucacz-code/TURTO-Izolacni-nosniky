# Peikko data scope / 2.2.29

## Implemented

Exact syntax recognition of the 14 configurations supplied by the user, including
multiline input. `Ds`, `Dt`, `SW`, `L`, `S11` and explicitly entered `CV` are separate
fields. No dimension is inferred from the reinforcement code. Unknown text stays
in the exact configuration key; drawing/position prefixes do not.

The adapter uses the existing QueryResult and project row contract. A full
normalized configuration is stored in `selection.type_name` so older project
normalizers cannot discard S11, B2 or OQ. The original input remains in
`source_text`; the normal action JSON/SQLite persistence is unchanged.

## Not established by this release

No Peikko resistance table is included. Identifying a product string does not
validate manufacturability, concrete suitability, fire resistance or a national
technical approval. The stored concrete is the selected action concrete (or the
explicit concrete in the string), not an inferred Peikko minimum concrete grade.
`REI120` is a designation token, not a verified rating. `B2` and `OQ` are retained
without assigning an undocumented structural meaning. ZS is recognized from the
user's schedule, but its load-bearing role is not asserted.

The family descriptions are inherited from 2.2.28. Manufacturer references:
https://www.peikko.cz/vyrobky/vyrobek/ebea/
https://www.peikko.com/products/product/tebea/
Country-specific manufacturer data is necessary for any future verified design.

No capacity field, utilization percentage or accepted substitution is generated
from these strings. Existing HIT/Ancon numerical engines are not replaced.

## Verification

`tools/verify_peikko_2229.py`: 15 test methods plus parametrized checks covering all
14 supplied configurations, normalization, conflicts, identity, concrete filtering,
legacy catalog delegation and the central row contract.

`tools/verify_peikko_2229_runtime.py`: rebuilds the pinned installed runtime from
Git history with networking disabled; opens the real Tk UI; tests the common
three tabs, manufacturer switches, bulk import, central SQLite save/reload,
blocking unverified substitutions and original HIT/Ancon method availability.
