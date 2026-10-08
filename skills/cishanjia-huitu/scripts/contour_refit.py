"""Refit one measured silhouette to coherent cubics, not a source-color trace."""
from __future__ import annotations
import numpy as np

def unit(v):
    length=np.linalg.norm(v)
    return v/max(length,1e-12)

def bezier(curve,t):
    t=np.asarray(t);u=1-t
    return u[...,None]**3*curve[0]+3*u[...,None]**2*t[...,None]*curve[1]+3*u[...,None]*t[...,None]**2*curve[2]+t[...,None]**3*curve[3]

def fit(points,tolerance=.45,*,start_tangent=None,end_tangent=None):
    """Adaptive tangent-preserving fit; tolerance uses input coordinate units."""
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or not np.isfinite(p).all() or not np.isfinite(tolerance) or tolerance<=0:
        raise ValueError('Finite measured contour points and positive tolerance required')
    if np.any(np.linalg.norm(np.diff(p,axis=0),axis=1)<1e-9):raise ValueError('Consecutive contour points must be distinct')
    def recurse(data,left,right,depth=0):
        if len(data)==2:
            distance=np.linalg.norm(data[-1]-data[0])/3
            return [np.array([data[0],data[0]+left*distance,data[-1]+right*distance,data[-1]])]
        steps=np.linalg.norm(np.diff(data,axis=0),axis=1);parameters=np.r_[0,np.cumsum(steps)]/max(steps.sum(),1e-12)
        def generate(t):
            u=1-t;b1=3*t*u*u;b2=3*t*t*u
            a1=b1[:,None]*left;a2=b2[:,None]*right
            residual=data-((u**3+b1)[:,None]*data[0]+(t**3+b2)[:,None]*data[-1])
            matrix=np.array([[np.sum(a1*a1),np.sum(a1*a2)],[np.sum(a1*a2),np.sum(a2*a2)]])
            rhs=np.array([np.sum(a1*residual),np.sum(a2*residual)])
            try:alpha=np.linalg.solve(matrix,rhs)
            except np.linalg.LinAlgError:alpha=np.array([-1.,-1.])
            distance=np.linalg.norm(data[-1]-data[0])
            if np.min(alpha)<distance*1e-6:alpha[:]=distance/3
            return np.array([data[0],data[0]+left*alpha[0],data[-1]+right*alpha[1],data[-1]])
        curve=generate(parameters)
        error=np.sum((bezier(curve,parameters)-data)**2,axis=1);split=int(np.argmax(error))
        if error[split]<=tolerance*tolerance:return [curve]
        if error[split]<tolerance*tolerance*4:
            for _ in range(4):
                q=bezier(curve,parameters)
                d=3*np.diff(curve,axis=0);dd=2*np.diff(d,axis=0)
                t=parameters;u=1-t
                q1=u[:,None]**2*d[0]+2*t[:,None]*u[:,None]*d[1]+t[:,None]**2*d[2]
                q2=u[:,None]*dd[0]+t[:,None]*dd[1]
                diff=q-data;den=np.sum(q1*q1+diff*q2,axis=1)
                new=np.clip(t-np.sum(diff*q1,axis=1)/np.where(abs(den)>1e-12,den,1),0,1)
                if np.any(np.diff(new)<0):break
                parameters=new;curve=generate(parameters)
                error=np.sum((bezier(curve,parameters)-data)**2,axis=1);split=int(np.argmax(error))
                if error[split]<=tolerance*tolerance:return [curve]
        split=max(1,min(len(data)-2,split))
        if depth>30:raise ValueError('Contour fit failed to converge')
        center=unit(data[split-1]-data[split+1])
        return recurse(data[:split+1],left,center,depth+1)+recurse(data[split:],-center,right,depth+1)
    def tangent(value,fallback):
        if value is None:return unit(fallback)
        v=np.asarray(value,dtype=float)
        if v.shape!=(2,) or not np.isfinite(v).all() or np.linalg.norm(v)<1e-9:raise ValueError('Finite nonzero contour tangent required')
        return unit(v)
    return recurse(p,tangent(start_tangent,p[1]-p[0]),tangent(end_tangent,p[-2]-p[-1]))

def closed_path(points,tolerance=.45,spacing=.5):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<4 or not np.isfinite(p).all():raise ValueError('Closed biological silhouette needs finite two-dimensional landmarks')
    if not np.isfinite(spacing) or spacing<=0:raise ValueError('Positive finite contour spacing required')
    if not np.isfinite(tolerance) or tolerance<=0:raise ValueError('Positive finite contour tolerance required')
    if np.linalg.norm(p[0]-p[-1])<1e-9:p=p[:-1]
    if len(p)<4:raise ValueError('Closed biological silhouette needs at least four distinct landmarks')
    # Uniform arc sampling and a short circular filter remove pixel stair-steps.
    closed=np.vstack([p,p[0]]);lengths=np.linalg.norm(np.diff(closed,axis=0),axis=1)
    if np.any(lengths<1e-9):raise ValueError('Consecutive contour points must be distinct')
    arc=np.r_[0,np.cumsum(lengths)]
    if arc[-1]/spacing>200000:raise ValueError('Contour spacing requests too many samples')
    samples=np.linspace(0,arc[-1],max(8,int(np.ceil(arc[-1]/spacing))),endpoint=False)
    uniform=np.column_stack([np.interp(samples,arc,closed[:,k]) for k in range(2)])
    smoothed=sum(weight*np.roll(uniform,offset,axis=0) for offset,weight in [(-2,.0625),(-1,.25),(0,.375),(1,.25),(2,.0625)])
    # Four arcs avoid a degenerate full-cycle endpoint pair.
    indices=np.linspace(0,len(smoothed),5,dtype=int)
    ring=np.vstack([smoothed,smoothed[0]]);curves=[]
    for a,b in zip(indices[:-1],indices[1:]):curves.extend(fit(ring[a:b+1],tolerance))
    out=[f'M {curves[0][0,0]:.4f} {curves[0][0,1]:.4f}']
    for c in curves:out.append('C '+' '.join(f'{v:.4f}' for v in c[1:].ravel()))
    return ' '.join(out)+' Z',len(curves)

def landmark_path(points,landmarks,*,closed=True,tolerance=.45,spacing=.5):
    """Preserve measured anchor positions and explicit corner/smooth tangents.

    points follows one contour in order. landmarks has index/kind/name records;
    it never turns a whole-image color boundary into finished anatomy.
    """
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<(4 if closed else 2) or not np.isfinite(p).all():raise ValueError('Finite ordered contour points required')
    if not np.isfinite(spacing) or spacing<=0 or not np.isfinite(tolerance) or tolerance<=0:raise ValueError('Positive finite spacing/tolerance required')
    if np.any(np.linalg.norm(np.diff(p,axis=0),axis=1)<1e-9) or (closed and np.linalg.norm(p[-1]-p[0])<1e-9):raise ValueError('Do not duplicate adjacent points or the closing endpoint')
    anchors={}
    if not isinstance(landmarks,list):raise ValueError('Landmarks must be a list of records')
    for record in landmarks:
        if not isinstance(record,dict):raise ValueError('Landmark must be a measurement record')
        index=record.get('index');kind=record.get('kind','smooth')
        if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(p) or index in anchors or kind not in {'smooth','corner'}:raise ValueError('Unique valid landmark indices with smooth/corner kinds required')
        anchors[index]=dict(record,kind=kind)
    if closed and len(anchors)<2:raise ValueError('Closed contour requires at least two fixed landmarks')
    if not closed:
        for index in (0,len(p)-1):anchors.setdefault(index,{'index':index,'kind':'corner','name':'endpoint'})
    indices=sorted(anchors);curves=[]
    for n,a in enumerate(indices):
        if not closed and n==len(indices)-1:break
        b=indices[(n+1)%len(indices)]
        raw=p[a:b+1] if b>a else np.vstack([p[a:],p[:b+1]])
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(raw,axis=0),axis=1))]
        if arc[-1]/spacing>200000:raise ValueError('Contour spacing requests too many samples')
        count=max(2,int(np.ceil(arc[-1]/spacing))+1)
        # Retain measured vertices even when the requested spacing is coarse.
        t=np.unique(np.r_[np.linspace(0,arc[-1],count),arc])
        data=np.column_stack([np.interp(t,arc,raw[:,k]) for k in range(2)])
        # Endpoint-pinned smoothing removes stair steps without moving anatomy.
        smooth=data.copy()
        if len(data)>4:smooth[1:-1]=.25*data[:-2]+.5*data[1:-1]+.25*data[2:]
        measured=np.isin(t,arc);smooth[measured]=data[measured]
        smooth[0]=p[a];smooth[-1]=p[b]
        left=(p[(a+1)%len(p)]-p[(a-1)%len(p)]) if anchors[a]['kind']=='smooth' and (closed or 0<a<len(p)-1) else raw[1]-raw[0]
        right=(p[(b-1)%len(p)]-p[(b+1)%len(p)]) if anchors[b]['kind']=='smooth' and (closed or 0<b<len(p)-1) else raw[-2]-raw[-1]
        curves.extend(fit(smooth,tolerance,start_tangent=left,end_tangent=right))
    output=[f'M {curves[0][0,0]:.4f} {curves[0][0,1]:.4f}']
    for c in curves:output.append('C '+' '.join(f'{v:.4f}' for v in c[1:].ravel()))
    rounding_shift=float(np.linalg.norm(np.round(p[indices],4)-p[indices],axis=1).max())
    report={'fixed_landmarks':[dict(anchors[i],point=p[i].tolist()) for i in indices],'segments':len(curves),'closed':closed,'anchor_shift_px':rounding_shift,'meaning':'Pins declared anatomy; reported shift includes SVG coordinate rounding. Source inspection is still required.'}
    return ' '.join(output)+(' Z' if closed else ''),report
