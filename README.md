# risk-metric
Implement a risk metric for financial markets, mostly focused on cryptocurrencies. First iteration on bitcoin. 

# Where I'm at:

## What is done:
- data retrieval from binance if missing days
- full historic data from Jan 1st, 2012
- simple price risk using SMA
- logarithmic/hyperbolic regression (not fully convinced....)
- overvaluation relative to log reg: another risk metric
- "average" risk metric

## What needs to be done:
- somehow account for diminishing returns (sounds very hard...)
    - right now tried: tanh and log coefficients but not successful in current implementation. 

Once that's done: 
- add social metrics
- add macro economic metrics
- add other price metrics
- add random other indicators you can source online