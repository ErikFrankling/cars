import json,sys,glob
for f in sorted(glob.glob(sys.argv[1]+'/*.json')):
    j=json.load(open(f))
    print('==',j.get('id'),j.get('name'),'| lic',j.get('license',{}).get('name') if j.get('license') else j.get('licenseId'))
    print(' desc:',(j.get('description') or '')[:900].replace('\n',' '))
    print(' cols:',[c['fieldName'] for c in j.get('columns',[])])
    print(' attach:',[(a.get('filename') or a.get('name'),a.get('assetId') or a.get('blobId')) for a in j.get('metadata',{}).get('attachments',[])])
