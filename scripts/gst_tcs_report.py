from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def rows(_state, _month):
    # Deferred while product GST/HSN billing is disabled.
    return []
def main():
    ap=argparse.ArgumentParser(description='Deferred Vibe4You GST/TCS report: emits no filing rows while product GST is disabled.')
    ap.add_argument('--state',type=Path,required=True); ap.add_argument('--month',required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    if len(args.month)!=7 or args.month[4]!='-': raise SystemExit('month must be YYYY-MM')
    state=json.loads(args.state.read_text(encoding='utf-8-sig')); data=rows(state,args.month); args.output.parent.mkdir(parents=True,exist_ok=True)
    fields=['month','supplierId','storeName','supplierGstin','taxableValue','gstIncluded','grossMerchandiseValue','tcsRate','tcsAmount','cgstTcs','sgstTcs','orderCount','missingHsnLines']
    with args.output.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(data)
    print(f'gst_tcs_report={args.output} suppliers={len(data)}')
if __name__=='__main__': main()
