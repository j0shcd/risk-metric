# risk-metric
Implement a risk metric for financial markets, mostly focused on cryptocurrencies. First iteration on bitcoin. 

# Where I'm at:

## What is done:
- data retrieval from binance if missing days
- full historic data from Jan 1st, 2012
- simple price risk using SMA
- overvaluation relative to log reg: another risk metric
- "average" risk metric
- Standardize the metric by taking its z-score, which means we are looking at standard deviations away from the mean "individual risk".
    - Each time, take the sigmoid of the z-score to "normalize" the outliers
    - Maybe "error" where take double z-score (once in individual model and again in compound model) but empirically works better...
- implemented EMA functionality
    - better results for MA risk which trickle to average risk
- added vizzes for price color coded by risk
    - one static and another using plotly, which launches a local web page where you can toggle the risk thresholds. 
- Added scheduler file which you can run with the following commands:
    - manually launch the script: "nohup python3 scheduled_run.py > scheduled_run.log 2>&1 &"


## What needs to be done:
- Change "separate risk" visualizations to have more clear grid (ie only horizontal lines at every 0.1 risk)
- Improve z-score standardization:
    - maybe need a more "robust to outliers" method
    - need to check if the data is normal...
        - or use confidence intervals (w/ bootstrap resampling)

## Ideas for new features:
- make an automation to automatically send a message to phone when risk goes through thresholds, like every 0.05, or 0.1 units of risk. 
    - runs in the background once a day?, only sends a message when passes a threshold. 
- add some sort of **"confidence level"** which could be something like "how normal is the distribution" or how much data do I have

## add social metrics
    - youtube views/subs
    - followers to certain accounts (twitter)
    - google trends statistics
    - wikipedia page views (bad)
    - fear and greed index, something like 30-80D EMA (BC used 90D EMA once, was too laggy)
    - sentiment analysis of twitter/youtube comments
  
## add macro economic metrics
    - find relevant "recession risk" indicators
    - sahm rule recession indicator?
    - yield curve?
    - unemployment rate?
    - net liquidity?
    - The VIX? (volatility index, see BC vid)
    - DXY? (see various BC videos on it)

## add other price metrics
    - running ROI (eg 1year)
    - advance/decline index
    - extension from 20W sma (see BC video on it, or extension from bull market support band, replicate "short term bubble risk")
    - RSI (consider different timeframes and different moving averages ("monthly RSI = 1 month MA? idk))
    - bollinger bands (2std away from 200W MA), maybe use a shorter moving average to make something better for bitcoin, probably how cowen corridor was made
    - seasonality?

## add random other indicators you can source online
    - best: volume levels at different price levels to predict resistance levels (very linked to risk (=bitcoin supply bought by long-term holders at given price))
    - Puell multiple (similar to what I have now)
    - bitcoin transaction fees?
    - ethereum transaction fees?
    - minercap to thermocap ratio
    - stablecoin supply ratio?
    - bitcoin supply in profit (good)
    - (some way to capture the "dry powder" would be useful)
    - stablecoin marketcap?
    - percentage of supply in profit/loss
    - terminal price, balance price, realized price (== distance from)
    - pi cycle top indicator

## Once have a few features:
- transform each above indicator into feature vectors, standardizing each of them (z-score) that can be used for some ML models like (boosted) Random Forest, regressions etc, to determine which have the most predictive power
- do some feature analysis to remove as many as possible (avoid overfitting...)
- add regularization
- use robust scaling from sklearn instead of z-score maybe, or combination of both
- optimise for True negative rate? (conservative model?) precision?, 
- Evaluate training and test error to see if overfitting
- unsupervised learning to cluster phases of the market (k-medoids++?)
- PCA/TSNE to combine indicators effectively
- target function? could be something like trying to predict the z-score of the median of the next X months of data (or the median outright, or a combination of both)
