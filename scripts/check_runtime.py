"""Offline read-only integrity/replay check; no protected performance or network."""
import json
from pathlib import Path
from pm_alpha.desktop import ReadOnlyStore, preflight, replay
from pm_alpha.forward_integrity import verify_forward
from pm_alpha.shadow_replay import replay_shadow

root=Path(__file__).resolve().parents[1]
result={'preflight':preflight(root)}
snapshot=ReadOnlyStore(root/'data/forward.sqlite')
class Borrowed:
    def __getattr__(self,key):return getattr(snapshot,key)
    def close(self):pass
try:
    factory=lambda path:Borrowed()
    result['forward_integrity']=verify_forward(root,factory)
    result['raw_replay']=replay(root,factory)
finally:snapshot.close()
if (root/'data/shadow.sqlite').is_file():result['shadow_replay']=replay_shadow(root)
result['valid']=result['forward_integrity']['valid'] and result['raw_replay']['valid'] and result.get('shadow_replay',{'valid':True})['valid']
result.update(live_trading=False,real_orders=0)
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['valid'] else 1)
