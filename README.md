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
- Standardize the metric by taking its z-score, which means we are looking at standard deviations away from the mean "individual risk".
    - Each time, take the sigmoid of the z-score to "normalize" the outliers
    - Maybe "error" where take double z-score (once in individual model and again in compound model) but empirically works better...
    - maybe need a more "robust to outliers" method
- implemented EMA functionality
    - better results for MA risk which trickle to average risk
- added vizzes for price color coded by risk
    - one static and another using plotly, which launches a local web page where you can toggle the risk thresholds. 


## What needs to be done:
- 
Once that's done: 
- add social metrics
- add macro economic metrics
- add other price metrics
- add random other indicators you can source online
- make an automation to automatically send a message to phone when risk goes through thresholds, like every 0.05, or 0.1 units of risk. 
    - runs in the background once a day?, only sends a message when passes a threshold. 