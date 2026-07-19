import re
import logging

logger = logging.getLogger("krish.classifier")

def classify(text: str, config: dict) -> str:
    clf_cfg = config.get("classifier", {})
    fast_patterns = clf_cfg.get("fast_patterns", [])
    thinking_patterns = clf_cfg.get("thinking_patterns", [])
    threshold = clf_cfg.get("complexity_threshold", 0.5)

    if not text or not text.strip():
        return "fast"

    cleaned = text.strip().lower()

    word_count = len(cleaned.split())
    fast_score = 0.0
    thinking_score = 0.0

    for pat in thinking_patterns:
        if re.search(pat, cleaned, re.IGNORECASE):
            thinking_score += 0.3

    for pat in fast_patterns:
        if re.search(pat, cleaned, re.IGNORECASE):
            fast_score += 0.25

    if word_count >= 15:
        thinking_score += 0.2
    if word_count <= 3:
        fast_score += 0.3

    if cleaned.endswith("?") and word_count <= 6:
        fast_score += 0.15

    if any(c in cleaned for c in ["\n", "{", "}", "(", ")", "def ", "class ", "import "]):
        thinking_score += 0.5

    has_code_indicators = bool(re.search(
        r"(```|`[a-z]+`|\b(function|class|def|import|const|let|var)\b)", cleaned
    ))
    if has_code_indicators:
        thinking_score += 0.6

    net_score = thinking_score - fast_score
    model_choice = "thinking" if net_score >= threshold else "fast"
    logger.info(
        f"Classified '{cleaned[:60]}...' -> {model_choice} "
        f"(thinking={thinking_score:.2f}, fast={fast_score:.2f}, net={net_score:.2f})"
    )
    return model_choice
