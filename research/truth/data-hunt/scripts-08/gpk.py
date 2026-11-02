"""Minimal GeoPackage polygon reader, no GDAL. Returns (attrs, rings) with SWEREF99TM coords."""
import sqlite3,struct
def wkb(b,p=0):
    rs=[];e='<' if b[p]==1 else '>';t=struct.unpack(e+'I',b[p+1:p+5])[0];p+=5
    t=t%1000
    if t==3:
        n=struct.unpack(e+'I',b[p:p+4])[0];p+=4
        for i in range(n):
            m=struct.unpack(e+'I',b[p:p+4])[0];p+=4
            import numpy as np
            a=np.frombuffer(b,dtype=e+'f8',count=2*m,offset=p).reshape(-1,2);p+=16*m
            rs.append(a)
        return rs,p
    if t==6:
        n=struct.unpack(e+'I',b[p:p+4])[0];p+=4
        for i in range(n):
            r,p=wkb(b,p);rs+=r[:1]
        return rs,p
    raise ValueError(t)
def geom(g):
    fl=g[3];env=(fl>>1)&7;sz={0:0,1:32,2:48,3:48,4:64}[env];return wkb(g,8+sz)[0]
def read(path,cols):
    c=sqlite3.connect(path);t=c.execute("select table_name from gpkg_contents").fetchone()[0]
    for row in c.execute(f'select {",".join(cols)},sp_geometry from "{t}"'):
        yield row[:-1],geom(row[-1])
