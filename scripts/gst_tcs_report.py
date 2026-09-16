from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
TCS_RATE=Decimal('0.005')
def d(v): return Decimal(str(v or 0))
def money(v): return v.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
def collected_at(o): return o.get('paymentCollectedAt') or o.get('paymentVerifiedAt') or (o.get('updatedAt') if o.get('paymentStatus')=='paid' else None)
def month_of(v): return str(v or '')[:7]
def rows(state,month):
    # Deferred while product GST/HSN billing is disabled. Do not calculate filing values from zero-GST order snapshots.
    return []

def _rows_when_product_gst_enabled(state,month):
    agg=defaultdict(lambda:{'storeName':'','taxable':Decimal(0),'gst':Decimal(0),'gross':Decimal(0),'missingHsn':0,'orders':set()})
    for o in state.get('orders',{}).values():
        if o.get('isPaymentTestOrder') or month_of(collected_at(o))!=month or o.get('status') in {'cancelled','returned'}: continue
        for item in o.get('items',[]):
            sid=str(item.get('storeId') or 'UNKNOWN')
            a=agg[sid]; a['storeName']=str(item.get('storeName') or sid); a['orders'].add(str(o.get('id')))
            a['taxable']+=d(item.get('taxableValue')); a['gst']+=d(item.get('gstAmount')); a['gross']+=d(item.get('lineTotal'))
            if not item.get('hsnCode'): a['missingHsn']+=1
    out=[]
    for sid,a in sorted(agg.items()):
        tcs=money(a['taxable']*TCS_RATE)
        out.append({'month':month,'supplierId':sid,'storeName':a['storeName'],'supplierGstin':'REQUIRED_FOR_REGISTERED_SUPPLIER','taxableValue':str(money(a['taxable'])),'gstIncluded':str(money(a['gst'])),'grossMerchandiseValue':str(money(a['gross'])),'tcsRate':'0.50%','tcsAmount':str(tcs),'cgstTcs':'0.25%','sgstTcs':'0.25%','orderCount':len(a['orders']),'missingHsnLines':a['missingHsn']})
    return out
def main():
    ap=argparse.ArgumentParser(description='Generate Vibe4You monthly GST/TCS reconciliation without changing order state.')
    ap.add_argument('--state',type=Path,required=True); ap.add_argument('--month',required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    if len(args.month)!=7 or args.month[4]!='-': raise SystemExit('month must be YYYY-MM')
    state=json.loads(args.state.read_text(encoding='utf-8-sig')); data=rows(state,args.month); args.output.parent.mkdir(parents=True,exist_ok=True)
    fields=['month','supplierId','storeName','supplierGstin','taxableValue','gstIncluded','grossMerchandiseValue','tcsRate','tcsAmount','cgstTcs','sgstTcs','orderCount','missingHsnLines']
    with args.output.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(data)
    print(f'gst_tcs_report={args.output} suppliers={len(data)}')
if __name__=='__main__': main()
