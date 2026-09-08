from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

TOL = 1e-9
ANCON_SOURCE = "Ancon Querkraftdorne für die Bauindustrie, Oktober 2018 (V1)"
SCHOCK_LD_SOURCE = "TI Schöck Stacon®/GB-en/2023.1/August – LD"
SCHOCK_SLD_SOURCE = "TI Schöck Stacon®/GB-en/2023.1/August – SLD"


@dataclass(frozen=True)
class DowelCandidate:
    manufacturer: str
    family: str
    size: str
    designation: str
    vrd: float
    utilization: float
    slab_table_mm: int
    gap_table_mm: int
    concrete_table: str
    movement: str
    page: str
    source: str
    status: str = "VYHOVUJE"
    note: str = ""
    length_mm: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "family": self.family,
            "size": self.size,
            "designation": self.designation,
            "vrd": self.vrd,
            "utilization": self.utilization,
            "slab_table_mm": self.slab_table_mm,
            "gap_table_mm": self.gap_table_mm,
            "concrete_table": self.concrete_table,
            "movement": self.movement,
            "page": self.page,
            "source": self.source,
            "status": self.status,
            "note": self.note,
            "length_mm": self.length_mm,
        }


def _rows(heights, gaps, values):
    return {int(g): {int(h): (None if v is None else float(v)) for h, v in zip(heights, row)} for g, row in zip(gaps, values)}


ANCON: dict[str, dict[str, Any]] = {}


def _add_ancon(family, size, heights, gaps, c25, c30, page, *, length_mm=None, lengths=(), large_joint=False):
    ANCON[f"{family}:{size}"] = {
        "family": family, "size": str(size), "heights": tuple(heights), "gaps": tuple(gaps),
        "tables": {"C25/30": _rows(heights, gaps, c25), "C30/37": _rows(heights, gaps, c30 if c30 is not None else c25)},
        "page": int(page), "length_mm": length_mm, "lengths": tuple(lengths), "large_joint": bool(large_joint),
    }


_h = [180, 200, 220, 240, 260, 280]
_add_ancon("ESD","8",_h,[0,10,20,30,40,50],[[17]*6,[17]*6,[15]*6,[13]*6,[11]*6,[10]*6],None,10,lengths=(300,350,400,500))
_add_ancon("ESD","10",_h,[10,20,30,40,50,60],[[26,27,27,27,27,27],[26]*6,[22]*6,[20]*6,[17]*6,[16]*6],[[29,30,30,30,30,30],[26]*6,[22]*6,[20]*6,[17]*6,[16]*6],11,lengths=(300,350,400,500))
_add_ancon("ESD","15",_h,[0,10,20,30,40,50],[[29,32,32,32,32,32],[29,32,32,32,32,32],[29,32,32,32,32,32],[28]*6,[25]*6,[22]*6],[[33,39,39,39,39,39],[33,36,36,36,36,36],[32]*6,[28]*6,[25]*6,[22]*6],12,lengths=(300,350,400,500))
_add_ancon("ESD","18",_h,[0,10,20,30,40,50],[[29,35,41,48,49,49],[29,35,41,44,44,44],[29,35,39,39,39,39],[29,35,35,35,35,35],[29,31,31,31,31,31],[28]*6],[[33,40,46,48,49,49],[33,40,44,44,44,44],[33,39,39,39,39,39],[33,35,35,35,35,35],[31]*6,[28]*6],13,lengths=(300,350,400,500))
_add_ancon("ESD","20",[220,240,260,280,300,350],[0,10,20,30,40,50],[[47,55,60,60,60,60],[47,55,60,60,60,60],[47,55,60,60,60,60],[47,55,58,58,58,58],[47,53,53,53,53,53],[47,48,48,48,48,48]],[[54,62,71,72,72,72],[54,62,70,70,70,70],[54,62,64,64,64,64],[54,58,58,58,58,58],[53]*6,[48]*6],14,lengths=(300,350,400,500))
_add_ancon("ESD","25",[240,260,280,300,350,400],[0,10,20,30,40,50],[[57,65,74,82,82,82],[57,65,74,75,75,75],[57,65,68,68,68,68],[57,61,61,61,61,61],[56]*6,[51]*6],[[64,74,83,83,83,83],[64,74,75,75,75,75],[64,68,68,68,68,68],[61]*6,[56]*6,[51]*6],15,lengths=(350,400,470))

_add_ancon("HLD","18",[160,180,200,220,240,260],[10,20,30,40,50,60],[[42,53,56,60,63,66],[38,49,52,55,58,61],[35,44,46,46,46,46],[35]*6,[28]*6,[24]*6],[[51,64,68,72,75,75],[46,58,61,61,61,61],[42,46,46,46,46,46],[35]*6,[28]*6,[24]*6],17,length_mm=270)
_add_ancon("HLD","22",[180,200,220,240,260,280],[10,20,30,40,50,60],[[73,90,97,104,112,115],[69,84,91,98,99,99],[63,77,81,81,81,81],[61,63,63,63,63,63],[51]*6,[43]*6],[[89,105,117,118,118,118],[83,101,101,101,101,101],[75,81,81,81,81,81],[63]*6,[51]*6,[43]*6],18,length_mm=310)
_add_ancon("HLD","24",[200,220,240,260,280,300],[10,20,30,40,50,60],[[88,105,124,133,134,134],[84,100,118,118,118,118],[78,94,101,101,101,101],[72,82,82,82,82,82],[66]*6,[56]*6],[[107,128,138,138,138,138],[101,120,120,120,120,120],[94,102,102,102,102,102],[82]*6,[66]*6,[56]*6],19,length_mm=330)
_add_ancon("HLD","30",[240,260,280,300,320,340],[10,20,30,40,50,60],[[151,163,177,190,203,203],[151,163,177,183,183,183],[145,161,161,161,161,161],[134,136,136,136,136,136],[111]*6,[94]*6],[[171,185,200,209,209,209],[171,185,186,186,186,186],[162]*6,[136]*6,[111]*6,[94]*6],20,length_mm=365)
_add_ancon("HLD","35",[300,320,340,360,380,400],[10,20,30,40,50,60],[[254,272,285,285,285,285],[254,260,260,260,260,260],[234]*6,[204]*6,[171]*6,[144]*6],[[288,293,293,293,293,293],[265]*6,[236]*6,[205]*6,[171]*6,[144]*6],21,length_mm=420)
_add_ancon("HLD","42",[350,400,450,500,550,600],[10,20,30,40,50,60],[[329,368,368,368,368,368],[328,334,334,334,334,334],[300]*6,[266]*6,[232]*6,[199]*6],[[368]*6,[334]*6,[300]*6,[266]*6,[232]*6,[199]*6],22,length_mm=470)
_add_ancon("HLD","52",[400,450,500,550,600,650],[10,20,30,40,50,60],[[443,496,514,514,514,514],[443,484,484,484,484,484],[443,453,453,453,453,453],[421]*6,[389]*6,[357]*6],[[502,533,533,533,533,533],[499]*6,[464]*6,[429]*6,[394]*6,[359]*6],23,length_mm=570)

_add_ancon("DSD","65",[200,220,240,260,280,300],[10,20,30,40,50,60],[[62,64,69,76,85,93],[62,64,69,76,85,93],[62,64,69,76,85,87],[62,64,68,68,68,68],[55]*6,[47,47,47,47,47,None]],[[71,73,78,87,96,106],[71,73,78,87,96,106],[71,73,78,87,87,87],[68]*6,[55]*6,[47,47,47,47,47,None]],25,length_mm=300)
_add_ancon("DSD","75",[240,260,280,300,320,340],[10,20,30,40,50,60],[[86,89,95,104,114,123],[86,89,95,104,114,123],[86,89,95,104,114,116],[86,89,90,90,90,90],[74]*6,[62]*6],[[98,101,107,118,129,140],[98,101,107,118,129,140],[98,101,107,116,116,116],[90]*6,[74]*6,[62]*6],26,length_mm=340)
_add_ancon("DSD","100",[320,340,360,380,400,420],[10,20,30,40,50,60],[[161,167,171,183,196,209],[158,163,167,179,191,204],[154,159,163,175,187,199],[150,155,159,161,161,161],[134]*6,[114]*6],[[183,189,193,208,222,237],[179,184,189,203,217,231],[174,180,185,198,204,204],[161]*6,[134]*6,[114]*6],27,length_mm=400)
_add_ancon("DSD","130",[360,380,400,420,440,460],[10,20,30,40,50,60],[[185,193,207,220,234,248],[181,189,202,216,229,243],[178,186,198,212,225,238],[174,182,195,207,220,234],[171,179,191,204,206,206],[168,175,176,176,176,176]],[[210,219,234,249,265,281],[205,215,229,244,260,275],[201,211,225,240,255,270],[198,206,221,235,249,249],[194,203,206,206,206,206],[176]*6],28,length_mm=470)
_add_ancon("DSD","150",[450,500,550,600,700,800],[10,20,30,40,50,60],[[281,308,340,380,465,486],[276,303,334,374,457,477],[271,298,328,368,450,451],[267,293,323,359,359,359],[262,288,297,297,297,297],[254]*6],[[318,349,385,431,527,583],[313,343,378,424,518,553],[307,337,372,417,451,451],[302,332,359,359,359,359],[297]*6,[254]*6],29,length_mm=550)
_add_ancon("DSD","400",[600,650,700,800,900,1000],[10,20,30,40,50,60],[[441,485,530,621,713,745],[435,478,522,612,666,666],[428,471,514,554,554,554],[422,442,442,442,442,442],[369]*6,[315]*6],[[500,550,600,704,779,779],[492,542,592,666,666,666],[485,534,554,554,554,554],[442]*6,[369]*6,[315]*6],30,length_mm=660)
_add_ancon("DSD","450",[600,650,700,800,900,1000],[10,20,30,40,50,60],[[485,515,561,654,748,840],[485,515,561,654,748,840],[485,515,561,654,748,840],[485,515,561,654,748,811],[485,515,561,654,685,685],[485,515,561,587,587,587]],[[550,584,636,742,848,952],[550,584,636,742,848,952],[550,584,636,742,848,941],[550,584,636,742,811,811],[550,584,636,685,685,685],[550,584,587,587,587,587]],31,length_mm=690)

_add_ancon("DSDS","30",[180,200,220,240,260,280],[60,80,100],[[34,39,44,50,56,62],[31,36,41,46,52,58],[28,33,37,42,47,53]],[[38,44,50,57,63,71],[35,41,46,52,59,65],[32,37,42,48,54,60]],32,large_joint=True)
_add_ancon("DSDS","50",[180,200,220,240,260,280],[60,80,100],[[41,41,46,52,59,65],[37,37,42,48,53,59],[35,35,40,45,50,56]],[[46,46,53,59,66,74],[42,42,48,54,60,67],[39,39,45,51,57,63]],33,large_joint=True)

EHLD = {
 "18": (160,270,{10:41.8,20:36.8,30:30.1,40:25.0,50:21.4,60:18.7}),
 "22": (180,300,{10:69.6,20:59.2,30:50.5,40:42.6,50:36.8,60:32.4}),
 "24": (200,330,{10:83.1,20:71.7,30:62.2,40:53.6,50:46.5,60:41.1}),
 "30": (240,350,{10:120.2,20:106.2,30:94.2,40:83.3,50:73.2,60:65.2}),
 "35": (300,400,{10:165.7,20:148.6,30:133.8,40:120.4,50:107.3,60:96.3}),
 "42": (350,470,{10:200.8,20:182.5,30:166.4,40:151.6,50:136.9,60:123.8}),
 "52": (400,570,{10:302.3,20:280.0,30:260.1,40:242.2,50:225.9,60:210.8}),
}

SCHOCK_LD_H = [160,180,200,220,250,280,300,350]
SCHOCK_LD_GAPS = [20,30,40,50]
SCHOCK_LD_SIZES = ["16","20","22","25","30"]
SCHOCK_LD = {
"LD": {
160:[[11.8,11.8,11.8,None,None],[11.8,11.8,11.8,None,None],[11.8,11.8,11.8,None,None],[10.9,11.8,11.8,None,None]],
180:[[18.8,20.6,20.6,20.1,None],[15.1,20.6,20.6,20.1,None],[12.6,20.6,20.6,20.1,None],[10.9,20.1,20.6,20.1,None]],
200:[[18.8,32.1,32.1,31.3,None],[15.1,27.4,32.1,31.3,None],[12.6,23.2,29.9,31.3,None],[10.9,20.1,26.0,31.3,None]],
220:[[18.8,33.5,42.6,45.1,44.1],[15.1,27.4,35.2,45.1,44.1],[12.6,23.2,29.9,42.0,44.1],[10.9,20.1,26.0,36.8,44.1]],
250:[[18.8,33.5,42.6,58.8,77.6],[15.1,27.4,35.2,49.0,77.6],[12.6,23.2,29.9,42.0,67.7],[10.9,20.1,26.0,36.8,59.8]],
280:[[18.8,33.5,42.6,58.8,81.7],[15.1,27.4,35.2,49.0,78.2],[12.6,23.2,29.9,42.0,67.7],[10.9,20.1,26.0,36.8,59.8]],
300:[[18.8,33.5,42.6,58.8,84.3],[15.1,27.4,35.2,49.0,78.2],[12.6,23.2,29.9,42.0,67.7],[10.9,20.1,26.0,36.8,59.8]],
350:[[18.8,33.5,42.6,58.8,90.7],[15.1,27.4,35.2,49.0,78.2],[12.6,23.2,29.9,42.0,67.7],[10.9,20.1,26.0,36.8,59.8]],
},
"LD-Q": {
160:[[10.4,11.8,11.8,None,None],[8.4,11.8,11.8,None,None],[7.0,11.8,11.8,None,None],[6.0,11.2,11.8,None,None]],
180:[[10.4,18.6,20.6,19.5,None],[8.4,15.2,19.5,19.5,None],[7.0,12.9,16.6,19.5,None],[6.0,11.2,14.5,19.5,None]],
200:[[10.4,18.6,23.7,30.5,None],[8.4,15.2,19.5,27.2,None],[7.0,12.9,16.6,23.3,None],[6.0,11.2,14.5,20.4,None]],
220:[[10.4,18.6,23.7,32.7,44.1],[8.4,15.2,19.5,27.2,43.4],[7.0,12.9,16.6,23.3,37.6],[6.0,11.2,14.5,20.4,33.2]],
250:[[10.4,18.6,23.7,32.7,51.3],[8.4,15.2,19.5,27.2,43.4],[7.0,12.9,16.6,23.3,37.6],[6.0,11.2,14.5,20.4,33.2]],
280:[[10.4,18.6,23.7,32.7,51.3],[8.4,15.2,19.5,27.2,43.4],[7.0,12.9,16.6,23.3,37.6],[6.0,11.2,14.5,20.4,33.2]],
300:[[10.4,18.6,23.7,32.7,51.3],[8.4,15.2,19.5,27.2,43.4],[7.0,12.9,16.6,23.3,37.6],[6.0,11.2,14.5,20.4,33.2]],
350:[[10.4,18.6,23.7,32.7,51.3],[8.4,15.2,19.5,27.2,43.4],[7.0,12.9,16.6,23.3,37.6],[6.0,11.2,14.5,20.4,33.2]],
}}

SLD_SIZES = ["220","250","300","350","400","450"]
SLDQ_SIZES = ["220","300","400"]
SLD_GAPS = [20,30,40,50,60]
SLD = {
(150,160): [[56.8,None,None,None,None,None],[45.7,None,None,None,None,None],[38.1,None,None,None,None,None],[32.6,None,None,None,None,None],[28.5,None,None,None,None,None]],
(160,180): [[56.8,74.7,None,None,None,None],[45.7,60.7,None,None,None,None],[38.1,50.9,None,None,None,None],[32.6,43.7,None,None,None,None],[28.5,38.2,None,None,None,None]],
(180,200): [[56.8,74.7,123.3,None,None,None],[45.7,60.7,101.8,None,None,None],[38.1,50.9,86.0,None,None,None],[32.6,43.7,74.2,None,None,None],[28.5,38.2,65.2,None,None,None]],
(200,220): [[56.8,74.7,123.3,None,None,None],[45.7,60.7,101.8,None,None,None],[38.1,50.9,86.0,None,None,None],[32.6,43.7,74.2,None,None,None],[28.5,38.2,65.2,None,None,None]],
(220,240): [[56.7,74.7,118.5,171.5,None,None],[45.7,60.7,101.8,156.2,None,None],[38.1,50.9,86.0,133.3,None,None],[32.6,43.7,74.2,115.7,None,None],[28.5,38.2,65.2,102.0,None,None]],
(230,250): [[56.8,74.7,121.3,176.0,None,None],[45.7,60.7,101.8,156.2,None,None],[38.1,50.9,86.0,133.3,None,None],[32.6,43.7,74.2,115.7,None,None],[28.5,38.2,65.2,102.0,None,None]],
(250,270): [[56.8,74.7,123.3,184.9,243.6,None],[45.7,60.7,101.8,156.2,217.2,None],[38.1,50.9,86.0,133.3,187.0,None],[32.6,43.7,74.2,115.7,163.3,None],[28.5,38.2,65.2,102.0,144.5,None]],
(280,300): [[56.8,74.7,123.3,186.4,255.9,356.2],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(300,320): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(330,350): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(350,370): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(380,400): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(400,420): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(430,450): [[56.8,74.7,123.3,179.3,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
(480,500): [[56.8,74.7,123.3,186.4,255.9,357.1],[45.7,60.7,101.8,156.2,217.2,307.9],[38.1,50.9,86.0,133.3,187.0,267.9],[32.6,43.7,74.2,115.7,163.3,235.7],[28.5,38.2,65.2,102.0,144.5,209.7]],
}
SLDQ = {
(150,160): [[55.4,None,None],[55.4,None,None],[50.7,None,None],[43.5,None,None],[38.1,None,None]],
(160,180): [[59.9,None,None],[59.9,None,None],[50.7,None,None],[43.5,None,None],[38.1,None,None]],
(180,200): [[74.1,138.8,None],[60.4,138.8,None],[50.7,122.9,None],[43.5,106.8,None],[38.1,94.2,None]],
(200,220): [[74.1,148.9,None],[60.4,144.0,None],[50.7,122.9,None],[43.5,106.8,None],[38.1,94.2,None]],
(220,240): [[72.6,158.5,None],[60.4,144.0,None],[50.7,122.9,None],[43.5,106.8,None],[38.1,94.2,None]],
(230,250): [[74.1,163.2,None],[60.4,144.0,None],[50.7,122.9,None],[43.5,106.8,None],[38.1,94.2,None]],
(250,270): [[74.1,171.7,310.4],[60.4,144.0,310.4],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(280,300): [[74.1,171.7,334.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(300,320): [[74.1,171.7,350.1],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(330,350): [[73.4,171.7,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(350,370): [[74.1,171.7,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(380,400): [[74.1,171.7,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(400,420): [[74.1,171.7,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(430,450): [[74.1,171.4,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
(480,500): [[74.1,171.7,359.6],[60.4,144.0,312.1],[50.7,122.9,272.6],[43.5,106.8,240.5],[38.1,94.2,214.4]],
}


def _concrete_table(value: str) -> str | None:
    m = re.search(r"C(\d+)/(\d+)", str(value or "").upper().replace(" ", ""))
    if not m or int(m.group(1)) < 25: return None
    return "C30/37" if int(m.group(1)) >= 30 else "C25/30"


def _gap_up(actual: float, gaps: Iterable[int]) -> int | None:
    return next((g for g in sorted(map(int, gaps)) if actual <= g + TOL), None)


def _height_down(actual: float, heights: Iterable[int]) -> int | None:
    vals = [h for h in sorted(map(int, heights)) if h <= actual + TOL]
    return max(vals) if vals else None


def _ancon_designation(meta, movement, low_sleeve, gap):
    fam, size = meta["family"], meta["size"]; q = movement == "transverse"
    if fam == "ESD":
        prefix = "ESDQ" if q else ("ED" if low_sleeve == "plastic" else "ESD")
        length = meta["lengths"][0] if meta.get("lengths") else None
        return f"Ancon {prefix} {size}" + (f" / {length}" if length else "")
    if fam == "HLD": return f"Ancon {'HLDQ' if q else 'HLD'} {size}"
    if fam == "DSD": return f"Ancon {'DSDQ' if q else 'DSD'} {size}"
    if fam == "DSDS":
        g = _gap_up(gap, (60,80,100)) or int(round(gap)); return f"Ancon {'DSDSQ' if q else 'DSDS'} {size}-{g}"
    return f"Ancon {fam} {size}"


def design_ancon(*, ved: float, slab_mm: float, gap_mm: float, concrete: str, movement: str = "axial", application: str = "new", low_sleeve: str = "stainless") -> tuple[list[DowelCandidate], str]:
    try: req, h, gap = abs(float(ved)), float(slab_mm), float(gap_mm)
    except Exception: return [], "Neplatný číselný vstup."
    if req <= TOL: return [], "Zadejte VEd > 0 kN na jeden trn."
    ctab = _concrete_table(concrete)
    if ctab is None: return [], "Ancon katalog v podkladu začíná na betonu C25/30."
    movement = "transverse" if str(movement).lower() in {"transverse","q","pricny","příčný"} else "axial"
    application = "existing_wall" if str(application).lower() in {"existing_wall","existing","stávající"} else "new"
    low_sleeve = "plastic" if str(low_sleeve).lower().startswith(("plast","plastic")) else "stainless"
    out: list[DowelCandidate] = []
    if application == "existing_wall":
        gt = _gap_up(gap, (10,20,30,40,50,60))
        if gt is None: return [], "E-HLD je tabulován pro spáru do 60 mm."
        for size,(hmin,length,table) in EHLD.items():
            if h + TOL < hmin: continue
            vrd = float(table[gt])
            if vrd + TOL >= req:
                out.append(DowelCandidate("Ancon","E-HLD",size,f"Ancon E-HLD{'Q' if movement=='transverse' else ''} {size}",vrd,req/vrd,hmin,gt,ctab,movement,"35",ANCON_SOURCE,note="Napojení nové desky na stávající betonovou stěnu; ověřit kotvení a předepsanou výztuž.",length_mm=length))
        out.sort(key=lambda c:(int(c.size), c.vrd)); return out, "" if out else "V tabulkách E-HLD nebyl nalezen vyhovující typ."
    family_rank = {"ESD":0,"HLD":1,"DSD":2,"DSDS":3}
    for meta in ANCON.values():
        if meta["large_joint"] and gap < 60 - TOL: continue
        ht = _height_down(h, meta["heights"]); gt = _gap_up(gap, meta["gaps"])
        if ht is None or gt is None: continue
        vrd = meta["tables"][ctab][gt].get(ht)
        if vrd is None or vrd + TOL < req: continue
        out.append(DowelCandidate("Ancon",meta["family"],meta["size"],_ancon_designation(meta,movement,low_sleeve,gap),float(vrd),req/float(vrd),ht,gt,ctab,movement,str(meta["page"]),ANCON_SOURCE,note="Únosnost platí při dodržení katalogové lokální výztuže a minimálních okrajových/osových vzdáleností.",length_mm=meta.get("length_mm")))
    out.sort(key=lambda c:(family_rank.get(c.family,9), int(re.sub(r"\D","",c.size) or 9999), c.vrd))
    return out, "" if out else "Pro zadanou tloušťku, spáru, beton a VEd nebyl v tabulkách Ancon nalezen vyhovující trn."


_ANCON_RE = re.compile(r"(?:ANCON\s+)?(E-HLDQ?|HLDQ?|DSDSQ?|DSDQ?|ESDQ?|ESD|ED)\s*[- ]?\s*(\d+)(?:\s*[-/]\s*(\d+))?", re.I)
_SCHOCK_RE = re.compile(r"(?:SCH[ÖO]CK\s+)?(?:STACON\s+)?(SLD-Q|SLDQ|SLD|LD-Q|LDQ|LD)\s*[- ]?\s*(\d+)", re.I)


def decode_dowel(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip(); m = _ANCON_RE.search(raw)
    if m:
        family = m.group(1).upper(); q = family.endswith("Q"); base = family[:-1] if q else family
        if base == "ED": base = "ESD"
        return {"manufacturer":"Ancon","family":family,"base_family":base,"size":m.group(2),"suffix":m.group(3) or "","movement":"transverse" if q else "axial","text":raw}
    m = _SCHOCK_RE.search(raw)
    if m:
        family = m.group(1).upper().replace("LDQ","LD-Q").replace("SLDQ","SLD-Q")
        return {"manufacturer":"Schöck","family":family,"base_family":family.replace("-Q",""),"size":m.group(2),"movement":"transverse" if family.endswith("-Q") else "axial","text":raw}
    return None


def ancon_capacity_from_designation(designation: str, slab_mm: float, gap_mm: float, concrete: str) -> DowelCandidate | None:
    info = decode_dowel(designation)
    if not info or info["manufacturer"] != "Ancon": return None
    fam,size,movement = info["base_family"],info["size"],info["movement"]
    if fam == "E-HLD":
        if size not in EHLD: return None
        hmin,length,table = EHLD[size]; gt = _gap_up(float(gap_mm), table.keys())
        if gt is None or float(slab_mm)+TOL < hmin: return None
        vrd=float(table[gt]); return DowelCandidate("Ancon","E-HLD",size,designation,vrd,0.0,hmin,gt,_concrete_table(concrete) or "C25/30",movement,"35",ANCON_SOURCE,length_mm=length)
    meta = ANCON.get(f"{fam}:{size}"); ct = _concrete_table(concrete)
    if not meta or not ct: return None
    ht = _height_down(float(slab_mm),meta["heights"]); gt=_gap_up(float(gap_mm),meta["gaps"])
    if ht is None or gt is None: return None
    vrd=meta["tables"][ct][gt].get(ht)
    if vrd is None: return None
    return DowelCandidate("Ancon",fam,size,designation,float(vrd),0.0,ht,gt,ct,movement,str(meta["page"]),ANCON_SOURCE,length_mm=meta.get("length_mm"))


def _sld_row(table, slab_mm: float, cover_mm: int):
    index = 0 if int(cover_mm) <= 20 else 1; eligible=[]
    for pair, rows in table.items():
        hreq=pair[index]
        if hreq <= slab_mm + TOL: eligible.append((hreq,pair,rows))
    return max(eligible,key=lambda x:x[0]) if eligible else None


def design_schock(*, required_vrd: float, slab_mm: float, gap_mm: float, movement: str="axial", cover_mm: int=30) -> tuple[list[DowelCandidate], str]:
    req=abs(float(required_vrd)); h=float(slab_mm); gap=float(gap_mm); q = str(movement).lower() in {"transverse","q","pricny","příčný"}; out=[]
    ht=_height_down(h,SCHOCK_LD_H); gt=_gap_up(gap,SCHOCK_LD_GAPS); fam="LD-Q" if q else "LD"
    if ht is not None and gt is not None:
        row=SCHOCK_LD[fam][ht][SCHOCK_LD_GAPS.index(gt)]
        for size,vrd in zip(SCHOCK_LD_SIZES,row):
            if vrd is not None and vrd + TOL >= req:
                out.append(DowelCandidate("Schöck",fam,size,f"Schöck Stacon® {fam} {size}",float(vrd),req/float(vrd),ht,gt,"C20/25–C50/60","transverse" if q else "axial","59–60",SCHOCK_LD_SOURCE,note="Platí při katalogové výztuži a dodržení kritických roztečí/okrajových vzdáleností."))
    table=SLDQ if q else SLD; sizes=SLDQ_SIZES if q else SLD_SIZES; sel=_sld_row(table,h,int(cover_mm)); gt2=_gap_up(gap,SLD_GAPS)
    if sel is not None and gt2 is not None:
        hreq,pair,rows=sel; vals=rows[SLD_GAPS.index(gt2)]; sfam="SLD-Q" if q else "SLD"
        for size,vrd in zip(sizes,vals):
            if vrd is not None and vrd + TOL >= req:
                out.append(DowelCandidate("Schöck",sfam,size,f"Schöck Stacon® {sfam} {size}",float(vrd),req/float(vrd),int(hreq),gt2,f"cnom {20 if int(cover_mm)<=20 else 30} mm","transverse" if q else "axial","31–34",SCHOCK_SLD_SOURCE,status="KONTROLA DESKY",note="VRd,ce,s trnového spojení vyhovuje; před konečným VYHOVUJE je nutné ověřit smykovou únosnost desky a katalogovou výztuž."))
    rank={"LD":0,"LD-Q":0,"SLD":1,"SLD-Q":1}; out.sort(key=lambda c:(rank[c.family], int(c.size), c.vrd))
    return out, "" if out else "Pro zadanou geometrii nebyl v ověřených tabulkách Schöck Stacon nalezen vyhovující typ."


def schock_capacity_from_designation(designation: str, slab_mm: float, gap_mm: float, cover_mm: int=30) -> DowelCandidate | None:
    info=decode_dowel(designation)
    if not info or info["manufacturer"]!="Schöck": return None
    fam,size=info["family"],info["size"]
    if fam in {"LD","LD-Q"} and size in SCHOCK_LD_SIZES:
        ht=_height_down(float(slab_mm),SCHOCK_LD_H); gt=_gap_up(float(gap_mm),SCHOCK_LD_GAPS)
        if ht is None or gt is None: return None
        v=SCHOCK_LD[fam][ht][SCHOCK_LD_GAPS.index(gt)][SCHOCK_LD_SIZES.index(size)]
        if v is None:return None
        return DowelCandidate("Schöck",fam,size,designation,float(v),0.0,ht,gt,"C20/25–C50/60",info["movement"],"59–60",SCHOCK_LD_SOURCE)
    if fam in {"SLD","SLD-Q"}:
        q=info["movement"]=="transverse"; table=SLDQ if q else SLD; sizes=SLDQ_SIZES if q else SLD_SIZES
        if size not in sizes:return None
        sel=_sld_row(table,float(slab_mm),int(cover_mm)); gt=_gap_up(float(gap_mm),SLD_GAPS)
        if sel is None or gt is None:return None
        hreq,pair,rows=sel; v=rows[SLD_GAPS.index(gt)][sizes.index(size)]
        if v is None:return None
        return DowelCandidate("Schöck",fam,size,designation,float(v),0.0,int(hreq),gt,f"cnom {20 if cover_mm<=20 else 30} mm",info["movement"],"31–34",SCHOCK_SLD_SOURCE,status="KONTROLA DESKY")
    return None


def propose_substitution(*, source_designation: str, target_manufacturer: str, slab_mm: float, gap_mm: float, concrete: str="C25/30", cover_mm: int=30, low_sleeve: str="stainless") -> tuple[DowelCandidate | None, DowelCandidate | None, str]:
    info=decode_dowel(source_designation)
    if not info:return None,None,"Zdrojové označení smykového trnu nebylo rozpoznáno."
    source = ancon_capacity_from_designation(source_designation,slab_mm,gap_mm,concrete) if info["manufacturer"]=="Ancon" else schock_capacity_from_designation(source_designation,slab_mm,gap_mm,cover_mm)
    if source is None:return None,None,"Pro zdrojový trn nelze z dané tloušťky/spáry určit katalogovou VRd."
    if "sch" in str(target_manufacturer).lower(): candidates,error=design_schock(required_vrd=source.vrd,slab_mm=slab_mm,gap_mm=gap_mm,movement=info["movement"],cover_mm=cover_mm)
    else:candidates,error=design_ancon(ved=source.vrd,slab_mm=slab_mm,gap_mm=gap_mm,concrete=concrete,movement=info["movement"],application="new",low_sleeve=low_sleeve)
    return (source,candidates[0],"") if candidates else (source,None,error)


def catalog_summary() -> str:
    return "Ancon: ED/ESD/ESDQ, HLD/HLDQ, DSD/DSDQ, DSDS/DSDSQ, E-HLD • Schöck Stacon: LD/LD-Q, SLD/SLD-Q (pro záměny)"
