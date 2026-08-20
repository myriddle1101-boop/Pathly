"""Seed the reviewed first teaching-asset bundle for the golden five.

The bundle is deliberately small and evidence-bounded. It is a curated
baseline for TA3, not a general-domain content importer.
"""
from __future__ import annotations

from teaching_asset_store import TeachingAssetStore

DOC_MLP = "public:01e27d8d07707beb3f8eb4ba3bfe4018f3dd4a2d14e2976aaba0ddf32c867207"
DOC_NN = "public:8aae94ed012561752b0e064e7d1d6d6f81ebb973da4d19e44693e3f0763cf773"

NODES = {
    "linear-separability": {
        "name": "Linear Separability", "doc": DOC_MLP, "pages": [2, 3],
        "foundation_intuition": {"setup": "Place positive and negative examples as points on a sheet.", "steps": ["Mark the two classes.", "Try one straight line.", "Check every point, not just the nearest pair.", "If one line puts all classes on opposite sides, the representation is linearly separable."], "takeaway": "The property belongs to the current representation."},
        "foundation_worked_example": {"points": "Use the four XOR corners: (0,0), (0,1), (1,0), (1,1).", "steps": ["Label (0,1) and (1,0) positive.", "Label (0,0) and (1,1) negative.", "Any line separating the two positive corners leaves one negative corner on the wrong side.", "Therefore the original representation is not linearly separable."], "answer": "A different feature representation is needed before a linear boundary can work."},
        "visual_or_coordinate_description": {"description": "A line divides the plane into two half-planes. The XOR labels alternate around the square, so neither half-plane assignment matches both classes."},
        "advanced_derivation": {"notation": "A linear classifier uses w^T x + b = 0 as its decision boundary.", "derivation": ["The sign of w^T x + b assigns a side of the boundary.", "Separability requires one choice of w and b that gives all positive points one sign and all negative points the other.", "This is a representational condition, separate from whether optimisation finds those parameters."], "boundary": "A nonlinear feature map can make the transformed points separable."},
        "advanced_worked_example": {"task": "Diagnose a proposed feature map for XOR.", "steps": ["Start with the alternating labels in (x1,x2).", "Add a feature that responds to the joint condition x1 and x2.", "Inspect whether a linear separator exists in the expanded representation.", "State which representational change, rather than which optimiser, removed the obstacle."], "answer": "Separability can change after representation changes; it is not a permanent label of the task."},
        "transfer_challenge": {"prompt": "A dataset is not linearly separable in its current features. What evidence would justify trying a feature transformation before a more complex optimiser?", "target": "representation-limit judgement"},
    },
    "xor": {
        "name": "XOR", "doc": DOC_MLP, "pages": [2, 3, 4, 5, 6, 7],
        "foundation_intuition": {"setup": "XOR returns 1 only when exactly one switch is on.", "steps": ["Same inputs (0,0) and (1,1) produce 0.", "Different inputs (0,1) and (1,0) produce 1.", "The positive answers sit on opposite corners, so one straight boundary cannot collect them.", "A hidden nonlinear representation can rearrange the problem."], "takeaway": "The difficulty is geometric, not the names of the labels."},
        "foundation_worked_example": {"table": [[0,0,0],[0,1,1],[1,0,1],[1,1,0]], "steps": ["Read the two input bits.", "Compare whether they match.", "Assign 1 only for a mismatch.", "Observe the alternating corners in the input plane.", "Explain why one line cannot isolate both positive corners."], "answer": "XOR needs a representation change before a final linear decision."},
        "visual_or_coordinate_description": {"description": "Draw a unit square: the two positive corners are diagonal from each other and the two negative corners occupy the other diagonal."},
        "advanced_derivation": {"notation": "A hidden layer can create features whose combinations make the XOR classes separable.", "derivation": ["A purely linear composition remains linear.", "A nonlinear activation changes the hidden coordinates.", "The output layer can then use a linear boundary in that new representation."], "boundary": "More linear depth without activation does not change the XOR representational limit."},
        "advanced_worked_example": {"task": "Explain an XOR network as representation construction.", "steps": ["Identify the two alternating positive corners.", "Choose hidden features that respond to useful half-spaces.", "Apply a nonlinearity so their combination is not reducible to one linear map.", "Use the output layer to separate the transformed features."], "answer": "The hidden nonlinearity, not depth alone, supplies the missing representational capacity."},
        "transfer_challenge": {"prompt": "A deeper network still fails XOR after every layer is linear. Which intervention addresses the actual mechanism-level limitation?", "target": "nonlinearity-versus-depth boundary"},
    },
    "neural-networks": {
        "name": "Neural Networks", "doc": DOC_NN, "pages": [13, 14],
        "foundation_intuition": {"setup": "Treat each hidden layer as a feature-making stage.", "steps": ["The input contains raw coordinates.", "A weighted transformation combines them.", "A nonlinear activation changes the representation.", "The next layer makes a decision from the new features."], "takeaway": "A neural network learns a sequence of representations, not a pile of unrelated lines."},
        "foundation_worked_example": {"task": "Trace one binary classification example through a small network.", "steps": ["Name the input features.", "Compute a weighted combination in a hidden unit.", "Apply an activation and record the new feature.", "Pass hidden features to the output decision.", "Identify where nonlinear representation enters."], "answer": "The hidden representation is the bridge between raw input and the final decision."},
        "visual_or_coordinate_description": {"description": "Show arrows from input nodes to hidden nodes to an output node; annotate each hidden node as a learned feature rather than a final class label."},
        "advanced_derivation": {"notation": "h = σ(Wx+b), y = Vh+c.", "derivation": ["Wx+b forms an affine representation.", "σ changes that representation when it is nonlinear.", "The output layer operates on h rather than directly on x.", "If σ is removed and every layer is linear, the composition collapses to one affine map."], "boundary": "Depth without nonlinearity does not add nonlinear capacity."},
        "advanced_worked_example": {"task": "Compare a two-layer linear stack with a nonlinear hidden layer.", "steps": ["Write the first affine map.", "Compose it with the second affine map.", "Observe that the result can be rewritten as one affine map.", "Insert σ between layers and identify what algebraic simplification is no longer valid."], "answer": "The activation is the representational hinge, while learned parameters determine which useful features are found."},
        "transfer_challenge": {"prompt": "A model has many layers but all are linear. What capability is still missing for XOR-like structure?", "target": "architecture-versus-representation reasoning"},
    },
    "activation-functions": {
        "name": "Activation Functions", "doc": DOC_NN, "pages": [15, 16, 17],
        "foundation_intuition": {"setup": "Compare a calculator that only rescales numbers with one that also bends the rule for negative values.", "steps": ["A weighted sum produces a numerical input.", "ReLU maps negative values to zero.", "It leaves positive values unchanged.", "The next layer receives a changed representation."], "takeaway": "The activation changes what later layers can represent."},
        "foundation_worked_example": {"table": [[-2,0],[-0.5,0],[0,0],[3,3]], "steps": ["Compute the weighted input z.", "If z is negative, ReLU outputs 0.", "If z is positive, ReLU outputs z.", "Compare this with a second linear layer, which would only rescale z."], "answer": "The piecewise operation creates a nonlinearity that a stack of linear operations lacks."},
        "visual_or_coordinate_description": {"description": "The ReLU graph follows the horizontal axis for negative inputs and the diagonal y=x for positive inputs, creating a kink at zero."},
        "advanced_derivation": {"notation": "ReLU(z)=max(0,z).", "derivation": ["A linear layer computes z=Wx+b.", "ReLU applies different rules on the negative and positive regions.", "That piecewise change prevents the full network from collapsing into one linear map.", "Removing every activation restores the linear-composition boundary."], "boundary": "The exact activation affects gradients and representational behaviour; it is not merely an output label."},
        "advanced_worked_example": {"task": "Diagnose what is lost when activations are removed.", "steps": ["Write two affine layers with an activation between them.", "Remove the activation.", "Multiply the matrices and combine the bias terms.", "Compare the resulting single affine map with the original piecewise map."], "answer": "The no-activation stack cannot express the same nonlinear representation."},
        "transfer_challenge": {"prompt": "When would adding another linear layer fail to solve a representation problem, and what operation changes that conclusion?", "target": "activation necessity boundary"},
    },
    "gradient-descent": {
        "name": "Gradient Descent", "doc": DOC_NN, "pages": [18, 19, 20],
        "foundation_intuition": {"setup": "Imagine adjusting one parameter while watching a loss value.", "steps": ["Measure the current loss.", "Use the gradient to identify the local uphill direction.", "Move in the opposite direction.", "Use the learning rate to choose the step size.", "Measure the loss again."], "takeaway": "The update is a direction-and-step decision, not a replacement value."},
        "foundation_worked_example": {"numbers": {"parameter": 2.0, "gradient": 0.5, "learning_rate": 0.1}, "steps": ["Start with θ=2.0.", "Compute the update 0.1×0.5=0.05.", "Subtract it: θ_new=1.95.", "If the gradient sign reverses, the update direction reverses too."], "answer": "The gradient is scaled by the learning rate and subtracted from the current parameter."},
        "visual_or_coordinate_description": {"description": "On a loss curve, the gradient points uphill locally; gradient descent takes a step downhill, with the learning rate controlling its length."},
        "advanced_derivation": {"notation": "θ_{t+1}=θ_t−η∇L(θ_t).", "derivation": ["∇L(θ_t) is the local slope vector.", "η scales the proposed movement.", "The negative sign selects local loss reduction.", "The approximation is local, so curvature, noise, and step size affect progress."], "boundary": "A large step can overshoot; a small step can make progress impractically slow."},
        "advanced_worked_example": {"task": "Compare two learning rates on the same local gradient.", "steps": ["Hold θ and ∇L fixed.", "Compute the update with η=0.1.", "Compute it again with η=1.0.", "Compare whether the second step remains within the useful local approximation.", "State why a learning rate affects success, not only speed."], "answer": "The update rule is direction plus scale; the local gradient alone does not determine a safe step."},
        "transfer_challenge": {"prompt": "If loss rises after an update, which parts of the update should be checked before concluding that the gradient concept is wrong?", "target": "update-direction and learning-rate diagnosis"},
    },
}


EXTRA_ASSETS = {
    "linear-separability": {
        "formula_explanation": {"formula": "w^T x + b = 0", "symbols": {"w": "normal vector to the boundary", "x": "input representation", "b": "offset"}, "meaning": "The sign of the score selects one side of the boundary."},
        "code_exercise": {"starter": "points = [(0,0),(0,1),(1,0),(1,1)]", "task": "Assign XOR labels and test a proposed line by checking the sign of w^T x+b for every point.", "check": "A valid separator must classify all four points correctly."},
        "contextual_example_variant": {"variants": ["separate two groups of plotted sensor readings", "decide whether two clusters can be separated by one straight rule"], "constraint": "The scenario changes, but separability still refers to the current representation."},
    },
    "xor": {
        "formula_explanation": {"formula": "x1 XOR x2 = 1 when x1 != x2", "symbols": {"x1,x2": "binary inputs", "1": "different inputs", "0": "matching inputs"}, "meaning": "The truth pattern creates alternating labels around the square."},
        "code_exercise": {"starter": "pairs = [(0,0),(0,1),(1,0),(1,1)]", "task": "Write the XOR rule, print its truth table, and explain why one linear score cannot separate the positive corners.", "check": "The positive rows are (0,1) and (1,0)."},
        "contextual_example_variant": {"variants": ["two switches where exactly one must be on", "a parity check that flags an odd number of active inputs"], "constraint": "The task remains a geometric alternating-label problem."},
    },
    "neural-networks": {
        "formula_explanation": {"formula": "h = σ(Wx+b), y = Vh+c", "symbols": {"x": "input", "W,b": "hidden-layer parameters", "σ": "nonlinear activation", "V,c": "output parameters"}, "meaning": "The hidden representation h is what lets later layers reason over learned features."},
        "code_exercise": {"starter": "h = relu(W @ x + b)", "task": "Trace one input through the affine operation, activation, and output layer; label which values are representations and which are predictions.", "check": "The activation changes h before the output computation."},
        "contextual_example_variant": {"variants": ["combine pixel features before an image decision", "combine measured signals before a binary decision"], "constraint": "The hidden layer is a learned representation, not an explanatory label."},
    },
    "activation-functions": {
        "formula_explanation": {"formula": "ReLU(z) = max(0,z)", "symbols": {"z": "weighted input to a unit", "0": "the negative-side output floor"}, "meaning": "The piecewise rule creates a kink and changes the representation passed onward."},
        "code_exercise": {"starter": "def relu(z): return max(0, z)", "task": "Evaluate the function on negative, zero, and positive inputs, then compare it with two stacked linear operations.", "check": "The negative side is clipped while positive values pass through."},
        "contextual_example_variant": {"variants": ["turn a negative evidence score into no active feature", "keep positive image evidence while suppressing negative evidence"], "constraint": "The scenario illustrates the same numerical piecewise operation."},
    },
    "gradient-descent": {
        "formula_explanation": {"formula": "θ_{t+1} = θ_t − η∇L(θ_t)", "symbols": {"θ": "current parameters", "η": "learning rate", "∇L": "local loss gradient"}, "meaning": "The update scales and subtracts the local uphill direction."},
        "code_exercise": {"starter": "theta = theta - learning_rate * gradient", "task": "Run two updates with the same gradient and two learning rates; compare the resulting parameter movement.", "check": "Changing the learning rate changes step size, not the gradient's meaning."},
        "contextual_example_variant": {"variants": ["adjust a model parameter to reduce prediction error", "tune a visual classifier after measuring its loss"], "constraint": "The example must identify loss, gradient, direction, and step size."},
    },
}


def seed() -> dict[str, int | str]:
    store = TeachingAssetStore()
    asset_ids = []
    for slug, node in NODES.items():
        for asset_type, tier in [
            ("foundation_intuition", "foundation"),
            ("foundation_worked_example", "foundation"),
            ("visual_or_coordinate_description", "shared"),
            ("advanced_derivation", "advanced"),
            ("advanced_worked_example", "advanced"),
            ("transfer_challenge", "advanced"),
            ("formula_explanation", "shared"),
            ("code_exercise", "shared"),
            ("contextual_example_variant", "shared"),
        ]:
            asset_id = f"{slug}-{asset_type}-v1"
            pages = node["pages"]
            store.upsert({
                "asset_id": asset_id,
                "canonical_concept_id": f"golden:{slug}",
                "asset_type": asset_type,
                "learner_tier": tier,
                "content": node.get(asset_type) or EXTRA_ASSETS[slug][asset_type],
                "assessment_targets": [f"{slug}-mechanism", f"{slug}-boundary"],
                "misconception_ids": [],
                "knowledge_version": "ta-golden-v2",
                "review_status": "approved",
                "evidence_refs": [{"document_id": node["doc"], "page_number": page} for page in pages],
            })
            asset_ids.append(asset_id)
    return store.publish_bundle(manifest_version="ta-golden-v2", asset_ids=asset_ids)


if __name__ == "__main__":
    print(seed())
