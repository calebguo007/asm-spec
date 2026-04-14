#!/usr/bin/env python3
"""ASM A/B Test v2 - Taxonomy-filtered, real API calls via Knot.

Key improvements over v1:
  1. Only selects from ai.llm.chat services (Claude/Gemini/GPT-4o)
  2. Real latency measurement via Knot API
  3. Multiple preference scenarios and io_ratio settings
  4. Statistical significance testing (Welch's t-test)

Usage:
    python real_ab_test_v2.py --token YOUR_TOKEN
    python real_ab_test_v2.py --token YOUR_TOKEN --prompts 10 --rounds 3
    python real_ab_test_v2.py --token YOUR_TOKEN --skip-api  # simulation mode
"""
from __future__ import annotations
import argparse, csv, json, math, os, random, sys, time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)
from scorer import Preferences, load_manifests, parse_manifest, score_topsis

KNOT_API_BASE = "https://knot.woa.com/apigw/api/v1/agents/agui"
KNOT_AGENT_ID = "1b736d1c48cf451d894dda63434df0f9"

TEST_PROMPTS = [
    {"id":"fact_1","cat":"factual","prompt":"What is the capital of France? Answer in one sentence.","kw":["Paris"]},
    {"id":"fact_2","cat":"factual","prompt":"What year did World War II end? Answer in one sentence.","kw":["1945"]},
    {"id":"reason_1","cat":"reasoning","prompt":"If all roses are flowers and some flowers fade quickly, can we conclude some roses fade quickly? Explain in 2-3 sentences.","kw":["cannot","no"]},
    {"id":"reason_2","cat":"reasoning","prompt":"A bat and ball cost $1.10 total. Bat costs $1.00 more than ball. How much does ball cost? Show work.","kw":["0.05","5 cent"]},
    {"id":"creative_1","cat":"creative","prompt":"Write a haiku about artificial intelligence.","kw":[]},
    {"id":"creative_2","cat":"creative","prompt":"Describe a sunset in exactly 20 words.","kw":[]},
    {"id":"code_1","cat":"code","prompt":"Write a Python function that checks if a string is a palindrome. Include docstring.","kw":["def","palindrome"]},
    {"id":"code_2","cat":"code","prompt":"Write a JavaScript function that finds max value in array without Math.max.","kw":["function","max"]},
    {"id":"summary_1","cat":"summary","prompt":"Summarize machine learning in exactly 3 bullet points.","kw":["data","learn"]},
    {"id":"instruct_1","cat":"instruct","prompt":"List exactly 5 programming languages sorted alphabetically. One per line.","kw":[]},
]

PREF = {
    "balanced":      Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
    "cost_first":    Preferences(cost=0.55, quality=0.25, speed=0.10, reliability=0.10),
    "quality_first": Preferences(cost=0.10, quality=0.55, speed=0.20, reliability=0.15),
    "speed_first":   Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
}
IO = {"chat": 0.3, "balanced": 0.5, "rag": 0.8}

@dataclass
class Rec:
    round_id:int; prompt_id:str; category:str; group:str
    pref:str; io_name:str; io_ratio:float
    sid:str; name:str
    d_cost:float; d_lat:float; d_qual:float; d_up:float
    topsis:float; rank:int
    a_lat:float; rlen:int; qual:float; has_kw:bool; text:str

def call_api(token, prompt, timeout=120):
    url = f"{KNOT_API_BASE}/{KNOT_AGENT_ID}"
    h = {"Content-Type":"application/json","x-knot-api-token":token}
    b = {"input":{"message":prompt,"conversation_id":"","stream":False}}
    t0 = time.time()
    try:
        r = requests.post(url, json=b, headers=h, timeout=timeout)
        dt = time.time()-t0
        if r.status_code != 200: return f"[ERR:{r.status_code}]", dt
        return r.json().get("rawEvent",{}).get("content",""), dt
    except Exception as e: return f"[ERR:{e}]", time.time()-t0

def eval_resp(info, resp):
    s = 0.0
    if resp and len(resp.strip())>0: s += 0.15
    if len(resp.strip())>10: s += 0.15
    if not resp.startswith("[ERR"): s += 0.20
    kws = info.get("kw",[])
    if kws:
        found = sum(1 for k in kws if k.lower() in resp.lower())
        r = found/len(kws); s += 0.35*r; hk = r >= 0.5
    else: s += 0.35; hk = True
    if 10 < len(resp.strip()) < 5000: s += 0.15
    return round(min(s,1.0),4), hk

def run(token, manifests, prompts, rounds=1, seed=2024, skip=False):
    rng = random.Random(seed)
    llm = [m for m in manifests if m["taxonomy"]=="ai.llm.chat"]
    if len(llm)<2: print("Need >=2 ai.llm.chat"); return []
    print(f"\nLLM Chat ({len(llm)}):")
    for m in llm:
        sv=parse_manifest(m); print(f"  {sv.display_name} cost=${sv.cost_per_unit:.6f} qual={sv.quality_score:.3f} lat={sv.latency_seconds:.2f}s")
    total=len(prompts)*rounds*3
    print(f"\n{len(prompts)} prompts x {rounds} rounds x 3 = {total} calls")
    if not skip: print(f"~{total*8/60:.1f} min")
    recs=[]; cn=0
    for rd in range(1,rounds+1):
        pn=rng.choice(list(PREF.keys())); ion=rng.choice(list(IO.keys())); ior=IO[ion]
        p=Preferences(cost=PREF[pn].cost,quality=PREF[pn].quality,speed=PREF[pn].speed,reliability=PREF[pn].reliability,io_ratio=ior)
        svcs=[parse_manifest(m,io_ratio=ior) for m in llm]
        scored=score_topsis(svcs,p)
        tm={r.service.service_id:(r.total_score,r.rank) for r in scored}
        ap=scored[0].service; rp=rng.choice(svcs); ep=max(svcs,key=lambda s:s.cost_per_unit)
        print(f"\n  Rd {rd}/{rounds} pref={pn} io={ior}({ion})")
        print(f"    ASM={ap.display_name} Rand={rp.display_name} Exp={ep.display_name}")
        for pi in prompts:
            for g,svc in [("A_ASM",ap),("B_Random",rp),("C_Expensive",ep)]:
                cn+=1; ts,tr=tm.get(svc.service_id,(0.0,0))
                if skip:
                    lat=svc.latency_seconds+rng.gauss(0,0.2); resp=f"[SIM]{pi['id']}"
                    q=max(0,min(1,svc.quality_score+rng.gauss(0,0.05))); hk=rng.random()>0.2
                else:
                    print(f"\r    [{cn}/{total}] {g} {pi['id']} {svc.display_name}       ",end="",flush=True)
                    resp,lat=call_api(token,pi["prompt"]); q,hk=eval_resp(pi,resp); time.sleep(0.5)
                recs.append(Rec(rd,pi["id"],pi["cat"],g,pn,ion,ior,svc.service_id,svc.display_name,
                    svc.cost_per_unit,svc.latency_seconds,svc.quality_score,svc.uptime,
                    ts,tr,round(lat,4),len(resp),round(q,4),hk,resp[:500]))
    print(); return recs

def _m(v): return sum(v)/len(v) if v else 0.0
def _s(v):
    if len(v)<2: return 0.0
    m=_m(v); return (sum((x-m)**2 for x in v)/(len(v)-1))**0.5
def _nc(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def tt(a,b):
    try:
        from scipy import stats; r=stats.ttest_ind(a,b,equal_var=False); return float(r.statistic),float(r.pvalue)
    except ImportError:
        n1,n2=len(a),len(b)
        if n1<2 or n2<2: return 0.0,1.0
        m1,m2=_m(a),_m(b); s1,s2=_s(a),_s(b); se=((s1**2/n1)+(s2**2/n2))**0.5
        if se==0: return 0.0,1.0
        t=(m1-m2)/se; return t,2*(1-_nc(abs(t)))

def analyze(recs):
    gs={"A_ASM":[],"B_Random":[],"C_Expensive":[]}
    for r in recs: gs[r.group].append(r)
    su={}
    for g,rs in gs.items():
        su[g]={"n":len(rs),"tp_m":round(_m([r.topsis for r in rs]),4),"tp_s":round(_s([r.topsis for r in rs]),4),
            "dc_m":round(_m([r.d_cost for r in rs]),8),"dl_m":round(_m([r.d_lat for r in rs]),4),
            "dq_m":round(_m([r.d_qual for r in rs]),4),"al_m":round(_m([r.a_lat for r in rs]),4),
            "al_s":round(_s([r.a_lat for r in rs]),4),"q_m":round(_m([r.qual for r in rs]),4),
            "q_s":round(_s([r.qual for r in rs]),4),"kw":round(_m([1.0 if r.has_kw else 0.0 for r in rs]),4)}
    ts={}
    for at in ["topsis","a_lat","qual","d_cost"]:
        av=[getattr(r,at) for r in gs["A_ASM"]]; bv=[getattr(r,at) for r in gs["B_Random"]]; cv=[getattr(r,at) for r in gs["C_Expensive"]]
        tab,pab=tt(av,bv); tac,pac=tt(av,cv)
        ts[at]={"ab":{"t":round(tab,4),"p":round(pab,6),"s":pab<0.05},"ac":{"t":round(tac,4),"p":round(pac,6),"s":pac<0.05}}
    fr={}
    for g,rs in gs.items():
        f={}
        for r in rs: f[r.name]=f.get(r.name,0)+1
        fr[g]=f
    tr={}
    for g,rs in gs.items():
        ds=[abs(r.a_lat-r.d_lat)/r.d_lat for r in rs if r.d_lat>0]
        tr[g]={"dm":round(_m(ds),4),"ds":round(_s(ds),4)}
    return {"info":{"time":datetime.now().isoformat(),"calls":len(recs),"prompts":len(set(r.prompt_id for r in recs)),
        "rounds":max(r.round_id for r in recs),"filter":"ai.llm.chat"},"su":su,"ts":ts,"fr":fr,"tr":tr}

def report(a):
    i,s,t,tr=a["info"],a["su"],a["ts"],a["tr"]
    sep="-"*80
    print("\n"+"="*80)
    print("  ASM A/B Test Report v2 (Real API - LLM Chat Only)")
    print("="*80)
    print(f"  Time: {i['time']}  Calls: {i['calls']}  Prompts: {i['prompts']}  Rounds: {i['rounds']}  Filter: {i['filter']}")
    print(f"\n{sep}")
    print(f"  {'Metric':<26} {'A_ASM':>16} {'B_Random':>16} {'C_Expensive':>16}")
    print(sep)
    for lb,mk,sk in [("TOPSIS","tp_m","tp_s"),("Declared Cost","dc_m",None),("Declared Lat(s)","dl_m",None),
        ("Declared Quality","dq_m",None),("Actual Lat(s)","al_m","al_s"),("Response Quality","q_m","q_s"),("KW Hit","kw",None)]:
        vs=[]
        for g in ["A_ASM","B_Random","C_Expensive"]:
            m=s[g].get(mk,0); vs.append(f"{m:.4f}+/-{s[g].get(sk,0):.4f}" if sk else f"{m:.6f}")
        print(f"  {lb:<26} {vs[0]:>16} {vs[1]:>16} {vs[2]:>16}")
    print(sep)
    print(f"\n  Significance (Welch t-test, a=0.05):")
    for at,lb in [("topsis","TOPSIS"),("d_cost","Cost"),("a_lat","Latency"),("qual","Quality")]:
        ab,ac=t[at]["ab"],t[at]["ac"]
        print(f"  {lb:<18} AvB: t={ab['t']:+.3f} p={ab['p']:.4f}{'*' if ab['s'] else ''}  AvC: t={ac['t']:+.3f} p={ac['p']:.4f}{'*' if ac['s'] else ''}")
    print(f"\n  Declared vs Actual Latency:")
    for g in ["A_ASM","B_Random","C_Expensive"]:
        d=tr[g]; print(f"  {g:<16} delta: {d['dm']:.2%} +/- {d['ds']:.2%}")
    print(f"\n  Selection Frequency:")
    for g in ["A_ASM","B_Random","C_Expensive"]:
        f=a["fr"][g]; tot=s[g]["n"]; print(f"  {g}:")
        for nm,cn in sorted(f.items(),key=lambda x:x[1],reverse=True):
            pc=cn/tot*100; print(f"    {nm:<30} {cn:>3}x ({pc:5.1f}%) {'#'*int(pc/3)}")
    at_=s["A_ASM"]["tp_m"]; bt=s["B_Random"]["tp_m"]; ct=s["C_Expensive"]["tp_m"]
    ac_=s["A_ASM"]["dc_m"]; cc=s["C_Expensive"]["dc_m"]
    imp=((at_-bt)/bt*100) if bt>0 else 0; sav=((cc-ac_)/cc*100) if cc>0 else 0
    print(f"\n{'='*80}")
    print(f"  KEY FINDINGS:")
    print(f"  1. ASM vs Random: TOPSIS +{imp:.1f}% ({at_:.4f} vs {bt:.4f})")
    print(f"  2. ASM vs Expensive: {at_:.4f} vs {ct:.4f}, cost saving {sav:.1f}%")
    print(f"  3. Sig: p={t['topsis']['ab']['p']:.6f} {'SIGNIFICANT' if t['topsis']['ab']['s'] else 'not sig'}")
    print(f"  4. Taxonomy: ai.llm.chat only (no cross-category bias)")
    print()

def save(recs, ana, od):
    os.makedirs(od, exist_ok=True)
    cp=os.path.join(od,"real_ab_v2.csv")
    fs=["round_id","prompt_id","category","group","pref","io_name","io_ratio","sid","name",
        "d_cost","d_lat","d_qual","d_up","topsis","rank","a_lat","rlen","qual","has_kw","text"]
    with open(cp,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fs); w.writeheader()
        for r in recs: w.writerow({k:getattr(r,k) if k!="text" else r.text[:200] for k in fs})
    print(f"CSV: {cp}")
    jp=os.path.join(od,"real_ab_v2.json")
    with open(jp,"w",encoding="utf-8") as f: json.dump(ana,f,indent=2,ensure_ascii=False)
    print(f"JSON: {jp}")

def main():
    ap=argparse.ArgumentParser(description="ASM A/B Test v2")
    ap.add_argument("--token","-t",required=True); ap.add_argument("--manifests","-m",default=str(Path(__file__).resolve().parent.parent/"manifests"))
    ap.add_argument("--output","-o",default=str(Path(__file__).resolve().parent/"results"))
    ap.add_argument("--prompts","-n",type=int,default=10); ap.add_argument("--rounds","-r",type=int,default=3)
    ap.add_argument("--seed","-s",type=int,default=2024); ap.add_argument("--skip-api",action="store_true")
    args=ap.parse_args()
    ms=load_manifests(args.manifests)
    if not ms: print("No manifests"); sys.exit(1)
    print(f"Loaded {len(ms)} manifests")
    if not args.skip_api:
        print("Verifying token..."); r,l=call_api(args.token,"Say ok")
        if r.startswith("[ERR"): print(f"Failed: {r}"); sys.exit(1)
        print(f"OK ({l:.2f}s)")
    ps=TEST_PROMPTS[:min(max(args.prompts,1),len(TEST_PROMPTS))]
    print(f"\nStarting v2 test...")
    recs=run(args.token,ms,ps,args.rounds,args.seed,args.skip_api)
    if not recs: print("No results"); sys.exit(1)
    print(f"Got {len(recs)} records")
    ana=analyze(recs); save(recs,ana,args.output); report(ana)

if __name__=="__main__": main()
