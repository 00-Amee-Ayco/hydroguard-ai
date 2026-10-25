"""Explicit prerecorded fixtures; no inference, model or sponsor call occurs."""
from hydroguard.data.sample import GAP_FINDING, HARM_FINDING
from hydroguard.evidence.models import CriticDecision, EvidenceFinding


def sample_critic(finding: EvidenceFinding) -> CriticDecision:
    if finding.text == HARM_FINDING:
        decision, reason = "reject", "Missing dry-season evidence is not proof of community water shortages."
    elif finding.text == GAP_FINDING and finding.claim_type == "evidence_gap":
        decision, reason = "approve", "Qualified gap limited to reviewed synthetic disclosures; no harm asserted."
    else:
        decision, reason = "reject", "No prerecorded approval fixture exists for this finding."
    return CriticDecision(finding_id=finding.finding_id, revision=finding.revision,
                          finding_fingerprint=finding.fingerprint(), decision=decision, reason=reason)
