# Where this project sits

Checked against the papers themselves on 17 Oct 2026. Anything not confirmed is marked.

## Hawkes processes in markets

**Filimonov & Sornette (2012), "Quantifying reflexivity in financial markets: towards a prediction of flash crashes", *Physical Review E*.**
Fits Hawkes processes to high-frequency futures data and reads the branching ratio as the share of activity that is self-generated ("reflexivity"). Argues it rose over the 2000s as algorithmic trading grew. This is where our use of the branching ratio as a reflexivity gauge comes from.

**Filimonov & Sornette (2015), "Apparent criticality and calibration issues in the Hawkes self-excited point process model", *Quantitative Finance* 15(8).** [arXiv:1308.6756](https://arxiv.org/abs/1308.6756)
The warning label. Shows that kernel misspecification, a changing background rate, and data problems push the estimated branching ratio towards 1. Takeaway for us: validate on simulated data, check goodness of fit, and don't over-read high branching ratios.

**Hardiman, Bercot & Bouchaud (2013), "Critical reflexivity in financial markets: a Hawkes process analysis".**
Uses long-memory kernels and finds markets close to the critical point n ≈ 1. A counterpoint on kernel choice; supports reporting our exponential-kernel results with care.

**Fabre & Muni Toke (2025), "High-Frequency Market Manipulation Detection with a Markov-modulated Hawkes process".** [arXiv:2502.04027](https://arxiv.org/abs/2502.04027)
A Hawkes-style intensity whose parameters switch between hidden regimes ("normal" vs "suspicious"), fitted by expectation-maximisation on crypto trades from a centralised exchange. It detects anomalous bursts. The gap it leaves: a centralised exchange doesn't reveal *who* traded, so it can't separate coordinated from ordinary traders.

## pump.fun and memecoin manipulation

**Szwajcok, Tsuchiya, Liu, Soska, Payer & Christin (2026), "Meme Coin Factories: Uncovering Large-Scale Manipulations on pump.fun", CCS '26.** [arXiv:2609.10246](https://arxiv.org/abs/2609.10246)
Large-scale measurement study (about 15 million coins over two years). Catalogues five manipulation strategies, including wash trading, hidden creators and coordinated selling, and documents "manipulation-as-a-service" tooling. Descriptive and forensic; it doesn't model how manipulators' trades trigger other traders.

**Kamat (2026), "Coordinated Sniper Cohorts on Pump.fun".** [arXiv:2607.02795](https://arxiv.org/abs/2607.02795)
Detects groups of wallets that repeatedly appear together among a launch's first ten buyers (a co-occurrence graph), then estimates their effect on first-hour buying.
**Important:** an October 2026 correction notice in the paper withdraws all its numerical results, including the cohort count and the buyer-flow estimate, because the underlying buyer records were faulty. Its cohort list, RED-COHORT-2026-v1 (Zenodo, CC-BY-4.0), was built from that data.
**Our use:** we cite the co-occurrence *idea* as related work, but don't use the published list as ground truth or quote the withdrawn figures.

**Mongardini & Mei (2025/26), "A Midsummer Meme's Dream: Investigating Market Manipulations in the Meme Coin Ecosystem".** [arXiv:2507.01963](https://arxiv.org/abs/2507.01963)
Studies about 35,000 memecoins across four chains. Labels pump-and-dumps with rules on hourly price and volume data: a peak with RSI above 80; a rise of more than 50% within 24 hours, with a volume surge of more than 500%; then a fall of more than 30% with volume dropping below half the pump level. **Our use:** a candidate source for the "pump-and-dump" labels and the rule-based baseline in Stage 5. The thresholds were designed for hourly data, so applying them to the much faster bonding-curve phase is a choice we must document.

## Our contribution (and what we don't claim)

| | Existing work | This project |
|---|---|---|
| Hawkes branching ratio as reflexivity | Filimonov & Sornette | Applied to pump.fun tokens, tracked through each token's life |
| Hawkes for manipulation detection | Fabre & Muni Toke (anonymous centralised-exchange trades) | Uses wallet identities to split traders into separate dimensions |
| Coordinated wallets on pump.fun | Kamat (co-occurrence cohorts; figures withdrawn); Szwajcok et al. (taxonomy) | Measures how much coordinated activity *excites* ordinary buying, as an entry of the branching matrix |
| Pump-and-dump detection | Mongardini & Mei (rules on hourly price/volume) | Tests whether excitation measures give earlier warning than those rules |

We don't claim to be first to apply Hawkes processes to crypto or to manipulation. The specific angle is the cross-excitation between wallet groups that on-chain data makes visible.

*Prior-work check (17 Oct 2026):* a search turned up no paper fitting multivariate Hawkes models split by wallet group on pump.fun. The nearest multivariate-Hawkes crypto work found was on stablecoin depegging ([arXiv:2205.06338](https://arxiv.org/abs/2205.06338)). A search isn't proof, so the write-up says "to my knowledge".
