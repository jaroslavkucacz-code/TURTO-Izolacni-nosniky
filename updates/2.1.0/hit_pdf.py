from __future__ import annotations
from typing import Any
import hit_pdf_127 as _prev
from hit_pdf_127 import *  # noqa
REPORT_VERSION="2.1.0";_prev.REPORT_VERSION=REPORT_VERSION;_base=_prev._base
_ORIGINAL_INPUT=_prev._input_summary;_ORIGINAL_CATALOG=_prev._ProposalReport._catalog_table;_ORIGINAL_CARD=_prev._ProposalReport.card_flows

def _input_summary(row:dict[str,Any],*,with_actions:bool=True)->str:
    if str(row.get("connection_type","")).upper()=="DOWEL":
        parts=["smykový trn",f"h {row.get('height_mm','—')} mm",f"spára {row.get('required_length_mm','—')} mm"]
        if row.get("concrete"):parts.append(str(row["concrete"]))
        if with_actions:
            acts=_prev._actions(row)
            if acts:parts.append(" • ".join(f"{a} {v} {u}" for a,v,u in acts))
        return " • ".join(parts)
    return _ORIGINAL_INPUT(row,with_actions=with_actions)

def _catalog_table(self,row,width):
    c=_prev._candidate(row)
    if str(c.get("connection_type","")).upper()!="DOWEL":return _ORIGINAL_CATALOG(self,row,width)
    widths=[160.,105.,width-265.];data=[[self.p("Katalogová hodnota",size=10.5,bold=True,color=_base.NAVY),self.p("Hodnota",size=10.5,bold=True,color=_base.NAVY,align=2),self.p("Jednotka",size=10.5,bold=True,color=_base.NAVY)],[self.p("VRd",bold=True),self.p(_prev._num(c.get("v1")),align=2),self.p("kN/prvek")]]
    table=self.table(data,widths,grid=True);table.setStyle(self.b["TableStyle"]([("BACKGROUND",(0,0),(-1,0),self.b["colors"].HexColor(_base.PANEL))]));table.repeatRows=1;return table

def _card_flows(self,row,refs):
    c=_prev._candidate(row)
    if str(c.get("connection_type","")).upper()!="DOWEL":return _ORIGINAL_CARD(self,row,refs)
    width=self.width-14;status=_prev._status(row);flows=[self.p(f'<font color="{_base.TEAL}">Zadání: </font>'+_base.escape(_input_summary(row,with_actions=False)),markup=True),self._actions_table(row,width),self.b["Spacer"](1,3)]
    if c:
        flows.append(self.p(f'<font color="{_base.GOLD}">Navržený smykový trn: </font>'+_base.escape(_prev._text(c.get("designation"))),bold=True,markup=True));flows.append(self.p(f"h: {_prev._num(row.get('height_mm'),0)} mm • spára: {_prev._num(row.get('required_length_mm'),0)} mm • {_prev._text(row.get('concrete'))} • zdroj {_prev._text(c.get('page'))}"));flows.append(self._catalog_table(row,width));flows.append(self.p(f"Výsledek: η = {_prev._percent(c.get('utilization'))} • {status}",bold=True,color=_prev._status_color(status)))
        mode=str(c.get("mode","") or "").strip();source=str(c.get("source_note","") or "").strip()
        if mode:flows.append(self.p("Rozhodující kontrola: "+mode,size=10.5,color=_base.MUTED))
        if source:flows.append(self.p("Katalogový podklad: "+source,size=10.5,color=_base.MUTED))
    detail=str(row.get("detail","") or "").strip()
    if detail:flows.append(self.p(detail,size=10.5,color=_base.WARNING if status!="VYHOVUJE" else _base.MUTED))
    return flows
_prev._input_summary=_input_summary;_prev._ProposalReport._catalog_table=_catalog_table;_prev._ProposalReport.card_flows=_card_flows
PdfExportError=_prev.PdfExportError
ensure_hit_pdf_backend=_prev.ensure_hit_pdf_backend
write_hit_proposal_pdf=_prev.write_hit_proposal_pdf
