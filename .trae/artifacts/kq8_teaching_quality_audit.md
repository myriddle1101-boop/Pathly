# KQ8 Golden Five Teaching-Quality Audit

Date: 2026-08-15  
Scope: the five-node neural-network path only. This is a read-only audit; it does not revise sources, graph data, prompts, or learner content.

## Executive conclusion

The approved semantic release contains the minimum factual teaching contract for all five nodes: five claim types (definition, mechanism, boundary, example, counterexample), two misconceptions, three assessment targets, and source-page references per node. That makes the current fallback factually bounded.

It is **not yet a sufficient teaching-quality substrate** for two genuinely different learner experiences. Its examples are mostly one-sentence assertions; it lacks reusable worked derivations, visual/coordinate descriptions, alternative contexts, formula-level explanations, and Foundation/Advanced-specific pedagogical assets. The current fallback necessarily reuses the same small set of claim strings across page explanation, example, summary, and questions, which produces the template-like quality observed in the browser.

There is also a delivery-layer gap: the approved KQ1/KQ5 semantic release is sound, but the legacy Neo4j `Concept` graph and public Chroma metadata do not meet the claimed end-to-end runtime standard. V4 fallback currently reads the approved Python semantic profiles directly rather than rebuilding each teaching pack from Neo4j + Chroma.

## Evidence and structural findings

| Check | Result | Meaning |
|---|---|---|
| `golden_teaching_semantics.validate_profiles()` | Pass | All five profiles have the expected claim, misconception, target and source-page fields. |
| KQ5 release manifest | Pass | Each node is marked claim/evidence/misconception/target complete. |
| Live `kg_golden_audit.py` against Neo4j + Chroma | 0/5 verified overall | Legacy graph relationships and Chroma page metadata are not fully reconciled with the approved semantic release. |
| Runtime fallback source | Direct semantic profile | It is evidence-bounded but does not prove full Neo4j + Chroma reconstruction at generation time. |

The live legacy-graph audit recorded these concrete defects:

- `Linear Separability → XOR` is absent from the legacy `Concept` chain.
- Legacy `XOR` `Concept` is missing.
- `Neural Networks` and `Activation Functions` form a prerequisite cycle in the legacy graph.
- `Gradient Descent` still has `Backpropagation` as a prerequisite and needs direction review.
- Public Chroma chunks are indexed but do not preserve page metadata expected by the legacy audit.

These findings do not invalidate the approved KQ5 release used by the current fallback. They do invalidate the stronger claim that live V4 can reconstruct the same audited teaching pack solely from the reconciled Neo4j + Chroma base.

## Teaching-quality rubric

For each node, the audit looked for material sufficient to write both a Foundation and an Advanced lesson without inventing unsupported content:

1. mechanism that can be shown as a reasoning chain;
2. concrete worked example with intermediate steps;
3. counterexample/boundary that can be compared, not merely stated;
4. formula, diagram, coordinate, or code affordance where relevant;
5. plausible misconceptions with corrections;
6. at least two natural contexts so personalization changes the example rather than just its opening sentence.

## Node-level findings

| Node | Current strengths | Missing teaching assets | Audit verdict |
|---|---|---|---|
| Linear Separability | Accurate representation/boundary distinction; XOR counterexample; two useful misconceptions. | No coordinate-level point set, no candidate-line comparison, no explicit feature-transform worked example, no advanced geometric formulation. | Factually ready; teaching assets incomplete. |
| XOR | Truth-pattern example; clear linear-versus-nonlinear boundary. | No fully worked hidden-feature construction, no numeric hidden-layer example, no diagram/coordinate transformation, no runnable minimal code task. | Factually ready; teaching assets incomplete. |
| Neural Networks | Clear hidden-representation mechanism and linear-stack boundary. | No forward-pass worked example, no concrete representation table, no parameter/activation trace, no architecture comparison. | Factually ready; teaching assets incomplete. |
| Activation Functions | Correct ReLU example and linear-composition counterexample. | No input-to-output table across multiple values, no derivative/saturation boundary, no comparison among activation families, no link from activation choice to optimisation behaviour. | Factually ready; teaching assets incomplete. |
| Gradient Descent | Strongest current mechanism: gradient, learning rate, opposite-direction update. | No multi-step numeric update, no loss-surface intuition/diagram description, no learning-rate contrast, no explicit connection to gradients from backpropagation. | Factually ready; teaching assets incomplete. |

## Why the browser output still feels similar

The fallback has one approved `example` and one `counterexample` per concept. It uses those same strings in the hook, explanation, worked example, recap and three questions. Foundation changes ordering and scaffolding; Advanced changes compression and framing. Those are real differences, but they cannot become deeply different lessons when both versions draw from the same single-sentence assets.

## Required remediation before another content-quality acceptance

1. Reconcile the five-node runtime graph: canonical nodes, prerequisite direction, aliases, and Chroma page metadata.
2. Extend each approved teaching profile with reviewable assets, not free-form model memory:
   - `worked_example_foundation` with intermediate steps;
   - `worked_example_advanced` with derivation, assumption or code task;
   - `visual_or_coordinate_description` where relevant;
   - `formula_explanation` with symbol meanings;
   - `contextual_example_variants` containing at least two natural domains;
   - `transfer_challenge` and `boundary_challenge`.
3. Bind every new factual asset to a page/chunk reference and review it through the existing KQ5 release process.
4. Only then repair the live generation path and use it to express the richer approved material.

## Decision

Do not expand the KG beyond the golden five. The next work should be a targeted **KQ8 teaching-asset enrichment plus runtime evidence reconciliation**. It directly addresses the template-like output while preserving the existing canonical facts and quality gates.
