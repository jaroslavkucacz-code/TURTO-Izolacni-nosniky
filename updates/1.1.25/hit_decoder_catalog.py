from __future__ import annotations

"""1.1.25 combined Decoder ISO catalog with exact HIT-WT recognition."""

import re
from catalog_engine import SelectionError
import hit_decoder_catalog_prev as _prev
from hit_decoder_catalog_prev import *  # noqa: F401,F403
from hit_decoder_records import HIT_CATALOG_ID, norm, wt_result
from hit_decoder_suggest import hit_suggestions


class CombinedCatalogDatabase(_prev.CombinedCatalogDatabase):
    def _parse_exact_hit(self, text: str, concrete: str):
        raw = re.sub(r"^LEVIAT\s+", "", norm(text))
        m = re.fullmatch(r"HIT-(HP|SP)\s+WT-([1-7])-(100|125|150|175|200|225|250|275|300|325|350)-(15|16|17|18|19|20|21|22|23|24|25)", raw)
        if m:
            series, load, hcm, bcm = m.groups()
            try:
                return wt_result(
                    series=series,
                    load_range=int(load),
                    wall_height_mm=int(hcm) * 10,
                    width_mm=int(bcm) * 10,
                    concrete=str(concrete or "C25/30"),
                )
            except ValueError as exc:
                raise SelectionError(str(exc)) from exc
        return super()._parse_exact_hit(text, concrete)

    def query(self, *, catalog_id, manufacturer, model, type_name, generation, moment_class, concrete_min, shear_class, cover, height_mm):
        if str(catalog_id) == HIT_CATALOG_ID and str(type_name).upper() == "WT":
            series = "HP" if str(model).upper().endswith("HP") else "SP"
            match = re.search(r"([1-7])", str(moment_class))
            if not match:
                raise SelectionError("Uloženému HIT-WT chybí rozsah WT-1 až WT-7.")
            width_match = re.search(r"(150|160|170|180|190|200|210|220|230|240|250)", str(shear_class))
            if not width_match:
                raise SelectionError("Uloženému HIT-WT chybí šířka B 150–250 mm.")
            try:
                return wt_result(
                    series=series,
                    load_range=int(match.group(1)),
                    wall_height_mm=int(str(height_mm)),
                    width_mm=int(width_match.group(1)),
                    concrete=str(concrete_min),
                )
            except ValueError as exc:
                raise SelectionError(str(exc)) from exc
        return super().query(
            catalog_id=catalog_id, manufacturer=manufacturer, model=model, type_name=type_name,
            generation=generation, moment_class=moment_class, concrete_min=concrete_min,
            shear_class=shear_class, cover=cover, height_mm=height_mm,
        )

    def suggest_designations(self, text: str, preferred_catalog_id=None, preferred_concrete=None, limit: int = 12):
        hit = hit_suggestions(self, text, preferred_concrete, max(limit, 12))
        ordinary = self.base.suggest_designations(
            text, preferred_catalog_id=preferred_catalog_id,
            preferred_concrete=preferred_concrete, limit=max(limit, 12),
        )
        best = {}
        from hit_decoder_records import compact
        from catalog_engine import natural_key
        for item in [*hit, *ordinary]:
            key = compact(item.designation)
            if key not in best or item.score > best[key].score:
                best[key] = item
        return sorted(best.values(), key=lambda x: (-x.score, natural_key(x.designation)))[:limit]
