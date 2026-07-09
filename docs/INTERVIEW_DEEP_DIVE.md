# GridWeather-Agent Interview Deep Dive

## 1. One-Minute Project Pitch

GridWeather-Agent is a weather-to-grid resilience system for transmission corridors. It integrates ERA5-Land weather, GEE DEM/Sentinel features, synthetic non-sensitive line geometry, IEEE738-like dynamic line rating priors, physics-guided weak labels, tabular risk models, PatchTST-GraphSAGE deep learning, and Agent/RAG operation support.

The project is not just a prediction model. It is an end-to-end engineering pipeline:

```text
weather/remote sensing/grid geometry -> physical priors -> risk prediction -> explanation/report -> service/RAG/infra
```

Current best practical result:

- Single-region physics-enhanced tabular model: macro-F1 0.886.
- TensorFlow PatchTST-GraphSAGE: macro-F1 0.548 on single-region temporal-graph modeling.
- Real two-region leave-one-region-out benchmark: macro-F1 0.138-0.160, revealing cross-region domain shift.

The strongest story is: tree-based physical baselines are currently stronger, while the deep temporal-graph path exposes the next research direction for long-term, multi-region, real-label grid risk modeling.

## 2. How To Explain The Algorithm Stack

### 2.1 Main Production Baseline

Main model:

- RandomForestClassifier for `risk_level`.
- RandomForestRegressor for `risk_score`.
- Time-based split.
- Ablation over weather, DEM, Sentinel, line geometry, DLR, IEEE738, physics prior.

Why this is reasonable:

- Current labels are physics-guided weak labels.
- The label logic is threshold-heavy.
- Tree ensembles are strong for tabular nonlinear threshold interactions.
- It gives a strong, explainable baseline before deep learning.

### 2.2 Physical Algorithms

Physical priors:

- Temperature/humidity/precipitation/wind risk logic.
- DLR proxy.
- IEEE738-like heat-balance features:
  - air density
  - solar gain
  - convective cooling
  - radiative cooling
  - ampacity
  - ampacity margin
- Line geometry:
  - line heading
  - wind-line angle
  - crosswind factor

How to defend:

The project does not ask a black-box model to infer grid physics from scratch. It injects domain priors so that the model connects weather conditions with conductor thermal headroom and line exposure.

### 2.3 Deep Learning Path

Deep model:

```text
PatchTST weather encoder + IEEE738/DLR node priors + GraphSAGE topology propagation
```

Inputs:

- `x_seq`: previous 24h weather sequence for every tower.
- `x_node`: DEM/Sentinel/line/DLR/IEEE738 node features.
- `edge_index`: adjacent tower graph along each line.

Outputs:

- Tower-level risk classification.

How to defend:

PatchTST captures temporal weather evolution. GraphSAGE captures spatial dependency and risk propagation along line topology. IEEE738 features inject physical constraints so the deep model is not purely data-driven.

### 2.4 Agent/RAG and Infra

Agent/RAG:

- BM25 retrieval.
- TF-IDF vector similarity.
- Hybrid search.
- Simple reranker.
- Chunking grid evaluation.
- Evidence packet.
- Budgeted memory.

Infra:

- FastAPI.
- Docker.
- Redis/PostGIS design.
- TTL-LRU cache.
- Token bucket limit.
- Circuit breaker.
- SingleFlight.
- Load testing.

How to defend:

The Agent is not a chat wrapper. It retrieves operation guidelines, calls deterministic tools, packages evidence, and generates risk action suggestions.

## 3. Why Deep Learning Does Not Currently Beat Random Forest

This is one of the most likely questions.

Answer:

The result is expected. The current dataset is still small for a temporal-graph model, and the target is a physics-guided weak label rather than real outage/icing/SCADA labels. Tree models naturally fit threshold-like tabular rules such as low temperature, high humidity, precipitation, DLR margin, and crosswind exposure. Also, we already engineered strong features such as IEEE738 ampacity margin and terrain indices, which reduces the need for deep representation learning.

What the deep model contributes:

- It proves that the project can model temporal sequences and line topology.
- It provides a research path for larger multi-region and multi-year datasets.
- It reveals cross-region domain shift.

What would make deep learning stronger:

- More months/years.
- More regions and more line topologies.
- Real failure/icing/SCADA labels.
- Self-supervised pretraining on weather sequences.
- Multi-task training with risk level, risk score, and DLR margin.
- Domain adaptation between climate regions.

Safe interview sentence:

```text
I do not claim deep learning is always better. In the current weak-label small-data setting, the physics-enhanced tree model is the strongest production baseline. PatchTST-GraphSAGE is implemented as the research model for time-series and topology learning, and its cross-region results reveal the domain-shift problem that future real-label training should address.
```

## 4. Technical Interview Questions By Role

## 4.1 Power Grid / Energy AI Interviewer

### Q1. What is the actual grid problem?

Answer:

The problem is not general weather forecasting. Grid operation cares about tower-level risk and line-level capacity margin. A weather forecast may say a region is cold and wet, but operation decisions need to know which line segment has icing risk, which towers are exposed, and whether the conductor still has thermal headroom.

### Q2. What does IEEE738 contribute?

Answer:

IEEE738 describes conductor thermal balance. In this project I use IEEE738-like features as physical priors: air density, solar gain, convective cooling, radiative cooling, ampacity, and ampacity margin. These features connect weather with conductor operating headroom.

### Q3. Is your DLR certified for operation?

Answer:

No. It is a study-level physical prior. A certified DLR system would need conductor type, diameter, resistance-temperature curve, emissivity, absorptivity, line current, conductor temperature, validated weather sensors, and operational calibration.

### Q4. Why use synthetic lines?

Answer:

Real transmission asset coordinates are sensitive. Synthetic lines let the project be public while preserving the same modeling structure. If a utility provides real line assets, the pipeline can replace `towers.csv` without changing the feature/model architecture.

### Q5. How would you integrate SCADA?

Answer:

SCADA current/load becomes an additional dynamic feature and can also be used to calculate real ampacity utilization. Real alarms/outages/icing thickness become supervised labels. The model then changes from weak-label risk prediction to supervised event or severity forecasting.

### Q6. What are the most important missing data?

Answer:

Real conductor metadata, SCADA load/current, observed conductor temperature, tower altitude validated from survey data, icing thickness, fault/outage records, and maintenance actions.

## 4.2 AI Lab / Research Interviewer

### Q1. What is the scientific problem?

Answer:

The scientific problem is cross-scale coupling. Weather products are grid-scale, while power-line risk is tower-scale and depends on terrain, land cover, line direction, conductor thermal physics, and temporal evolution. The model must bridge meteorology, remote sensing, graph topology, and power-system physical priors.

### Q2. Why PatchTST?

Answer:

PatchTST is suitable for multivariate time-series modeling. It patches the time axis, reduces sequence length, and lets attention model temporal dependencies. In this project it encodes each tower's previous weather sequence.

### Q3. Why GraphSAGE?

Answer:

Transmission lines naturally form graphs. Adjacent towers share local terrain and weather exposure, and risk can be spatially correlated along a line. GraphSAGE aggregates neighbor representations and can generalize to new graph nodes better than a fixed adjacency-only model.

### Q4. What is the difference between graph smoothing and GraphSAGE?

Answer:

Graph smoothing is a deterministic post-processing baseline that averages neighbor scores. GraphSAGE is a learnable message-passing model that combines node features, temporal encodings, and neighbor embeddings.

### Q5. Why is cross-region generalization hard?

Answer:

Different regions have different climate regimes, terrain, humidity, wind exposure, and baseline risk distributions. A model trained on central hills may not transfer to southwest mountains because the same temperature/humidity pattern can have different risk implications under different terrain and line exposure.

### Q6. How would you improve cross-region transfer?

Answer:

Use more regions, domain-adversarial training, region embeddings, climate-zone conditioning, meta-learning, self-supervised pretraining, and calibration on a small amount of target-region labels.

## 4.3 Big-Tech Algorithm Interviewer

### Q1. What is your baseline discipline?

Answer:

I start with a strong tabular baseline, then run systematic ablation. I do not add deep learning until I can define what it should improve: temporal dynamics and topology propagation.

### Q2. Why macro-F1?

Answer:

Risk levels are imbalanced. Accuracy can be dominated by low-risk samples. Macro-F1 gives equal weight to each class and is more appropriate when high-risk classes matter.

### Q3. What is the risk of weak labels?

Answer:

Weak labels can encode the assumptions used to generate them. A model may learn the rule generator rather than real-world failure behavior. That is why real fault/icing labels are needed for final validation.

### Q4. How do you avoid time leakage?

Answer:

The training/evaluation split is time-based. For sequence models, windows are built only from previous time steps. For cross-region evaluation, the held-out region is completely excluded from training.

### Q5. What does permutation importance tell you?

Answer:

It measures how much performance drops when a feature is randomly permuted. It is model-agnostic and helps identify which weather, terrain, line, or DLR features the model relies on.

### Q6. What would you do if high-risk recall is low?

Answer:

Use class weights, focal loss, threshold moving, oversampling, event-centric windows, two-stage detection, and additional real high-risk labels.

## 4.4 Agent / RAG Interviewer

### Q1. What does the Agent do?

Answer:

The Agent does not directly predict risk. It retrieves operation guidelines, calls risk-model outputs, collects evidence, and generates recommendations with traceable basis.

### Q2. Why hybrid retrieval?

Answer:

BM25 is strong for exact operational terms. Vector similarity is better for semantic paraphrases. Hybrid retrieval is more robust than either alone.

### Q3. How do you choose chunk size?

Answer:

Operational procedures should preserve paragraph/section boundaries. Logs may use fixed windows. Tables should be chunked by row/entity. The project includes chunking evaluation with recall@5 and MRR.

### Q4. How do you avoid context overflow?

Answer:

Keep stable facts in summary memory, retain only recent turns verbatim, retrieve evidence on demand, and avoid placing raw full tables in the prompt.

### Q5. How do you prevent hallucination?

Answer:

The LLM should not invent risk values. Risk values come from deterministic model outputs and physical features. The LLM only formats explanations and action recommendations from evidence packets.

## 4.5 AI Infra / Engineering Interviewer

### Q1. How would you service this model?

Answer:

Use FastAPI for prediction endpoints, Redis for cache, PostGIS for tower/line geometry, object storage for weather/features, Docker for deployment, and scheduled jobs for ERA5/GEE refresh.

### Q2. What is cached?

Answer:

Static tower features, latest weather windows, risk predictions by `(region_id, line_id, tower_id, model_version, time_window)`, and RAG retrieval results by query/document version.

### Q3. How do you prevent cache stampede?

Answer:

Use SingleFlight so concurrent requests for the same key share one downstream computation. Also add TTL jitter and stale-while-revalidate for non-critical reports.

### Q4. How do you limit traffic?

Answer:

Use token bucket rate limiting. Important line-risk queries get higher priority. Low-priority report generation can be queued or degraded.

### Q5. What happens if CDS/GEE fails?

Answer:

Use the last successful data snapshot, mark data timestamp and confidence, retry with backoff, and fall back to a rule model or cached predictions.

### Q6. How do you monitor it?

Answer:

Monitor data freshness, download success rate, input distribution drift, prediction latency p50/p95/p99, high-risk count drift, cache hit rate, rejected requests, and model error if labels arrive later.

## 5. Hand-Written Coding Topics

### 5.1 LRU Cache

Expected topic:

- Hash map + doubly linked list or OrderedDict.
- `get` and `set` average O(1).
- Add TTL expiration.

Project file:

- `src/gridweather/infra/cache.py`

### 5.2 Token Bucket

Expected topic:

- Capacity controls burst.
- Refill rate controls long-term throughput.
- Reject or delay when tokens are insufficient.

Project file:

- `src/gridweather/infra/rate_limit.py`

### 5.3 Circuit Breaker

Expected topic:

- Closed, open, half-open states.
- Failure threshold.
- Recovery timeout.

Project file:

- `src/gridweather/infra/circuit_breaker.py`

### 5.4 SingleFlight

Expected topic:

- Multiple requests for same key should wait for one computation.
- Prevents cache breakdown.

Project file:

- `src/gridweather/infra/singleflight.py`

### 5.5 Graph Construction

Expected topic:

- Sort towers by line and tower order.
- Add bidirectional edges between adjacent towers.
- Return `edge_index` for GNN.

Project file:

- `src/gridweather/models/temporal_graph.py`

### 5.6 Time Window Construction

Expected topic:

- For each tower, sort by time.
- Use previous `window` steps as input.
- Target is current/future risk.
- Avoid using future information.

Project file:

- `src/gridweather/models/temporal_graph.py`

## 6. Resume Bullets By Target Role

### 6.1 Power Grid / Energy AI

```text
Built a weather-to-grid risk system for transmission corridors by integrating ERA5-Land weather, GEE DEM/Sentinel features, line geometry, and IEEE738-like dynamic line rating priors to predict tower-level icing/weather risk and generate operation recommendations.
```

```text
Constructed a real two-region ERA5-Land benchmark and evaluated leave-one-region-out transfer, revealing strong climate/terrain domain shift in grid weather-risk modeling.
```

### 6.2 AI Lab / Algorithm

```text
Implemented a PatchTST-GraphSAGE deep-learning model: PatchTST encodes tower-level weather sequences, GraphSAGE propagates risk representations along line topology, and IEEE738-like physical priors condition node features.
```

```text
Compared physics-enhanced tree baselines against temporal-graph deep learning; results show tree models dominate under weak-label small-data settings, while deep models expose the need for multi-region real-label training.
```

### 6.3 Agent / RAG

```text
Built an operation-support Agent pipeline with BM25 + TF-IDF hybrid retrieval, reranking, chunking evaluation, evidence packaging, budgeted memory, and risk-action report generation.
```

### 6.4 AI Infra / MLOps

```text
Added service/infra components including FastAPI, Docker, Redis/PostGIS design, TTL-LRU cache, token-bucket rate limit, circuit breaker, SingleFlight cache-stampede protection, scheduled refresh, and local load testing.
```

## 7. Best Final Interview Narrative

Use this sequence:

1. The business problem is tower-level grid weather risk, not general weather forecasting.
2. I built a real ERA5/GEE data pipeline and non-sensitive synthetic line topology.
3. I used physics-guided weak labels because public real outage labels are unavailable.
4. I injected DLR/IEEE738 priors so the model reflects power-system physics.
5. I validated features through systematic ablation; IEEE738 features produced the best tabular macro-F1.
6. I implemented PatchTST-GraphSAGE to explore time-series and topology learning.
7. The deep model currently underperforms tree baselines because the dataset is small and weak-label based.
8. I expanded to a real two-region benchmark and showed leave-one-region-out transfer is hard.
9. I added Agent/RAG and infra modules to demonstrate landing awareness.
10. The next step is real SCADA/fault/icing labels, more regions, longer time series, and domain adaptation.

## 8. Questions You Should Ask The Interviewer

For power grid roles:

- Does your team have access to real conductor temperature, SCADA, or outage/icing labels?
- Are DLR/RTTR projects currently research-stage or operationally deployed?
- What is the most painful weather risk scenario: icing, wind, wildfire, heat, or typhoon?

For AI Lab roles:

- Is the team more focused on foundation weather models, downstream impact modeling, or decision support?
- Are there internal graph/time-series benchmarks for infrastructure risk?

For Agent/Infra roles:

- What are the latency and reliability requirements for operation-assist systems?
- How are RAG outputs audited when used in operational workflows?

These questions show that you understand both model development and deployment constraints.
