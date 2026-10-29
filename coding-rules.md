# Coding Manual

## Fields

| Column | Values | Card. | Scope | Rule |
|---|---|---|---|---|
| `no` | integer | 1 | work | R18 |
| `pillar` | P / M / V | 1 | work | R3 |
| `name`, `title`, `year_first_public` | — | 1 | work | R18 |
| `pattern` | SN / NS / HL | 1 | primary unit | R4 |
| `formalism` | ONT / KG / LOG / HYB / OTH | 1 | primary unit | R7 |
| `design_time_source` | ONT / KG / empty | 1 | primary unit | R7 |
| `language` | free text, optional | multi | primary unit | R7 |
| `binding` | D / G / E / H | multi | primary unit | R8 |
| `provenance` | A / M / S / U | multi | primary unit | R9 |
| `synthesis_role` | program / model / content / search / none | 1 | primary unit | R10 |
| `assurance` | E / P/K / P/W / D/K / D/K-st / D/W | 1 | primary unit | R11, R12 |
| `functions` | P / Mw / Ml / Mk / V / X | multi | all units | R13 |
| `shared_models` | groups, e.g. `P=Mw;Ml=V` | — | all units | R13 |
| `evaluation` | art-run / art-iso / out | 1 | work | R14 |
| `planning_loop` | single / closed / na | 1 | work | R15 |
| `fallback` | yes / unk / empty | 1 | primary unit | R5 |
| `human_override` | yes / empty | 1 | primary unit | R5 |
| `env_validation` | yes / empty | 1 | primary unit | R11 |
| `repair_loop` | yes / empty | 1 | work | R4 |
| `basis` | F / A | 1 | work | R18 |

- **Multi-valued fields.** Separate values with `+`.
- **`shared_models`.** `=` joins functions within a group; `;` separates groups.

---

## R1 Unit

- A unit is a triple (c, Y, Σ):
  - c is the agent function: planning Π, memory write μ, retrieval ρ, or gating Γ;
  - Y is the set of candidates the unit submits: outputs of c, or artefacts that c uses;
  - Σ = (L, M, R) is the language, the model (specification or store), and the decision procedure used to generate or check Y.
- Code each unit separately.
- Components without machine-checkable semantics are not units.

## R2 Primary unit

- Each work has exactly one primary unit. Fields with scope "primary unit" describe it. Other units appear only in `functions`, `shared_models` and `repair_loop`.
- **Synthesize-then-apply systems:**
  - The paper evaluates behavior produced under the artefact → choose the applying unit.
  - The paper evaluates only the artefact → choose the synthesis unit.
  - The applying unit must belong to the proposed system. If the artefact is used only inside a benchmark's evaluation protocol, choose the synthesis unit and treat the downstream metric as a task outcome.
  - An evaluation that only counts the manual edits a generated model needs counts as evaluating only the artefact.
  - Synthesized gate rules evaluated by their verdicts on logged trajectories → choose the gate unit.
- **Several units constrain the LLM's output and the paper evaluates the task outcome.** Compare them on these criteria in order; stop at the first one that separates them:
  1. largest ablation gain;
  2. explicitly claimed as the paper's contribution;
  3. handles most submitted objects in the hardest reported setting.
- **Memory works:**
  - Core claim is memory structure, write policy, or graph construction → choose μ, even if the evaluation is downstream QA.
  - Core claim is retrieval or QA over the graph, and writing is kept minimal → choose ρ.
- **Otherwise** → the unit that the main evaluation targets.

## R3 Pillar

- **By the primary unit's function:** Π → P; μ or ρ → M; Γ → V.
- **Knowledge graphs:**
  - Submitted actions change the state the graph represents → Π, P.
  - The graph is only read to answer queries → ρ with function Mk, M. This applies even to multi-hop navigation.

## R4 Pattern

- **Independent program.** A program whose semantics is fixed and cannot be steered by the LLM. Examples: a planner, solver, model checker, reasoner, automaton, or an interpreter that applies a fixed check to each candidate.
- **φ.** The property the unit claims for what it submits. Syntactic well-formedness or executability counts as φ only when it is the only property claimed.

| Code | Criterion |
|---|---|
| SN | An independent program generates, constrains or filters **every** submitted object so that it satisfies φ; its verdict does not return to the LLM |
| NS | No independent program decides φ before submission. This includes: checks of a weaker property only (well-formedness, runnability, solvability relative to the generated model); symbolic feedback at training time only; output produced by executing LLM-written code (R6) |
| HL | (1) An independent program decides φ; (2) its verdict, even a bare rejection, returns to generation at least once; (3) only candidates it accepts are submitted |

**Identifying R**

- Judge R from the method section, not from the paper's wording.
- If the method section gives no deterministic decision procedure, there is no R.
- If the text and the algorithm disagree on whether R is independent, code NS.
- Code the normal run path. Fallback and override paths are coded under R5.

**Write units (μ)**

- φ is a property of the written content.
- **Code NS when:**
  - content is written without checks, or with only deterministic assembly after extraction;
  - structured output only constrains format or value sets;
  - a reviewer only labels entries and every labeled entry is stored;
  - a reasoner is mentioned but its effect on writes is not specified.
- **R is present when:**
  - handlers for declared edge types enforce their semantics, and no write path bypasses the handlers. Then φ = "edge-type semantics and store invariants";
  - node types and references are validated. Then φ = "schema-conformant".

**Retrieval units (ρ)**

- **Default.** φ = "the answer is correct". A store-only R cannot decide this, so code NS, E.
- **Faithfulness.** φ = "the answer is grounded in the store" only if both hold:
  1. the paper claims faithfulness to the store;
  2. R constrains every submitted answer to the store.

  The unit can then be SN or HL, with assurance D/K-st.
- **Constraining evidence is not enough.** R that only filters or bounds the evidence, while the LLM writes the answer freely, does not satisfy condition 2.
- **`fallback` for retrieval units:**
  - **yes:** the LLM may answer from its own knowledge.
  - **unk:** the paper does not say what is answered when nothing grounding is found.
  - **empty:** answers come only from query execution.

**Boundary cases**

| Situation | Coding |
|---|---|
| Reject or resample without returning the verdict | SN |
| A gate's verdict is returned to the agent, and retries pass the same check | HL. If only a status code is returned → SN |
| A symbolic program inserts repair actions itself, with no verdict returned | SN |
| The LLM steps through a symbolic simulator; the plan is submitted only after a verifier accepts it | HL |
| The reviewer is an LLM, or check code written by the LLM for the current answer | NS |
| A repair loop driven by a parser, a solver over the generated model, executor errors or timeouts on the artefact, or structural rule scripts | NS + `repair_loop = yes` |
| Failed LLM code is regenerated without the error being returned | No `repair_loop` |
| The program is repaired only from checks on training tasks | NS + `repair_loop = yes` |
| Environment feedback on executed actions drives replanning | Not R; no `repair_loop`. Affects `binding` and `planning_loop` |
| The symbolic component runs only when a cheaper component fails | HL only for outputs that reach it. If unchecked outputs are submitted → `fallback = yes` |
| Symbolic feedback only during training | NS |
| Executability is the claimed φ | Can be SN |
| The LLM transcribes the symbolic output step by step, without adding, dropping or reordering steps | Pattern unchanged |
| The executed version is an unchecked LLM rewrite | NS |
| Plan steps invoke learned or LLM-written skills deterministically | Pattern unchanged; skill synthesis is a separate unit |
| A model is accepted or revised by item-wise comparison with observations | `env_validation = yes`, not `repair_loop` |

**`repair_loop`**

- `yes` if any synthesis unit in the work is repaired in a loop driven by a check that decides only well-formedness, runnability or solvability.

## R5 Fallback and human override

- Neither path changes the pattern.
- **Fallback.** After a rejection, timeout or uncovered case, an unchecked output is submitted. Code `fallback = yes`, and grade `assurance` by what the fallback path guarantees.
- **Human override.** A human can release an action judged violating, or submit an escalated decision. Code `human_override = yes`. Do not downgrade assurance.
- **`fallback` = empty when:**
  - an alternative generator's output must pass the same check;
  - the submitted best candidate still satisfies φ;
  - the check is the only generator;
  - on failure, the system submits nothing, returns failure, or hands control back to the user.
- **`fallback` = yes when:**
  - a warned call executes when re-issued;
  - a constraint is only logged;
  - a stage proceeds without the gate passing once its round or budget cap is reached;
  - a specification is removed after repeated violations.
- **`fallback` = unk** when the final-failure behavior is unspecified and another source could submit output. Do not downgrade `assurance`.
- **Not human override:**
  - goal changes;
  - editing stored content;
  - confirming proposals;
  - soft constraints the user sets in advance.
- **Configurable gates.** Code the main configuration only.
- **Scope.** Code `fallback` for the primary unit only.

## R6 LLM-written programs

| Situation | Pattern | `synthesis_role` |
|---|---|---|
| Fixed before it sees candidates; applied by an interpreter | Can be SN | model |
| Written for a specific candidate | NS | program |
| Executing it produces the submitted output | NS | program |

- Human-written programs: `provenance` A, `synthesis_role` none.
- These count as programs:
  - task-specific declarative configurations that an executor runs;
  - LLM-written planners;
  - query plans, relation paths or logical fragments written for the current question;
  - write queries whose execution produces the stored content.
- These do not count as programs:
  - a fixed query filled with LLM-supplied values → content;
  - step-by-step LLM scoring with no symbolic plan → none.
- State-maintenance code written offline and fixed before use → model, A+S.
- A fixed check applied to parameters the LLM extracted: pattern unchanged; reference at most K.

## R7 Formalism

- **Units with an independent R.** Code the language of the artefact R reads at runtime. Structures that reach R only through LLM transcription are not counted.
- **NS units.** Code the language of the artefact the unit queries; if it queries nothing, the artefact it submits.
- **Design-time structures.** Structures used only at design time go in `design_time_source`.

| Code | Definition |
|---|---|
| ONT | Class hierarchy with reasoner-usable axioms, used at runtime |
| KG | Graph whose schema types at most nodes and edges; includes typed record collections, task graphs and procedure DAGs |
| LOG | Logical, temporal or procedural specification, or program |
| HYB | Two formalisms, both read by R at runtime and both indispensable to the claim |
| OTH | Any other formalism |

- `design_time_source`: ONT or KG if the runtime artefact was derived from it and it is not used at runtime; otherwise empty.
- `language`: the specific language (optional).

## R8 Binding time

- Record every stage at which Σ is used:
  - units with R: the stages where R decides;
  - NS units: the stages where M is queried or written.

| Code | Stage |
|---|---|
| D | Before deployment, independent of any episode |
| G | During candidate construction or selection, on model-predicted state |
| E | Before an action takes effect, on observed real history |
| H | After effects occur, on recorded trajectories |

**Assigning the stage**

- Simulator execution → G.
- An artefact written at design time and checked at runtime → E.
- **Replanning:**
  - at each step, or when observations contradict the model → E;
  - only on external goal changes → G;
  - model revision from execution results across episodes → E.
- **NS units:**
  - store updated from observations and queried before each action → E;
  - static knowledge → G;
  - both → G+E.
- **Not D:**
  - training-time symbolic feedback;
  - specification analysis that decides no φ;
  - pen-and-paper proofs;
  - offline learning of a gate's rules.
- Offline induction followed by online revision → D+E.
- **Post-hoc checks:**
  - online check after each action that controls the next step → E+H;
  - offline audit only → H;
  - pre-call alert-only monitor → E.
- A transformation that decides no φ adds nothing.

**Consistency with `planning_loop`**

- `planning_loop = closed` requires E, except:
  1. the loop closes only through external goal changes;
  2. an offline-synthesized full-state policy → D;
  3. an NS unit querying static knowledge → G.

## R9 Provenance

**What to code**

- Units with R: the artefacts R checks against.
- NS units: the artefacts submitted or queried, including auxiliary structures and executed programs.
- Training-time feedback units: also the artefacts that produce the training signal.
- Environment models read directly by R → A.
- Initial states proposed by a neural model → S.

**What is excluded**

- LLM-extracted check inputs.
- State reconstructed deterministically from observations.
- artefacts that R does not read.
- Search-control artefacts (these go to `synthesis_role = search`).
- Task descriptions given only to the LLM.

**Mixed cases**

| Case | Code |
|---|---|
| LLM draft reviewed or corrected by humans | A+S |
| Human fixes only syntax errors | S |
| Mined from LLM-extracted data | M+S |
| LLM-generated, filtered by observed data | S + `env_validation = yes` |
| LLM selects from a human-written closed set | A+S, noted as selection-type |
| Deterministic conversion of human-written material | A |
| Enforced human-defined type vocabularies or schemas | A |

- Type lists that are not enforced, or architectural layers only → not A.
- Main vs. variant experiments: code the main experiment.
- Contradictory descriptions: follow the algorithm and figures.

| Code | Definition |
|---|---|
| A | Human-authored |
| M | Mined from observation data by non-neural methods |
| S | Produced by a neural model |
| U | Not reported |

## R10 Synthesis role

- Records the use of the unit's artefacts with S provenance, whether or not they are counted in `provenance`.
- **Priority:** program > model > content > search > none.

| Code | Use |
|---|---|
| program | Written for a specific candidate, or its execution produces the output; the unit is NS |
| model | Model, specification or fixed checking program that outputs are judged against |
| content | Stored content |
| search | Search control; not counted in `provenance` |
| none | No artefact with S provenance |

- `search` is assurance-neutral only if:
  1. `fallback` is empty;
  2. generated code runs isolated from the model, the property, the verifier, and search state it does not own.

## R11 Assurance

**Strength × reference**

- **Strength:**
  - E: empirical violation rates only;
  - P: probabilistic bound under explicit assumptions;
  - D: every submitted output satisfies φ.
- **Reference:**
  - **W** if at least one holds:
    - the verdict is on the executed object itself;
    - the verdict is on a model proven exact for φ;
    - for P, the bound is about the real world under explicit distributional assumptions.
  - **K** otherwise.

**Rules**

- NS → E.
- SN or HL → E only if `fallback = yes`.
- **Always K:**
  - pre-deployment proofs about a model;
  - learned models;
  - LLM-extracted parameters;
  - agent-reconstructed state;
  - pure PDDL benchmarks.
- Several environments: use the weakest.
- The reference does not depend on whether φ is adequate.
- **Order:**
  - E < P/K < D/K < D/W;
  - P/K < P/W < D/W;
  - D/K and P/W are incomparable;
  - D/K-st is unordered.

| Code | Definition |
|---|---|
| E | Empirical only |
| P/K | Probabilistic, relative to a model |
| P/W | Probabilistic, about the real world |
| D/K | Deterministic, relative to a model, specification or store |
| D/K-st | Store-only R; only under R4's faithfulness conditions |
| D/W | Deterministic, on the executed object (requires E) or on a model proven exact |

**`env_validation`**

- `yes` if model components are accepted or filtered one by one against observed environment behavior (execution, simulation, replay).
- These do not count:
  - neural perception only;
  - a single demonstration;
  - task-level success only;
  - LLM fact replacement;
  - outcome labels.
- `env_validation` does not upgrade K to W and does not count toward `evaluation`.

## R12 Assurance ceilings

| R decides | Ceiling |
|---|---|
| Properties of model content (validity, satisfaction, consistency, satisfiability) | D/K; D/W per R11 |
| Membership or reachability only | D/K-st for retrieval units meeting R4; otherwise NS, E |

- Judge by what R decides, not by the formalism.
- **Transition graphs.** Checking that a plan is a path through a transition graph is a content check, with φ = "conforms to the transitions".
- **Graphs without preconditions and effects** cannot establish plan validity → NS, E.

## R13 Functions and shared models

- Code functions for all units.
- The primary unit's function must appear in `functions` and match `pillar`.

| Code | Definition |
|---|---|
| P | Constructs, constrains or verifies plans |
| Mw | State kept within one episode, including gate traces |
| Ml | The agent's own experience, reused across episodes |
| Mk | External knowledge the agent reads |
| V | Checks an explicit property of actions, plans or trajectories |
| X | Checks only the executability of a pending action |

**`shared_models`**

- `=` joins functions that use the same model instance or its deterministic compilation.
- `;` separates instances.
- Each group has at least two codes.

**Mw, Ml or Mk**

- **Mw vs. Ml:** decided by episode scope, not by the paper's name for the memory.
- **Mk vs. Ml:** decided by the source of the content.
- **Both in one store:** code `Mk=Ml`.

**P, X or V**

- **P:**
  - executability constraints applied during plan construction;
  - specification masking during decoding;
  - whole-plan checks whose verdicts are returned for replanning.
- **X:** a check on the next action, against the current real observation, before execution.
- **V:** a property gate, or an independent guardrail that substitutes its own plan.
- **Unit Γ:** a unit whose output is a verdict on a given plan.
- **Input filters:**
  - filters on user input only are not gates;
  - gates on both input and output: code the output stage only.

## R14 Evaluation

- **Priority:** art-run > art-iso > out.
- **art-\*.** Code art-run or art-iso if the paper reports the quality of its own symbolic artefacts measured against a reference: a gold model, a human semantic annotation, or a specification, compared on a test set or checked item by item by an expert.
- **art-run vs. art-iso:**
  - **art-run:** the measured artefacts are the ones used in the evaluation runs, including artefacts generated once and loaded unchanged.
  - **art-iso:** the measured artefacts come from a separate experiment, differ from the version that runs, or are not stated to be the ones used.
- **Code out for:**
  - weak properties only (parsable, solvable, executable, or passing the validator);
  - attribution on failed runs only;
  - accuracy of gate verdicts;
  - accuracy of extracted check inputs;
  - pass rates against self-formalized assertions;
  - tests of human-written code;
  - graph statistics, size or growth;
  - checks on dataset labels;
  - evidence recall;
  - scores with no reference;
  - accuracy cited from other work;
  - LLM judgment without a gold reference;
  - papers with no quantitative evaluation.
- **Deterministic mapping.** Measuring LLM output that maps deterministically to the artefact counts as measuring the artefact.
- **Independence from `env_validation`.** `evaluation` and `env_validation` are coded independently.

## R15 Planning loop

| Code | Definition |
|---|---|
| single | The plan is generated once and execution results do not return |
| closed | Execution results can affect later decisions |
| na | Pillar is not P |

- **Code single for:**
  - iteration inside a simulator only;
  - re-prompting on code exceptions only;
  - loops described as out of scope.

## R16 Inclusion

| | Criterion |
|---|---|
| IC1 | Closes an observe–decide–act loop, or is a single-shot pipeline providing planning, memory or gating functions that closed-loop agents call; the neural component is an LLM or foundation model |
| IC2 | An explicit symbolic structure with machine-checkable semantics is a functional component |
| IC3 | Peer-reviewed, or a substantive preprint from an identifiable team |
| IC4 | 2022 or later, except foundational KR, planning and formal-methods work |

## R17 Exclusion

| | Criterion |
|---|---|
| EC1 | Purely neural agents |
| EC2 | Non-agentic LLM applications |
| EC3 | Position papers without method content |
| EC4 | Superseded versions |
| EC5 | Surveys, benchmarks and analyses that propose no system |

## R18 Record fields

- `no`: sequence number.
- `name`: the system name; if there is none, a 2–3 word English description.
- `title`: the title of the version that was coded.
- `year_first_public`: the year the earliest version of the work became public.
- `basis`: F (full text) or A (abstract only).

## R19 Cost of the symbolic layer

Coded in `cost_93.csv` for the 93 guaranteed units (`assurance` other than E and D/K-st), from the experiments that the paper reports. Each code is 1 if the paper reports the quantity and 0 otherwise.

| Column | Definition |
|---|---|
| `U` | Task success with and without the unit, on the same tasks and with the same LLM, by ablation or against an LLM-only baseline; for gates, also success on benign tasks with and without the gate, or the rate at which benign actions are blocked |
| `T` | A measured run time, latency, token count, number of LLM calls, or monetary cost |
| `A` | A quantified human effort to write, mine, or correct the unit's artefacts, such as the time spent or the number of rules written or corrections made; na if `provenance` contains neither A nor M |
| `evidence` | Where the paper reports the quantity, or why it is coded 0 |

- **Not counted for `T`:** limits, timeouts, qualitative statements, and totals over all compared methods.
- **Not counted for `A`:** domains supplied by a benchmark.

## Research community

`community_202.csv` assigns each work to a community by the primary category of its arXiv version, found by identifier or by title; for works without an arXiv version, by venue. Cross-listings are not used.

| Code | arXiv primary categories |
|---|---|
| AI | cs.AI, cs.MA |
| Robotics | cs.RO |
| NLP/IR | cs.CL, cs.IR |
| SE/FM/Security | cs.SE, cs.CR, cs.LO, cs.PL |
| ML | cs.LG |
| Other | cs.CV, cs.HC |

---

## Consistency checks

| # | Check |
|---|---|
| B1 | `pattern = NS` ⇒ `assurance = E` |
| B2 | `pattern ∈ {SN, HL}` ∧ `assurance = E` ⇒ `fallback = yes` |
| B3 | S ∈ `provenance` ⇔ `synthesis_role ∈ {model, content, program}` |
| B4 | `synthesis_role = program` ⇒ `pattern = NS` |
| B5 | `synthesis_role = search` ∧ `fallback = yes` ⇒ not reported as assurance-neutral |
| B6 | `assurance = D/W` ∧ E ∉ `binding` ⇒ model proven exact for φ |
| B7 | `assurance = D/K-st` ⇒ `formalism ∈ {KG, HYB}` |
| B8 | `env_validation = yes` ∧ `assurance ≠ E` ⇒ reference is K |
| B9 | `formalism = ONT` ⇒ ontology used by R at runtime |
| B10 | `pillar` P ⇒ P ∈ `functions`; M ⇒ Mw, Ml or Mk ∈ `functions`; V ⇒ V or X ∈ `functions` |
| B11 | Every code in `shared_models` is in `functions`; each group has ≥ 2 distinct codes |
| B12 | `planning_loop ≠ na` ⇔ `pillar = P` |
| B13 | `repair_loop = yes` ∧ the primary unit is a synthesis unit ⇒ `pattern = NS` |
| B14 | `basis = A` ⇒ flagged in the analysis |
| B15 | `synthesis_role = search` ⇒ `pattern ∈ {SN, HL}` |
| B16 | `assurance = D/K-st` ⇒ retrieval unit with a faithfulness claim |
| B17 | `pattern = NS` ⇒ `formalism` non-empty |
| B18 | `fallback = unk` ⇒ analyzed both as yes and as empty |
| B19 | Multi-valued fields use only `+` and valid codes |
| B20 | `planning_loop = closed` ∧ E ∉ `binding` ⇒ an R8 exception applies |
