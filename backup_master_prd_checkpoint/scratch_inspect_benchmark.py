import re
from extractor import extract_text_from_pdf_path

t_text = extract_text_from_pdf_path('Tender_50_Requirements_Messy_Synthetic.pdf')
lines = [l.strip() for l in t_text.split('\n') if l.strip()]
reqs = {}
for i, l in enumerate(lines):
    m = re.match(r'^(T\d{2})$', l)
    if m:
        reqs[m.group(1)] = {
            'name': lines[i+1],
            'spec': lines[i+2],
            'cond': lines[i+3],
            'oblg': lines[i+4],
        }

def parse_vendor_table(vname):
    text = extract_text_from_pdf_path(vname)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    claims_by_t = {}
    i = 0
    while i < len(lines):
        if 'Technical Schedule / Item T' in lines[i]:
            m = re.search(r'T\d{2}', lines[i])
            if m and i >= 2:
                claims_by_t[m.group()] = f"{lines[i-2]}: {lines[i-1]}"
        i += 1
    for i in range(len(lines)):
        m = re.match(r'^(T\d{2})$', lines[i])
        if m:
            val = lines[i+1] if i+1 < len(lines) else ''
            claims_by_t[m.group(1)] = val
    return claims_by_t

aurora = parse_vendor_table('Vendor_AuroraGrid_Synthetic_Bid.pdf')
nova = parse_vendor_table('Vendor_NovaLite_Synthetic_Bid.pdf')
ecoray = parse_vendor_table('Vendor_EcoRay_Synthetic_Bid.pdf')

for t_code in sorted(reqs.keys()):
    r = reqs[t_code]
    print(f"=== {t_code}: {r['name']} ({r['cond']}, {r['oblg']}) ===")
    print(f"  Tender: {r['spec']}")
    print(f"  Aurora: {aurora.get(t_code, '[NOT FOUND]')}")
    print(f"  Nova  : {nova.get(t_code, '[NOT FOUND]')}")
    print(f"  EcoRay: {ecoray.get(t_code, '[NOT FOUND]')}")
