import urllib.error
import pytest
from pm_alpha.data.http import PublicHTTP,AccessBlocked
from pm_alpha.data.polymarket import Polymarket
from pm_alpha.storage import Store
from pm_alpha.schema import DataInvalid

def test_no_retry_or_circumvention_on_403(tmp_path,monkeypatch):
    calls=[]
    def blocked(*args,**kwargs):
        calls.append(args)
        raise urllib.error.HTTPError("https://example.org",403,"forbidden",{},None)
    monkeypatch.setattr("urllib.request.urlopen",blocked)
    s=Store(tmp_path/"a.sqlite");client=PublicHTTP(tmp_path/"raw",s)
    with pytest.raises(AccessBlocked):client.get("https://example.org","/data")
    assert len(calls)==1 and len(s.records("blocker"))==1;s.close()

def test_history_follows_opaque_cursor_and_keeps_terminal_separate(clock):
    class HTTP:
        def __init__(self):self.calls=[]
        def get(self,base,path,params):
            self.calls.append(params)
            if not params["cursor"]:return {"data":[{"timestamp":1,"price":.5,"resolution_seconds":10800}],"pagination":{"next_cursor":"opaque"}},"a",clock
            return {"data":[{"timestamp":2,"price":1,"resolution_seconds":0}],"pagination":{"next_cursor":None}},"b",clock
    h=HTTP();rows=Polymarket(h).history("token")
    assert len(rows)==2 and h.calls[1]["cursor"]=="opaque"
    assert rows[-1][0]["resolution_seconds"]==0

def test_repeated_cursor_fails(clock):
    class HTTP:
        def get(self,*args):return {"data":[],"pagination":{"next_cursor":"same"}},"h",clock
    with pytest.raises(DataInvalid):Polymarket(HTTP()).history("token")
