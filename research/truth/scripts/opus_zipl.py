import zipfile,sys
for f in sys.argv[1:]:
    z=zipfile.ZipFile(f)
    for i in z.infolist():
        n=i.filename.lower()
        if any(k in n for k in ('signal','timing','phase','.pdf','.doc','.txt','.xls')) and i.file_size<5e7: print(f.split('/')[-1],i.filename,i.file_size)
    print(len(z.infolist()))
