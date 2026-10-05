import numpy as np
import pytest
from src.metrics.covar import _quantile_regression_lp,_quantile_regression


def loss(x,y,a,b,q):
 r=y-a-b*x;return np.where(r>=0,q*r,(q-1)*r).sum()


def test_lp_exact_line_and_scale_equivariance():
 x=np.linspace(-1,1,100);y=.04+.7*x
 a,b=_quantile_regression_lp(x,y,.05)
 assert a==pytest.approx(.04,abs=1e-9) and b==pytest.approx(.7,abs=1e-9)
 aa,bb=_quantile_regression_lp(x*100,y*10,.05)
 assert aa==pytest.approx(a*10) and bb==pytest.approx(b/10)


def test_lp_pinball_objective_matches_or_improves_irls():
 rng=np.random.default_rng(19);x=rng.normal(0,.02,252);y=.6*x+rng.normal(0,.01,252)
 a,b=_quantile_regression_lp(x,y,.05)
 aa,bb=_quantile_regression(x,y,.05)
 assert np.isfinite([a,b,aa,bb]).all()
 assert loss(x,y,a,b,.05)<=loss(x,y,aa,bb,.05)+1e-9


def test_failed_irls_uses_same_loss_lp(monkeypatch):
 import statsmodels.regression.quantile_regression as qr
 def fail(*args,**kw):raise RuntimeError('forced IRLS failure')
 monkeypatch.setattr(qr.QuantReg,'fit',fail)
 x=np.linspace(-.03,.03,100);y=.5*x-.002
 a,b=_quantile_regression(x,y,.05)
 assert a==pytest.approx(-.002) and b==pytest.approx(.5)


def test_invalid_samples_remain_unavailable():
 x=np.arange(100,dtype=float)
 assert np.isnan(_quantile_regression_lp(x,x,0)[0])
 assert np.isnan(_quantile_regression_lp(x*0,x,.05)[0])
 assert np.isnan(_quantile_regression_lp(x[:10],x[:10],.05)[0])


def test_constant_response_is_exact_quantile():
 a,b=_quantile_regression_lp(np.arange(100,dtype=float),np.full(100,-.03),.05)
 assert a==pytest.approx(-.03) and b==pytest.approx(0.)
