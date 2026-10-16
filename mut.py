import subprocess, sys, shutil
P='src/containment.py'; orig=open('../c.bak').read()
M=[
("divide by larger","return len(a & b) / min(len(a), len(b))","return len(a & b) / max(len(a), len(b))",1),
("core = union","if 2 * n > len(group)}","if n >= 1}",1),
("core = intersection","if 2 * n > len(group)}","if n == len(group)}",1),
("first-pass core = union","if 2 * n > len(members[k])}","if n >= 1}",1),
("skip prune","    out = []\n    for group in groups:","    return groups\n    out = []\n    for group in groups:",1),
("skip merge pass","    groups = sorted((sorted(g) for g in groups), key=lambda g: g[0])\n    for _ in range(rounds):","    return groups\n    for _ in range(rounds):",1),
("skip agglomerate","groups = prune(\n            agglomerate(groups, texts, threshold, max_length_ratio)","groups = prune(\n            groups",1),
("skip ungrouped join","            if best is not None:\n                groups[best] = sorted(groups[best] + [letter_id])","            pass",1),
("skip regroup","        groups += first_pass(left","        groups += [] and first_pass(left",1),
("first-pass threshold 0.2","                if fits(tokens, core(k), threshold, max_length_ratio):","                if fits(tokens, core(k), 0.2, max_length_ratio):",1),
("no sort","eligible = sorted(i for i in texts if","eligible = list(i for i in letters['letter_id'] if",1),
("name = earliest","name = max(group, key=lambda m: (len(texts[m] & core), [-ord(c) for c in m]))","name = group[0]",1),
("prune not leave-one-out","if fits(texts[m], core_without(group, m, texts), threshold, max_length_ratio)","if fits(texts[m], core_of(group, texts), threshold, max_length_ratio)",1),
("no length guard","return small > 0 and large <= max_length_ratio * small and","return small > 0 and",1),
]
for name,a,b,_ in M:
    if a not in orig: print("!! missing:",name); continue
    open(P,'w').write(orig.replace(a,b))
    r=subprocess.run(["uv","run","pytest","-q","-x","--no-header","-p","no:cacheprovider","tests/test_containment.py"],capture_output=True,text=True,timeout=600)
    line=[l for l in r.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l.lower()]
    print(f"{name:28s} {line[-1] if line else r.stdout[-300:]}")
open(P,'w').write(orig)
