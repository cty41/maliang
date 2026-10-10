"""Deterministic visual execution briefs, not visual designs or approvals.

Drafts contain schemaVersion plus identity, topology, silhouetteClass,
visualMoment, paletteRoles, targets and references. Empty paletteRoles/targets
inherit explicit family values; references is an ordered list of role-bound
inputs and may be empty. Topology parts require only an id, with an optional
text description. Shape intentions must be permitted by the family, but need
not be expressible by the debug renderer. Family variants are optional.

compile_design(contract, draft) returns a ConstructionPacket containing the
prompt, tasks, inherited targets, reference-only imageInputs, pending acceptance
and context layout. It does not render images. validate_design uses the same
brief validation by default. Family drawing rule IDs must not use built-in
acceptance IDs: technical-targets, identity, pose or palette.

Both APIs accept keyword-only debug_geometry=True. That mode requires numeric
variants and part anchor/size pairs and supports only capsule/ball. Variant
fractions use source-canvas dimensions; part coordinates use the core-local
unit rectangle. guides holds optional PNG bytes, while options/debugArtifacts
are labeled debug-layout, unapproved, not-generation-input. Ellipsoid parts and
screen-direction triangles show code layout, not species, silhouette design,
isometric projection or pose proof. Their coordinates do not enter the prompt.

Palette values are human-reviewed role targets; drawingRules.required separates
hard requirements from suggestions. alpha-bounds accepts only its exact declared
technical predicate. No generation, reference file access, candidate adoption or
runtime writes occur here. Actual backend parameters and reference submission
remain unverified until an execution adapter binds them.
"""
from .compiler import ConstructionPacket, audit_alpha_bounds, compile_design
from .validation import DesignError, Diagnostic, validate_design

__all__ = ["ConstructionPacket", "DesignError", "Diagnostic", "audit_alpha_bounds", "compile_design", "validate_design"]
