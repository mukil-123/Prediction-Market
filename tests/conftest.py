from datetime import datetime,timedelta,timezone
import pytest
from pm_alpha.schema import Market,Quote,Stamp,Label,ResearchRow

@pytest.fixture
def clock():return datetime(2026,1,1,tzinfo=timezone.utc)

@pytest.fixture
def row_factory(clock):
    def make(index=0,outcome=1,p=.5,ask=.5,depth=True,cluster=None):
        t=clock+timedelta(days=index);mid=f"m{index:04d}"
        stamp=Stamp(t,t,t)
        m=Market("kalshi",mid,cluster or mid,"Synthetic binary event","Fixture rules",t+timedelta(hours=2),stamp)
        q=Quote(mid,stamp,p,ask-.02,ask,((ask,1000.0),) if depth else ())
        label=Label(mid,outcome,t+timedelta(hours=3),"synthetic-only")
        return ResearchRow(m,q,label,t,.07,"VERIFIED_SYNTHETIC_FIXTURE")
    return make
