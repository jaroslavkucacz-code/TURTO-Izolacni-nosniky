from __future__ import annotations
"""TURTO 2.2.40 – correct PDF terminology and shear-substitution capacity display."""
import math
from pathlib import Path
from typing import Any

VERSION = "2.2.40"
_INSTALLED = False


def _n(value):
    try:
        x = float(str(value).strip().replace(",", "."))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _f(value, d=1):
    x = _n(value)
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def _pct(value):
    x = _n(value)
    return "—" if x is None else _f(100 * x, 1) + " %"


def _bucket(status):
    s = str(status or "").upper()
    if s.startswith("VYHOVUJE"):
        return "ok"
    if any(x in s for x in ("NELZE", "NEVYHOVUJE", "CHYBA")):
        return "fail"
    return "review"


def _ctx(rows):
    rows = list(rows)
    domains = {str(r.get("domain_id", "")) for r in rows}
    tabs = {str(r.get("report_tab", "")) for r in rows}
    if domains == {"shear_dowels"} and tabs == {"substitution"}:
        return "sub", "Záměny smykových trnů", "Statická kontrola záměny smykového trnu"
    if domains == {"shear_dowels"} and tabs == {"design"}:
        return "design", "Návrh smykových trnů", "Statická kontrola návrhu smykového trnu"
    if domains == {"shear_dowels"} and tabs == {"decoder"}:
        return "decoder", "Dekodér smykových trnů", "Detail smykového trnu"
    if domains == {"shear_dowels"}:
        return "shear", "Smykové trny", "Detail smykového trnu"
    if "shear_dowels" in domains:
        return "mixed", "Technické prvky – přehled AKCE", "Technická kontrola prvku"
    return "thermal", "", ""


def _report_row(data: dict[str, Any], index: int) -> dict[str, Any]:
    source = dict(data.get("source")) if isinstance(data.get("source"), dict) else {}
    target = dict(data.get("target")) if isinstance(data.get("target"), dict) else {}
    sv = _n(source.get("vrd")); tv = _n(target.get("vrd")); ved = _n(data.get("ved"))
    if ved is not None and ved <= 0: ved = None
    ratio = _n(data.get("capacity_ratio"))
    if ratio is None and sv and tv is not None: ratio = tv / sv
    util = ved / tv if ved is not None and tv and tv > 0 else None
    mode = str(data.get("verification_mode", "catalog") or "catalog").lower()
    note = str(target.get("note", "") or data.get("error", "") or "").strip()
    src_name = str(source.get("designation") or data.get("source_designation") or "—")
    dst_name = str(target.get("designation") or "—")
    candidate = {
        "designation": dst_name, "connection_type": "DOWEL",
        "manufacturer": str(target.get("manufacturer", data.get("target_manufacturer", "")) or ""),
        "height": data.get("slab_mm", ""), "concrete": data.get("concrete", ""),
        "utilization": util, "v1": tv, "m1": 0, "m2": 0, "v2": 0,
        "mode": "Podle VEd" if mode == "ved" else "Katalogová VRd",
        "page": str(target.get("page", "") or ""), "source_note": str(target.get("source", "") or ""),
    }
    return {
        "domain_id": "shear_dowels", "domain": "Smykové trny", "group": "Záměny", "report_tab": "substitution",
        "name": str(data.get("name", "") or f"S{index:03d}"), "quantity": int(_n(data.get("quantity")) or 1),
        "connection_type": "DOWEL", "height_mm": data.get("slab_mm", ""), "required_length_mm": data.get("gap_mm", ""),
        "concrete": data.get("concrete", ""), "cover_mm": data.get("cover_mm", ""), "candidate": candidate,
        "status": str(data.get("status", "NEPOSOUZENO") or "NEPOSOUZENO"), "detail": note, "notes": [],
        "custom_actions": ([{"label": "VEd", "value": ved, "unit": "kN/trn"}] if ved is not None else []),
        "source_designation": src_name, "target_designation": dst_name, "source_vrd": sv, "target_vrd": tv,
        "ved": ved, "capacity_ratio": ratio, "verification_mode": mode,
    }


def _structured(owner):
    rows = getattr(owner, "shear_substitution_rows", None)
    return [_report_row(dict(r), i) for i, r in enumerate(rows or (), 1) if isinstance(r, dict)]


def install(app_base):
    global _INSTALLED
    if _INSTALLED: return
    import pdf_scope, hit_pdf
    cls = hit_pdf._ProposalReport; base = hit_pdf._base
    old_collect = pdf_scope.collect_report_sections
    old_header = cls.header; old_sh = cls.summary_header; old_sr = cls.summary_row
    old_sp = cls.summary_pages; old_card = cls.card_flows; old_write = cls.write

    def collect(owner):
        sections = old_collect(owner)
        if hasattr(owner, "shear_substitution_rows"):
            sections[("shear_dowels", "substitution")] = _structured(owner)
        return sections

    def header(self, c, title, page, total):
        kind, _, _ = _ctx(self.rows)
        if kind == "thermal": return old_header(self, c, title, page, total)
        self.logo_draw(c); x, width = self.margin + 82, self.width - 82
        self.draw(c, self.p(title, size=16, bold=True, color=base.NAVY), 15, x, width)
        self.draw(c, self.p(f"TURTO  •  {self.generated}", color=base.MUTED), 37, x, width)
        self.draw(c, self.p(self.project, bold=True), 54, x, width)
        c.setStrokeColor(self.b["colors"].HexColor(base.GOLD)); c.setLineWidth(1.2)
        c.line(self.margin, self.h - self.top + 5, self.w - self.margin, self.h - self.top + 5)
        fy = self.h - 60; c.setStrokeColor(self.b["colors"].HexColor(base.BORDER)); c.setLineWidth(.5)
        c.line(self.margin, 64, self.w - self.margin, 64)
        self.draw(c, self.p(self.creator, size=10), fy, width=self.width - 90)
        self.draw(c, self.p(f"{page} / {total}", align=2), fy, self.w - self.margin - 80, 80)
        footer = "Technický přehled AKCE. Výsledky je nutno ověřit podle příslušných katalogových podkladů."
        if kind == "sub": footer = "Katalogová záměna smykových trnů. Rozhodující je skutečné VEd vůči VRd navržené záměny."
        self.draw(c, self.p(footer, size=9.5, color=base.MUTED), fy + 16)

    def summary_header(self):
        kind, _, _ = _ctx(self.rows)
        if kind == "thermal": return old_sh(self)
        if kind == "sub":
            widths = [39, 99, 119, 62, 62, 70, self.width - 451]
            labels = ["Poz.", "Původní trn", "Navržená záměna", "VRd zám.", "VRd pův.", "Kontrola", "Výsledek"]
        else:
            widths = [43, 166, 205, 70, self.width - 484]
            result = "Navržený smykový trn" if kind == "design" else "Výsledek / prvek"
            labels = ["Poz.", "Zadání", result, "Kontrola", "Výsledek"]
        return self.table([[self.p(v, size=10, bold=True, color=base.WHITE) for v in labels]], widths, background=base.NAVY), widths

    def summary_row(self, row, index, widths):
        if _ctx(self.rows)[0] != "sub": return old_sr(self, row, index, widths)
        mode = str(row.get("verification_mode", "catalog")); ved = _n(row.get("ved")); tv = _n(row.get("target_vrd"))
        control = "η " + _pct(ved / tv) if mode == "ved" and ved is not None and tv else _pct(row.get("capacity_ratio")) + " VRd"
        status = str(row.get("status", "NEPOSOUZENO")); color = base.SUCCESS if _bucket(status)=="ok" else base.DANGER if _bucket(status)=="fail" else base.WARNING
        cells = [[self.p(row.get("name"), bold=True), self.p(row.get("source_designation")), self.p(row.get("target_designation"), bold=True),
                  self.p(_f(row.get("target_vrd")), bold=True, align=2, color=base.NAVY), self.p(_f(row.get("source_vrd")), align=2, color=base.MUTED),
                  self.p(control, align=2), self.p(status, bold=True, align=2, color=color)]]
        return self.table(cells, widths, background=base.WHITE if index % 2 == 0 else base.PANEL, grid=True)

    def summary_pages(self):
        kind, _, _ = _ctx(self.rows)
        if kind == "thermal": return old_sp(self)
        head, widths = self.summary_header(); buckets = [_bucket(r.get("status")) for r in self.rows]
        intro = self.p(f"{len(self.rows)} pozic  •  vyhovuje {buckets.count('ok')}  •  k ověření {buckets.count('review')}  •  nevyhovuje / nelze {buckets.count('fail')}", bold=True)
        desc = "Souhrnný technický přehled smykových trnů."
        if kind == "sub": desc = "Záměny smykových trnů: v režimu podle VEd rozhoduje VEd ≤ VRd navržené záměny; VRd původního trnu je referenční hodnota pro záměnu 1:1."
        flows = [intro, self.p(desc, size=10.5, color=base.MUTED), self.b["Spacer"](1,6), head]
        y = self.top + sum(self.height(x) for x in flows); pages=[]
        for i,row in enumerate(self.rows):
            flow=self.summary_row(row,i,widths); h=self.height(flow)
            if y+h > self.h-self.bottom:
                pages.append(("summary",flows)); head,widths=self.summary_header(); flows=[head]; y=self.top+self.height(head)
            flows.append(flow); y += h
        pages.append(("summary",flows)); return pages

    def card_flows(self, row, refs):
        if not (row.get("domain_id")=="shear_dowels" and row.get("report_tab")=="substitution"):
            return old_card(self,row,refs)
        width=self.width-14; status=str(row.get("status","NEPOSOUZENO")); bucket=_bucket(status)
        color=base.SUCCESS if bucket=="ok" else base.DANGER if bucket=="fail" else base.WARNING
        sv=_n(row.get("source_vrd")); tv=_n(row.get("target_vrd")); ved=_n(row.get("ved")); ratio=_n(row.get("capacity_ratio")); mode=str(row.get("verification_mode","catalog"))
        flows=[self.p(f"h = {_f(row.get('height_mm'),0)} mm  •  spára = {_f(row.get('required_length_mm'),0)} mm" + (f"  •  {row.get('concrete')}" if row.get('concrete') else ""), color=base.MUTED)]
        comp=self.table([[self.p("Původní trn",bold=True,color=base.MUTED),self.p("Navržená záměna",bold=True,color=base.NAVY)],
                         [self.p(row.get("source_designation")),self.p(row.get("target_designation"),bold=True)],
                         [self.p("VRd původního = "+_f(sv)+" kN",color=base.MUTED),self.p("VRd záměny = "+_f(tv)+" kN",bold=True,color=base.NAVY)]], [width/2,width/2], grid=True)
        comp.setStyle(self.b["TableStyle"]([("BACKGROUND",(0,0),(-1,0),self.b["colors"].HexColor(base.PANEL))])); flows += [comp,self.b["Spacer"](1,5)]
        if mode=="ved" and ved is not None:
            rows=[("Režim","Podle skutečného VEd"),("VEd",_f(ved)+" kN/trn"),("VRd navržené záměny",_f(tv)+" kN"),("Využití záměny η = VEd / VRd",_pct(ved/tv) if tv else "—"),("VRd původního trnu – pouze reference",_f(sv)+" kN"),("Výsledek",status)]
        else:
            rows=[("Režim","Katalogová VRd – záměna 1:1"),("VRd navržené záměny",_f(tv)+" kN"),("VRd původního trnu – referenční požadavek",_f(sv)+" kN"),("Poměr VRd,zám / VRd,pův",_pct(ratio)),("Skutečné VEd","nezadáno"),("Výsledek",status)]
        data=[[self.p("Kontrola záměny",bold=True,color=base.WHITE),self.p("Hodnota",bold=True,color=base.WHITE)]]
        for label,value in rows:
            primary=label in {"VEd","VRd navržené záměny","Využití záměny η = VEd / VRd","Výsledek"}
            data.append([self.p(label,bold=primary),self.p(value,bold=primary,color=color if label=="Výsledek" else base.NAVY if primary else base.MUTED)])
        check=self.table(data,[width*.62,width*.38],grid=True); check.setStyle(self.b["TableStyle"]([("BACKGROUND",(0,0),(-1,0),self.b["colors"].HexColor(base.NAVY))])); flows.append(check)
        if mode!="ved" and tv is not None and sv is not None and tv<sv:
            flows.append(self.p(f"Záměna nedosahuje VRd původního trnu; lze ji potvrdit po doložení skutečného VEd ≤ {_f(tv)} kN/trn.",size=10.5,color=base.WARNING))
        if mode=="ved": flows.append(self.p("Při kontrole podle VEd je rozhodující únosnost navržené záměny; VRd původního typu je pouze referenční.",size=10.5,color=base.MUTED))
        flows.append(self.p("Únosnosti nejsou interpolovány.",size=10.5,color=base.MUTED))
        if row.get("detail"): flows.append(self.p(str(row["detail"]),size=10.5,color=base.MUTED if bucket=="ok" else base.WARNING))
        return flows

    def write(self, path: Path):
        kind, stitle, dtitle = _ctx(self.rows)
        if kind == "thermal": return old_write(self,path)
        plan=self.summary_pages()+self.detail_pages()+self.notes_pages(); c=self.b["Canvas"](str(path),pagesize=self.b["A4"],pageCompression=1)
        c.setTitle(f"TURTO – {stitle} – {self.project}"); c.setAuthor(self.creator); c.setCreator("TURTO "+VERSION); c.setSubject(stitle)
        di=si=ni=0
        for index,(ptype,items) in enumerate(plan,1):
            title={"summary":stitle,"detail":dtitle,"notes":"Poznámky a omezení"}[ptype]; self.header(c,title,index,len(plan)); y=self.top; c.bookmarkPage(f"page{index}")
            if ptype=="detail":
                di+=1; c.addOutlineEntry("Pozice "+", ".join(str(card.row.get("name","—")) for card in items),f"page{index}",0)
                for card in items: y=self.card_draw(c,card,y)+6
            else:
                if ptype=="summary": si+=1; label=f"Souhrn – {si}"
                else: ni+=1; label=f"Poznámky – {ni}"
                c.addOutlineEntry(label,f"page{index}",0)
                for flow in items: y=self.draw(c,flow,y)
            if y>self.h-self.bottom+6.2: raise hit_pdf.PdfExportError("Obsah PDF přesahuje vyhrazenou tiskovou oblast.")
            c.showPage()
        c.save(); return {"pages":len(plan),"summary_pages":si,"detail_pages":di,"notes_pages":ni}

    pdf_scope.collect_report_sections=collect; cls.header=header; cls.summary_header=summary_header; cls.summary_row=summary_row
    cls.summary_pages=summary_pages; cls.card_flows=card_flows; cls.write=write; cls._turto_pdf_context_240=True
    app_base.ThermalConnectorApp._turto_pdf_context_240=True; _INSTALLED=True


def selftest():
    sample={"name":"S005","quantity":6,"source_designation":"CRET 140","slab_mm":350,"gap_mm":20,"concrete":"C30/37","source":{"designation":"CRET-140","vrd":347.0},"target":{"designation":"Ancon HLD 42","vrd":334.0},"status":"OVĚŘIT VEd","verification_mode":"catalog","capacity_ratio":334/347}
    row=_report_row(sample,5); assert row["source_vrd"]==347 and row["target_vrd"]==334 and row["candidate"]["utilization"] is None
    assert _ctx([row])[1]=="Záměny smykových trnů" and "HIT" not in _ctx([row])[1]
    ved=dict(sample,verification_mode="ved",ved=320,status="VYHOVUJE dle VEd"); r=_report_row(ved,5); assert abs(r["candidate"]["utilization"]-320/334)<1e-12
    assert _bucket("VYHOVUJE dle VEd")=="ok" and _bucket("OVĚŘIT VEd")=="review" and _bucket("NELZE dle VEd")=="fail"

if __name__ == "__main__": selftest()
