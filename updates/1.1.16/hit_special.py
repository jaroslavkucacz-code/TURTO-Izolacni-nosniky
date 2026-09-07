from __future__ import annotations
import math
from typing import Any

TOL = 1e-9
HIT_CATALOG_SOURCE = "HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN"
HIT_CATALOG_URL = "https://www.leviat.com/en-us/mwdownloads/download/link/id/898.pdf"

# Height groups used in AT/FT interaction tables.
_H4 = ((160,170),(180,190),(200,210),(220,250))
_H3 = ((160,190),(200,210),(220,250))

def _band(height:int, spans):
    for i,(lo,hi) in enumerate(spans):
        if lo <= height <= hi: return i
    return None

def _interp(points: dict[float, tuple[float,...]], x: float, idx:int) -> float|None:
    if not points: return None
    keys=sorted(float(k) for k in points)
    if x < keys[0]-TOL or x > keys[-1]+TOL: return None
    for k in keys:
        if abs(x-k)<=TOL: return float(points[k][idx])
    for a,b in zip(keys,keys[1:]):
        if a <= x <= b:
            ya=float(points[a][idx]); yb=float(points[b][idx])
            t=(x-a)/(b-a)
            return ya+(yb-ya)*t
    return None

def _interp_signed(points: dict[float, tuple[float,...]], x: float, idx:int) -> float|None:
    # same interpolation helper, keys may be negative
    return _interp(points,x,idx)

# --- AT tables, HIT 20.2-EN pp.132-133 ---
_AT_N = {
"HP": {
"AT1": {0:(0,0,0,0),2:(4.5,5.4,6.3,7.0),4:(8.3,9.8,11.1,12.1),6:(11.4,13.3,15.0,16.0),8:(14.2,16.3,18.2,19.1),10:(16.5,18.8,20.9,21.5),12:(18.5,21.0,23.2,23.6),20:(24.7,27.3,29.5,29.2),30:(29.5,32.1,34.3,33.1),40:(32.8,35.3,37.2,35.5),50:(35.1,37.4,39.3,37.1),60:(36.8,39.0,40.8,38.2)},
"AT2": {0:(0,0,0,0),2:(9.6,11.5,13.3,14.8),4:(17.5,20.7,23.6,25.6),6:(24.3,28.2,31.9,33.8),8:(30.0,34.5,38.6,40.4),10:(35.0,39.9,44.3,45.7),12:(39.3,44.5,49.1,50.0)},
},
"SP": {
"AT1": {0:(0,0,0,0),2:(3.6,4.3,5.0,5.6),4:(6.6,7.8,8.9,9.7),6:(9.2,10.7,12.0,12.8),8:(11.3,13.0,14.6,15.2),10:(13.2,15.1,16.7,17.2),12:(14.8,16.8,18.5,18.9),20:(19.7,21.9,23.6,23.3),30:(23.6,25.7,27.4,26.5),40:(26.2,28.2,29.8,28.4),50:(28.1,29.9,31.4,29.7),60:(29.4,31.2,32.6,30.6)},
"AT2": {0:(0,0,0,0),2:(8.0,9.6,11.1,12.4),4:(14.7,17.3,19.8,21.5),6:(20.3,23.7,26.7,28.4),8:(25.2,29.0,32.4,33.9),10:(29.3,33.5,37.1,38.3),12:(33.0,37.3,41.2,42.0)},
}}
_AT_M = {
"HP": {
"AT1": {0:(2.5,3.0,3.6,4.1),5:(2.2,2.7,3.2,3.7),10:(2.0,2.4,2.9,3.2),15:(1.7,2.1,2.5,2.8),20:(1.5,1.8,2.2,2.3),25:(1.2,1.5,1.8,1.8),30:(1.0,1.2,1.4,1.4)},
"AT2": {0:(5.3,6.4,7.6,8.7),5:(5.0,6.1,7.2,8.3),10:(4.8,5.8,6.9,7.8),15:(4.5,5.5,6.5,7.4),20:(4.3,5.2,6.2,6.9),25:(4.0,4.9,5.8,6.4),30:(3.7,4.6,5.4,6.0)},
},
"SP": {
"AT1": {0:(2.0,2.4,2.9,3.3),5:(1.7,2.1,2.5,2.8),10:(1.5,1.8,2.1,2.4),15:(1.2,1.5,1.8,1.9),20:(1.0,1.2,1.4,1.5),25:(0.7,0.9,1.1,1.0),30:(0.5,0.6,0.7,0.6)},
"AT2": {0:(4.4,5.4,6.4,7.3),5:(4.2,5.1,6.0,6.9),10:(3.9,4.8,5.6,6.4),15:(3.7,4.5,5.3,5.9),20:(3.4,4.2,4.9,5.5),25:(3.2,3.9,4.6,5.0),30:(2.9,3.6,4.2,4.6)},
}}
_AT_V = {
"HP": {"AT1": {1:(6.2,6.8,7.9),2:(12.4,13.6,15.8)}, "AT2": {1:(7.9,8.7,10.1),2:(15.8,17.4,20.1)}},
"SP": {"AT1": {1:(5.1,5.9,6.8),2:(10.2,11.7,13.6)}, "AT2": {1:(6.5,7.5,8.7),2:(13.0,15.0,17.4)}},
}

# --- FT tables, HIT 20.2-EN pp.140-141 ---
_FT_N_POS = {
"HP": {50:(56.6,60.4,63.4,59.9),40:(52.9,56.9,60.1,57.3),30:(47.7,51.9,55.3,53.4),20:(39.8,44.1,47.7,47.1),12:(29.9,33.9,37.4,38.1),10:(26.6,30.4,33.7,34.8),8:(22.8,26.3,29.4,30.8),6:(18.5,21.5,24.3,25.8),4:(13.4,15.7,18.0,19.5),2:(7.3,8.7,10.1,11.2),0:(0,0,0,0)},
"SP": {50:(56.6,60.4,63.4,59.9),40:(52.9,56.9,60.1,57.3),30:(47.7,51.9,55.3,53.4),20:(39.8,44.1,47.7,47.1),12:(29.9,33.9,37.4,38.1),10:(26.6,30.4,33.7,34.8),8:(22.8,26.3,29.4,30.8),6:(18.5,21.5,24.3,25.8),4:(13.4,15.7,18.0,19.5),2:(6.4,8.0,9.6,11.1),0:(0,0,0,0)},
}
_FT_N_NEG = {
"HP": {0:(0,0,0,0),-2:(-6.4,-7.6,-8.8,-9.8),-4:(-11.7,-13.8,-15.7,-17.1),-6:(-16.2,-18.8,-21.2,-22.6),-8:(-20.0,-23.0,-25.8,-26.9),-10:(-23.3,-26.6,-29.5,-30.4),-12:(-26.2,-29.7,-32.7,-33.4),-20:(-34.8,-38.6,-41.7,-41.2),-30:(-41.7,-45.4,-48.4,-46.8),-40:(-46.3,-49.8,-52.6,-50.1),-50:(-49.6,-52.9,-55.5,-52.4)},
"SP": {0:(0,0,0,0),-2:(-5.4,-6.4,-7.4,-8.3),-4:(-9.8,-11.6,-13.2,-14.3),-6:(-13.6,-15.8,-17.8,-18.9),-8:(-16.8,-19.3,-21.6,-22.6),-10:(-19.5,-22.3,-24.8,-25.5),-12:(-22.0,-24.9,-27.4,-28.0),-20:(-29.2,-32.4,-35.0,-34.6),-30:(-35.0,-38.1,-40.6,-39.2),-40:(-38.8,-41.8,-44.1,-42.0),-50:(-41.6,-44.4,-46.5,-43.9)},
}
_FT_M_POS = {
"HP": {70:(0.5,0.6,0.8,0.3),60:(1.0,1.2,1.5,1.2),50:(1.5,1.8,2.2,2.1),40:(2.0,2.5,2.9,3.0),30:(2.5,3.1,3.6,3.9),25:(2.7,3.4,4.0,4.4),20:(3.0,3.7,4.3,4.8),15:(3.3,4.0,4.7,5.3),10:(3.5,4.3,5.1,5.7),5:(3.7,4.5,5.4,6.1)},
"SP": {70:(0.5,0.6,0.8,0.3),60:(1.0,1.2,1.5,1.2),50:(1.5,1.8,2.2,2.1),40:(2.0,2.5,2.9,3.0),30:(2.5,3.1,3.6,3.9),25:(2.7,3.4,4.0,4.4),20:(3.0,3.7,4.3,4.8),15:(3.3,4.0,4.7,5.3),10:(3.4,4.1,4.8,5.5),5:(3.2,3.8,4.5,5.2)},
}
_FT_M_NEG = {
"HP": {0:(3.5,4.3,5.0,5.8),-5:(3.3,4.0,4.7,5.4),-10:(3.0,3.7,4.3,4.9),-15:(2.8,3.4,4.0,4.4),-20:(2.5,3.1,3.6,4.0),-25:(2.2,2.8,3.3,3.5),-30:(2.0,2.5,2.9,3.1),-35:(1.7,2.1,2.6,2.6),-40:(1.5,1.8,2.2,2.2),-45:(1.2,1.5,1.9,1.7),-50:(1.0,1.2,1.5,1.3)},
"SP": {0:(3.0,3.6,4.2,4.9),-5:(2.7,3.3,3.9,4.4),-10:(2.4,3.0,3.5,4.0),-15:(2.2,2.7,3.2,3.5),-20:(1.9,2.4,2.8,3.1),-25:(1.7,2.1,2.5,2.6),-30:(1.4,1.8,2.1,2.1),-35:(1.2,1.5,1.7,1.7),-40:(0.9,1.2,1.4,1.2),-45:(0.7,0.8,1.0,0.8),-50:(0.4,0.5,0.7,0.3)},
}
_FT_V = {
"HP": {2:(((13.6,15.8),(15.0,17.4),(17.4,20.1))),3:(((20.4,20.4),(22.5,26.1),(26.0,26.0)))},
"SP": {2:(((11.2,13.0),(12.9,15.0),(15.0,17.4))),3:(((16.8,19.5),(19.3,22.5),(22.5,26.1)))},
}

def _conc_index(concrete:str)->int:
    return 0 if concrete == 'C20/25' else 1

def _spacing_from_limits(n:float, nrd:float|None, m:float, mrd:float|None, v:float, vrd:float|None)->float:
    limits=[]
    if n>TOL:
        if not nrd or abs(nrd)<=TOL: return 0.0
        limits.append(abs(nrd)/n)
    if m>TOL and n<=TOL:
        # For pure moment the ratio method degenerates; use tabulated M at N=0.
        if not mrd or abs(mrd)<=TOL: return 0.0
        limits.append(abs(mrd)/m)
    if v>TOL:
        if not vrd or abs(vrd)<=TOL: return 0.0
        limits.append(abs(vrd)/v)
    return min(limits) if limits else math.inf

def design_at(series:str,height:int,m_pos:float,m_neg:float,n_pos:float,n_neg:float,v_pos:float,v_neg:float):
    series=series.upper(); height=int(height)
    if n_pos>TOL: return [], 'AT je v katalogových tabulkách ověřen pro tlakovou normálovou sílu NEd−; NEd+ musí být 0.'
    i4=_band(height,_H4); i3=_band(height,_H3)
    if i4 is None or i3 is None: return [], 'AT má ověřené katalogové hodnoty pro h = 160 až 250 mm.'
    m=max(abs(m_pos),abs(m_neg)); n=abs(n_neg); v=max(abs(v_pos),abs(v_neg))
    if n>TOL and m<=TOL: return [], 'AT: pro nenulovou NEd− a MEd = 0 není katalogová metoda |nEd/mEd| definována.'
    ratio=0.0 if n<=TOL else n/m
    out=[]
    for subtype,loops in [('AT1',2),('AT2',3)]:
        nrd_mag=_interp(_AT_N[series][subtype],ratio,i4)
        if n>TOL and nrd_mag is None: continue
        nrd=-(nrd_mag or 0.0)
        mrd=None
        if abs(nrd)<=30+TOL:
            mrd=_interp(_AT_M[series][subtype],abs(nrd),i4)
        elif n<=TOL:
            mrd=_interp(_AT_M[series][subtype],0.0,i4)
        for shear_count in (1,2):
            vrd=float(_AT_V[series][subtype][shear_count][i3])
            amax=_spacing_from_limits(n,nrd,m,mrd,v,vrd)
            if not math.isfinite(amax) or amax < 0.25-TOL: continue
            code=f'{subtype}-{loops:02d}{shear_count:02d}'
            out.append({'type':'AT','code':code,'suffix':'','mrd':float(mrd or 0.0),'vrd':vrd,'nrd':nrd,'amax':amax,'x_mm':0.0,'page':132 if series=='HP' else 133,'mode':f'AT • amax {amax:.3f} m • |n/m|={ratio:.3f} 1/m','source':'HIT 20.2-EN pp.131-134'})
    out.sort(key=lambda r:(-r['amax'], r['code']))
    return out,''

def _ft_case_spacing(series:str,height_idx:int,n:float,m:float,positive:bool):
    if n<=TOL:
        # use N=0 negative-side moment capacity
        mrd=_interp_signed(_FT_M_NEG[series],0.0,height_idx)
        return math.inf,0.0,mrd
    if m<=TOL: return 0.0,0.0,None
    ratio=n/m
    if positive:
        nrd=_interp(_FT_N_POS[series],ratio,height_idx)
        if nrd is None: return 0.0,0.0,None
        # M table positive N is keyed by N itself, not ratio.
        mrd=_interp(_FT_M_POS[series],nrd,height_idx)
        return nrd/n,nrd,mrd
    nrd=_interp_signed(_FT_N_NEG[series],-ratio,height_idx)
    if nrd is None: return 0.0,0.0,None
    mrd=_interp_signed(_FT_M_NEG[series],nrd,height_idx)
    return abs(nrd)/n,nrd,mrd

def design_ft(series:str,height:int,concrete:str,m_pos:float,m_neg:float,n_pos:float,n_neg:float,v_pos:float,v_neg:float):
    series=series.upper(); height=int(height)
    i4=_band(height,_H4); i3=_band(height,_H3)
    if i4 is None or i3 is None: return [], 'FT má ověřené katalogové hodnoty pro h = 160 až 250 mm.'
    m=max(abs(m_pos),abs(m_neg)); np=abs(n_pos); nn=abs(n_neg); vp=abs(v_pos); vn=abs(v_neg)
    pos_space,pos_nrd,pos_mrd=_ft_case_spacing(series,i4,np,m,True)
    neg_space,neg_nrd,neg_mrd=_ft_case_spacing(series,i4,nn,m,False)
    if np>TOL and pos_space<=TOL: return [], 'FT: kombinace NEd+ / MEd je mimo rozsah katalogové interakční tabulky.'
    if nn>TOL and neg_space<=TOL: return [], 'FT: kombinace NEd− / MEd je mimo rozsah katalogové interakční tabulky.'
    base_limits=[]
    if np>TOL: base_limits.append(pos_space)
    if nn>TOL: base_limits.append(neg_space)
    if np<=TOL and nn<=TOL and m>TOL:
        mrd0=min(v for v in (pos_mrd,neg_mrd) if v is not None)
        base_limits.append(mrd0/m)
    ci=_conc_index(concrete)
    out=[]
    # FT1 is the one-direction shear type; the capacity table is negative, so VEd+ excludes FT1.
    for subtype in ('FT1','FT2'):
        if subtype=='FT1' and vp>TOL: continue
        for shear_count in (2,3):
            vrd=float(_FT_V[series][shear_count][i3][ci])
            v=max(vp,vn) if subtype=='FT2' else vn
            limits=list(base_limits)
            if v>TOL: limits.append(vrd/v)
            if not limits: continue
            amax=min(limits)
            if amax < 0.25-TOL: continue
            nrd = pos_nrd if np>=nn else neg_nrd
            mrd_candidates=[x for x in (pos_mrd if np>TOL else None, neg_mrd if nn>TOL else None) if x is not None] if False else []
            mrd = min([x for x in (pos_mrd,neg_mrd) if x is not None], default=0.0)
            code=f'{subtype}-02{shear_count:02d}'
            direction='V−' if subtype=='FT1' else 'V±'
            out.append({'type':'FT','code':code,'suffix':'','mrd':float(mrd or 0.0),'vrd':vrd,'nrd':float(nrd or 0.0),'amax':amax,'x_mm':0.0,'page':140 if series=='HP' else 141,'mode':f'{subtype} • {direction} • amax {amax:.3f} m','source':'HIT 20.2-EN pp.139-142'})
    out.sort(key=lambda r:(-r['amax'], 0 if r['code'].startswith('FT1') else 1, r['code']))
    return out,''

# OTX tables: each entry is (C20/25, >=C25/30), indexed by load distance x.
_X1=(75,85,95,105); _X2=(75,85,95,105,115,125,135,145)

def _pairs(nums):
    return tuple((float(nums[i]),float(nums[i+1])) for i in range(0,len(nums),2))

def _const_pairs(pair,n): return tuple(pair for _ in range(n))

_OTX={
'HP':{
 'OTX1':{
  6:{180:_pairs((27.3,28.0,25.9,26.7,24.6,25.4,23.5,24.2)),190:_pairs((28,28,28,28,27.6,28,26.2,27.0)),200:_pairs((28.8,28.8,28.8,28.8,28.8,28.8,28.1,28.8)),210:_const_pairs((28.8,28.8),4),220:_const_pairs((28.8,28.8),4),230:_const_pairs((28.8,28.8),4),240:_const_pairs((29.7,29.7),4),250:_const_pairs((29.7,29.7),4)},
  8:{180:_pairs((27.8,28.7,26.4,27.2,25.0,25.8,23.8,24.6)),190:_pairs((31.4,32.4,29.7,30.6,28.1,29.0,26.7,27.5)),200:_pairs((32.8,33.7,31.1,31.9,29.5,30.3,28.1,28.8)),210:_pairs((36.4,37.3,34.4,35.2,32.6,33.4,31.0,31.7)),220:_pairs((40.2,41.2,37.9,38.8,35.9,36.7,34.0,34.8)),230:_pairs((44.4,46.4,41.7,42.7,39.4,40.2,37.3,38.1)),240:_pairs((42.8,43.7,40.5,41.3,38.5,39.2,36.6,37.3)),250:_pairs((46.4,47.2,43.8,44.6,41.5,42.3,39.5,40.2))}},
 'OTX2':{
  6:{180:_pairs((27.3,28.0,25.9,26.7,24.6,25.4,23.5,24.2,22.4,23.1,21.4,22.1,20.6,21.2,19.7,20.3)),190:_pairs((28,28,28,28,27.6,28,26.2,27.0,25.0,25.7,23.9,24.6,22.9,23.5,22.0,22.6)),200:_pairs((28.8,28.8,28.8,28.8,28.8,28.8,28.1,28.8,26.8,27.5,25.6,26.3,24.5,25.2,23.6,24.1)),210:_pairs((28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.2,28.8,27.0,27.6,25.9,26.4)),220:_pairs((28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.8,28.3,28.8)),230:_const_pairs((28.8,28.8),8),240:_const_pairs((29.7,29.7),8),250:_const_pairs((29.7,29.7),8)},
  8:{180:_pairs((27.8,28.7,26.4,27.2,25.0,25.8,23.8,24.6,22.7,23.4,21.8,22.4,20.8,21.5,20.0,20.6)),190:_pairs((31.4,32.4,29.7,30.6,28.1,29.0,26.7,27.5,25.5,26.2,24.3,25.0,23.3,23.9,22.3,22.9)),200:_pairs((32.8,33.7,31.1,31.9,29.5,30.3,28.1,28.8,26.8,27.5,25.6,26.3,24.5,25.2,23.6,24.1)),210:_pairs((36.4,37.3,34.4,35.2,32.6,33.4,31.0,31.7,29.5,30.2,28.2,28.8,27.0,27.6,25.9,26.4)),220:_pairs((40.2,41.2,37.9,38.8,35.9,36.7,34.0,34.8,32.4,33.1,30.9,31.5,29.5,30.1,28.3,28.9)),230:_pairs((44.4,46.4,41.7,42.7,39.4,40.2,37.3,38.1,35.4,36.1,33.7,34.4,32.2,32.8,30.8,31.4)),240:_pairs((42.8,43.7,40.5,41.3,38.5,39.2,36.6,37.3,34.9,35.6,33.4,34.0,32.0,32.6,30.7,31.2)),250:_pairs((46.4,47.2,43.8,44.6,41.5,42.3,39.5,40.2,37.6,38.3,35.9,36.6,34.4,35.0,33.0,33.5))}}
},
'SP':{
 'OTX1':{
  6:{180:_pairs((22.5,22.7,22.5,22.7,22.5,22.7,21.7,22.4)),190:_const_pairs((22.5,22.7),4),200:_const_pairs((24.0,24.1),4),210:_const_pairs((24.0,24.1),4),220:_const_pairs((24.0,24.1),4),230:_const_pairs((24.0,24.1),4),240:_const_pairs((25.6,25.7),4),250:_const_pairs((25.6,25.7),4)},
  8:{180:_pairs((25.5,26.4,24.2,25.1,23.1,23.9,22.1,22.8)),190:_pairs((29.1,30.2,27.6,28.6,26.2,27.1,25.0,25.8)),200:_pairs((33.3,34.4,31.4,32.5,29.8,30.7,28.3,29.1)),210:_pairs((35.9,36.7,35.8,36.7,33.8,34.8,32.0,32.8)),220:_pairs((37.5,38.6,35.5,36.4,33.6,34.5,32.0,32.7)),230:_pairs((40.1,40.7,39.5,40.5,37.3,38.3,35.4,36.2)),240:_pairs((40.9,41.8,38.7,39.7,36.8,37.7,35.1,35.8)),250:_pairs((43.5,43.9,42.4,43.3,40.2,41.1,38.2,38.9))}},
 'OTX2':{
  6:{180:_pairs((22.5,22.7,22.5,22.7,22.5,22.7,21.7,22.4,20.8,21.5,19.9,20.6,19.2,19.8,18.5,19.1)),190:_pairs((22.5,22.7,22.5,22.7,22.5,22.7,22.5,22.7,22.5,22.7,22.4,22.7,21.5,22.2,20.7,21.3)),200:_pairs((24.0,24.1,24.0,24.1,24.0,24.1,24.0,24.1,24.0,24.1,23.8,24.1,22.9,23.5,22.0,22.7)),210:_const_pairs((24.0,24.1),8),220:_const_pairs((24.0,24.1),8),230:_const_pairs((24.0,24.1),8),240:_const_pairs((25.6,25.7),8),250:_const_pairs((25.6,25.7),8)},
  8:{180:_pairs((25.4,26.4,24.2,25.1,23.0,23.9,22.0,22.8,21.1,21.8,20.2,20.9,19.4,20.1,18.7,19.3)),190:_pairs((29.0,30.1,27.5,28.5,26.2,27.1,25.0,25.8,23.8,24.6,22.8,23.6,21.9,22.6,21.0,21.7)),200:_pairs((33.2,34.3,31.3,32.4,29.7,30.7,28.2,29.1,26.9,27.7,25.7,26.5,24.6,25.3,23.6,24.3)),210:_pairs((35.9,36.7,35.7,36.7,33.7,34.7,31.9,32.8,30.3,31.2,28.8,29.7,27.5,28.3,26.3,27.1)),220:_pairs((37.4,38.5,35.4,36.4,33.6,34.5,31.9,32.8,30.5,31.3,29.1,29.9,27.9,28.6,26.8,27.4)),230:_pairs((40.1,40.7,39.4,40.4,37.3,38.2,35.4,36.2,33.6,34.5,32.1,32.9,30.7,31.4,29.4,30.1)),240:_pairs((40.5,41.8,38.7,39.6,36.8,37.6,35.0,35.8,33.5,34.2,32.0,32.8,30.7,31.4,29.5,30.2)),250:_pairs((42.5,43.9,42.3,43.2,40.1,41.0,38.2,39.0,36.4,37.2,34.8,35.5,33.3,34.0,32.0,32.6))}}
}}

def _next_x(x:float, allowed):
    for val in allowed:
        if x <= val+TOL: return val
    return None

def design_otx(series:str,height:int,concrete:str,n_pos:float,n_neg:float,v_pos:float,v_neg:float,x_mm:float):
    series=series.upper(); height=int(height); x=float(x_mm)
    if v_neg>TOL: return [], 'OTX přenáší smyk v jednom katalogovém směru; VEd− musí být 0.'
    if height not in (180,190,200,210,220,230,240,250): return [], 'OTX má ověřené katalogové hodnoty pro h = 180 až 250 mm po 10 mm.'
    if x<=0: return [], 'OTX vyžaduje vzdálenost zatížení x [mm].'
    n=max(abs(n_pos),abs(n_neg)); v=abs(v_pos); ci=_conc_index(concrete)
    out=[]
    for subtype,allowed in [('OTX1',_X1),('OTX2',_X2)]:
        xcol=_next_x(x,allowed)
        if xcol is None: continue
        xi=allowed.index(xcol)
        for dia in (6,8):
            vrd=float(_OTX[series][subtype][dia][height][xi][ci])
            nrd=0.1*vrd
            limits=[]
            if v>TOL: limits.append(vrd/v)
            if n>TOL: limits.append(nrd/n)
            if not limits: continue
            amax=min(limits)
            if amax < 0.25-TOL: continue
            out.append({'type':'OTX','code':f'{subtype}-0202','suffix':f'{dia:02d}','mrd':0.0,'vrd':vrd,'nrd':nrd,'amax':amax,'x_mm':x,'x_used':xcol,'page':146 if series=='HP' else 148,'mode':f'{subtype} • x={x:g} mm → tabulka {xcol} mm • amax {amax:.3f} m','source':'HIT 20.2-EN pp.146-149'})
    out.sort(key=lambda r:(-r['amax'], 0 if r['code'].startswith('OTX1') else 1, int(r['suffix'])))
    return out,''

def design_special(connection_type:str, series:str, height:int, concrete:str, *, m_pos=0.0,m_neg=0.0,n_pos=0.0,n_neg=0.0,v_pos=0.0,v_neg=0.0,x_mm=0.0):
    typ=connection_type.upper()
    if typ=='AT': return design_at(series,height,m_pos,m_neg,n_pos,n_neg,v_pos,v_neg)
    if typ=='FT': return design_ft(series,height,concrete,m_pos,m_neg,n_pos,n_neg,v_pos,v_neg)
    if typ=='OTX':
        if m_pos>TOL or m_neg>TOL: return [], 'OTX v aktuálním katalogu přenáší N a V, nikoli M; MEd musí být 0.'
        return design_otx(series,height,concrete,n_pos,n_neg,v_pos,v_neg,x_mm)
    return [], f'Nepodporovaný speciální typ {typ}.'
