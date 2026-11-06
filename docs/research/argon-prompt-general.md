# Argon research prompt: cross-domain architectures for structured probabilistic prediction

Paste everything below the line into Argon.

---

I am designing a prediction system and want **inspiration from AI and statistical-learning research in any
field**, so I can build something new. I am not looking for a model to copy. Focus on work from 2024–2026,
plus older ideas only if they are foundational. Cover at least 8 different fields, for example quantitative
finance, energy and power systems, epidemiology, robotics and autonomous-vehicle motion prediction,
recommender and retrieval systems, protein and molecule generation, audio and speech, insurance and
catastrophe risk, supply chain and demand forecasting, language-model decoding, tabular and time-series
foundation models, and astronomy or particle physics. Domains that look unrelated are welcome.

## The abstract problem

Given a query made of:
- a continuous 2-D position;
- a calendar date and time of day (both cyclic);
- a horizon from a few days to about 3 years ahead,

produce **N joint samples** (around 1,000) of a structured object. Then summarise each element of the
object by its mean and standard deviation.

**The object.** 4–5 continuous channels, each defined along one ordered axis with 44 positions. So it is a
small multi-channel curve of about 180 numbers.
- Neighbouring positions and the channels are strongly correlated.
- The channels obey known soft constraints (smoothness, plus fixed relationships between some channels).
- What matters downstream is the joint shape: differences between neighbouring positions drive the
  outcome. A sample with correct per-element marginals but the wrong joint structure is useless.

**Data available.**
1. About 35 years of hourly history of the object on a regular 2-D lattice. That is millions of examples,
   but only about 35 independent realisations of the slow year-to-year variability.
2. A sparse set of much more accurate direct measurements, at about 100 lattice-independent locations,
   twice a day. They differ systematically from the dense history, which is too smooth and has too little
   spread.
3. A few slow scalar "driver" indices that shift the object's distribution. They can be forecast only
   partly: one is useful for about 12–18 months, another for about 2 years. Their own forecast uncertainty
   has to flow through.
4. A slow, non-stationary trend. The future is partly outside the range of the training data.
5. For the first ~2 weeks only, external sample sets from two independent providers (50–65 samples
   each). They are sharp at short horizons, their skill decays to nothing, and their errors differ from
   each other. Their archive of past outputs is short (a few years).

**Current baseline.**
- Draw real historical objects from similar calendar dates and times of day.
- Blend the four nearest lattice points.
- Shift each draw linearly by the trend and by the driver-index differences, keeping each term only if
  it passes a significance test and a walk-forward backtest.
- Mix in the external samples at short horizons.
- Widen the spread to match the accurate measurements.

**Requirements.**
- Calibrated coverage (68/95/99.7 %) per channel, position and horizon band.
- Better joint realism than the baseline, measured by CRPS, energy score and variogram score.
- Faithful tails (99.9th percentile of the neighbour differences).
- Never worse than resampled history at long horizons.
- Inference under 1 ms for 1,000 samples.
- Interpretable.
- Training on at most one GPU.
- Leakage-free walk-forward evaluation.

## What I want back

1. **Mechanism catalogue (30+ entries).** For each idea from any field:
   - the paper or system, field and year;
   - the core mechanism in 2–3 sentences;
   - *which of my sub-problems it addresses*, using these labels: joint/coherent sampling,
     retrieval/analog conditioning, combining sources of different reliability, calibration or coverage
     guarantees, small-data or few-independent-samples learning, distribution shift or extrapolation
     beyond training range, tail modelling, horizon-dependent skill decay, propagating input
     uncertainty, fast amortised sampling, learning from sparse accurate measurements plus dense biased
     data;
   - evidence quality (peer-reviewed, preprint, benchmark size);
   - data and compute needed.
2. **Transferable principles.** Abstract each mechanism into a principle independent of its domain, e.g.
   "retrieve, then learn a correction", or "train on a synthetic prior, then condition in-context".
   Group the duplicates.
3. **5 novel hybrid designs** that recombine principles from *different* fields into something that does
   not exist yet for my problem. For each:
   - a diagram in words;
   - which baseline weakness it fixes;
   - the failure modes;
   - the smallest experiment that would falsify it;
   - an estimate of the effort.
4. **Ranking** by expected gain per unit of effort. Be blunt about which ideas are fashionable but unlikely
   to beat resampled history with only 35 independent years.
5. **Sources.** Links for every claim. Mark anything you could not verify.

Avoid generic advice such as "use a transformer". I want concrete mechanisms, and evidence on whether they
worked.
