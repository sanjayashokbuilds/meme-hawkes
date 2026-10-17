# Concepts, from zero

Plain-English notes for everything this project uses. Intuition first; the maths at the end of each section is just the same idea written precisely.

---

## 1. Point processes: data that is a list of times

Most data you've worked with is "a value at a time": a price every day, a temperature every hour. Trade data is different. The interesting thing is *when* each trade happens. A trade is a dot on a timeline:

```
time →   •  •      •          •••• •••  ••    •
```

A **point process** is a model for where the dots land. The questions it answers are: how often do dots arrive, and does one dot make the next one more likely?

The key quantity is the **intensity**, written λ(t) ("lambda of t"). Read it as *the expected number of events per second right now*. If λ(t) = 2, then over the next tiny slice of time dt, the chance of a trade is about 2·dt.

Intensity is to a point process what a speedometer is to a car journey: it's the rate at this instant, and it can change from moment to moment.

---

## 2. Poisson process: the "no memory" baseline

The simplest point process has a **constant** intensity: λ(t) = μ ("mu"). Events arrive at random with no memory. A trade a second ago has no effect on whether one happens now. Raindrops on a window are the classic picture.

Two useful facts:
- The number of events in a window of length T has mean μT.
- The gaps between events are independent, each following an exponential distribution with mean 1/μ.

A Poisson process can't produce *clusters*. Real trading clusters heavily, and the Hawkes process exists to model that.

---

## 3. Hawkes process: events that cause events

A Hawkes process says: every event temporarily *raises* the intensity, and the boost fades over time.

Picture a quiet group chat. Someone posts (an event). For the next few minutes, replies are much more likely, because one post triggers others. The effect wears off, and the chat goes quiet again until the next spark.

So the intensity has two parts:
- **Background rate μ**: events that happen "on their own" (news, someone randomly deciding to buy).
- **Self-excitation**: a bump added after every past event, which shrinks as that event recedes into the past.

```
λ(t)
 │        ╱╲
 │       ╱  ╲╱╲
 │  ╱╲  ╱      ╲___╱╲
 │_╱  ╲╱            ╲_____  ← falls back to μ
 └──•────•─•────────•──────→ t
```

Each dot makes the line jump up; between dots it decays back down towards μ.

**The formula:**

λ(t) = μ + Σ over past events tᵢ < t of φ(t − tᵢ)

where φ (the **kernel**) is the shape of the bump: how big it is, and how fast it fades.

---

## 4. The exponential kernel

We need a shape for the bump. The standard choice is an exponential decay:

φ(s) = α · e^(−β·s)

- **α (alpha)**: the size of the jump right after an event.
- **β (beta)**: how fast it fades. Bigger β means faster forgetting. 1/β is the typical memory length in seconds.

Why exponential? The maths becomes cheap. The total "leftover excitation" at any moment can be updated with one multiplication per event instead of re-summing over all past events. That makes fitting fast enough to run inside a web app.

The honest catch: real markets often have slower-fading, "long-memory" kernels (power laws). The exponential is a simplification we test, not a truth we assume. That's what the goodness-of-fit check in Section 8 is for.

---

## 5. The branching ratio: how much activity is self-generated

This is the headline number of the project.

Think of every background event as an "immigrant" that can have "children" (events it triggers). The children can have children of their own, and so on: a family tree.

The **branching ratio n** is the *average number of children per event*. For the exponential kernel it's the total area under the bump:

n = α / β

How to read it:
- **n = 0**: no event triggers any other. Pure Poisson.
- **n = 0.7**: each event triggers 0.7 others on average. Roughly 70% of all activity is *reactions*, not fresh decisions.
- **n ≥ 1**: each event triggers at least one more. Activity can snowball without limit, and the process is "explosive".

Filimonov & Sornette called n a measure of market **reflexivity**: the share of trading driven by trading itself, rather than by outside information. That's exactly the quantity that should rise during a hype-driven pump.

A known trap (also from Filimonov & Sornette): if the model is wrong, the estimate of n gets pushed *upwards* towards 1. That includes a kernel with the wrong shape, or a background rate that actually changes over time. So a high n can be an artefact. We need to check fit before believing it.

---

## 6. Multivariate Hawkes: who triggers whom

Now split trades into types (the model calls them "dimensions"), for example:
1. coordinated-wallet buys
2. ordinary-wallet buys
3. coordinated-wallet sells
4. ordinary-wallet sells

Each type has its own intensity, and *every type can excite every other type*. So instead of one α and one β, there is a grid. α₂₁ is "how much a coordinated buy (type 1) raises the rate of ordinary buys (type 2)".

The **branching matrix** has entries nᵢⱼ = αᵢⱼ / βᵢⱼ: the average number of type-i events directly triggered by one type-j event.

**Our core question is a single entry of this matrix:** coordinated buys → ordinary buys. If it's large, ordinary buyers are being pulled in by the coordinated wallets' activity.

The overall "explosiveness" of the system is the largest eigenvalue of the branching matrix (its spectral radius). It plays the same role as n in the one-type case.

One honesty point to keep in mind: excitation is a *statistical* link ("ordinary buys tend to follow coordinated buys"), not proof that one causes the other. A third factor, such as a viral tweet, could drive both. We'll word results accordingly.

---

## 7. Maximum likelihood: picking the parameters

We have the trade times. We want the μ, α, β that best explain them.

The **likelihood** answers: *if the true parameters were these, how probable is the exact data we saw?* Maximum likelihood estimation (MLE) searches for the parameters that make that probability as large as possible.

Link to your Chola build: MLE is what you'd get from Bayesian inference with a flat prior, if you took the peak of the posterior instead of the whole distribution.

For a point process the log-likelihood has two parts, and both are intuitive:

log L = Σᵢ log λ(tᵢ) − ∫₀ᵀ λ(t) dt

- **First term, the reward:** the model should have had a *high* intensity at the moments trades actually happened.
- **Second term, the penalty:** the model shouldn't predict lots of trades when none happened. The integral is the total number of events the model "expected" over the whole window.

A model that just sets λ huge everywhere wins the first term but gets crushed by the second. The best fit balances the two.

We maximise this numerically with `scipy.optimize`, keeping μ, α, β positive and α/β < 1.

**How we'll know our code is right (Stage 3):** simulate fake data from parameters we choose, fit the model, and check we get those parameters back. Only then do we touch real data.

---

## 8. Checking the fit: the time-rescaling theorem

A neat result: if the model is right, you can "stretch" time using the intensity. Fast in busy periods, slow in quiet ones. After stretching, the events look exactly like a plain Poisson process with rate 1.

So we compute the stretched gaps between consecutive events (the integral of λ between them). If the model is correct, these gaps should follow an exponential distribution with mean 1. We check with a **QQ plot**: sorted gaps against what an exponential predicts. A straight diagonal line means a good fit. A bend shows where the model fails, such as too many very short gaps.

---

## 9. Simulation: Ogata thinning

To validate the estimator we need to *generate* Hawkes data. **Ogata's thinning** method:

1. Look at the current intensity. Since it only decays until the next event, it's an upper bound for the near future.
2. Propose a candidate event time as if events arrived at that upper-bound rate.
3. Accept the candidate with probability (true intensity at that time) / (upper bound). Otherwise reject it.
4. If accepted, the intensity jumps. Repeat.

It's like rejection sampling, which you've used in Monte Carlo work.

---

## 10. A Solana-specific problem: tied timestamps

Solana groups transactions into **slots**, roughly 400 ms each. Several trades in the same slot share a time, and a burst of sniper buys often lands in the very first slot.

A Hawkes process assumes no two events happen at exactly the same moment. If we feed it ties naively, the fit sees "events triggering each other with zero delay". It then tends to invent huge α and β, which inflates the branching ratio.

The common fixes, which we'll choose between in Stage 3:
- **Spread ties randomly within their slot.** Simple and widely used; repeat with different random draws to check the results don't depend on the draw.
- **Use within-slot transaction order** to keep the sequence but still spread the times.
- **Merge ties into one event with a size ("mark")**, at the cost of a richer model.

---

## 11. How pump.fun works: the bonding curve

On pump.fun, anyone can launch a token in seconds. At first there is no order book and no other traders to match against. You trade directly with a smart contract, the **bonding curve**:

- The price is a fixed formula of how many tokens have already been sold.
- Every buy moves the price up the curve; every sell moves it back down.
- When enough SOL has gone in, the token **"graduates"** to a normal trading pool (PumpSwap since 2025, Raydium before that), where pricing works differently.

Why this matters for us:
- Every trade is a clear decision by one wallet, and it's all public on-chain with the wallet address.
- The earliest buyers get the cheapest price. That gives automated "sniper" wallets a strong reason to buy in the first slots, which is where coordinated groups show up.
- A pump-and-dump on the curve looks like: early wallets buy cheap, ordinary buyers pile in and push the price up, and the early wallets sell into that demand.

*To verify in Stage 2:* exact curve parameters and the graduation threshold have changed over time, so we'll read them from the data rather than hard-coding numbers from memory.
