"""Patch SafeTune's SafeGrad alignment gradient: per-token KL over real (non-pad) tokens.

SafeTune 0.1.8 computes F.kl_div(..., reduction="batchmean") on (batch, seq, vocab) logits, which
divides by batch size only: the KL is summed over every position, padding included. Against a
per-token-mean task loss and rho=1 that term is ~seq_len times too large, so it swamps the task
gradient and the model stays at the reference.
"""
import logging

import torch
import torch.nn.functional as F
from safetune.interventions.harden import safegrad as _sg

log = logging.getLogger(__name__)


def masked_token_kl(student_logits, aligned_logits, attention_mask, temperature=1.0):
    """Mean over non-pad tokens of KL(aligned || student), per token, temperature-scaled."""
    log_p = F.log_softmax(student_logits.float() / temperature, dim=-1)
    p_ref = F.softmax(aligned_logits.float() / temperature, dim=-1)
    per_token = (p_ref * (p_ref.clamp_min(1e-12).log() - log_p)).sum(-1)  # (batch, seq)
    mask = attention_mask.to(per_token.dtype)
    return (per_token * mask).sum() / mask.sum().clamp_min(1.0) * temperature ** 2


def _alignment_gradient(self, model, safety_batch):
    params = self._trainable_params(model)
    if not params:
        return None
    prepared = self._prepare_batch(safety_batch, model)
    if self._reference_model is None:
        align_loss = model(**prepared).loss
    else:
        student = model(**prepared)
        with torch.no_grad():
            ref = self._reference_model(**{k: v.to(self._reference_model.device) for k, v in prepared.items()})
        align_loss = masked_token_kl(student.logits, ref.logits.detach().to(student.logits.device),
                                     prepared["attention_mask"], self._kl_temperature)
    self._last_align_loss = float(align_loss.detach())
    grads = torch.autograd.grad(align_loss, params, allow_unused=True)
    return [g.detach() if g is not None else torch.zeros_like(p) for g, p in zip(grads, params)]


def apply():
    _sg.SafeGradHFTrainer._alignment_gradient = _alignment_gradient
    log.warning("SafeGrad alignment loss patched: masked per-token KL")


if __name__ == "__main__":  # unit check against the original reduction
    torch.manual_seed(0)
    B, T, V = 2, 6, 11
    s, r = torch.randn(B, T, V), torch.randn(B, T, V)
    mask = torch.ones(B, T); mask[1, 3:] = 0
    orig = _sg.safegrad_kl_alignment_loss(s, r)  # sums over T, divides by B
    full = masked_token_kl(s, r, torch.ones(B, T))
    assert torch.allclose(orig, full * T, atol=1e-5), (orig, full * T)
    # padding positions no longer contribute
    r2 = r.clone(); r2[1, 3:] = torch.randn(3, V) * 50
    assert torch.allclose(masked_token_kl(s, r, mask), masked_token_kl(s, r2, mask))
    assert masked_token_kl(r, r, mask).abs() < 1e-6
    print("ok: original = per-token KL x seq_len; mask excludes padding; KL(x||x)=0")
