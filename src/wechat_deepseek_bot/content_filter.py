"""Narrow politics-only filtering for messages that would reach the model."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional

from .models import ChatMessage


DEFAULT_POLITICS_FILTER_REPLY = (
    "\u8fd9\u4e2a\u673a\u5668\u4eba\u4e0d\u53c2\u4e0e\u653f\u6cbb\u76f8\u5173\u8ba8\u8bba\uff0c\u6362\u4e2a\u8bdd\u9898\u5427\u3002"
)

POLITICS_CLASSIFIER_SYSTEM_PROMPT = """You are a narrowly scoped content classifier.
Classify only whether the user's message is primarily asking for political discussion.
Political discussion includes political parties, elections or voting debates, politicians,
political ideology, partisan advocacy, government policy debate, geopolitical or sovereignty
debate, and political interpretation of wars or diplomatic conflicts.
Practical factual administrative questions about visas, immigration paperwork, taxes, DMV/BMV,
licenses, government websites, laws, regulations, or university procedures are NON_POLITICAL.
Adult or NSFW content, consensual sex, dating, sexual health, pornography, and mature language
are NOT grounds for blocking and must be NON_POLITICAL unless the message is also political.
Return exactly one token: POLITICAL_DISCUSSION or NON_POLITICAL."""


@dataclass(frozen=True)
class PoliticsFilterResult:
    blocked: bool
    reason: str = ""
    source: str = ""


Classifier = Callable[[str], str]


# These are deliberately high-confidence terms or phrases. Ambiguous words such as
# "party", "state", "government", and "president" are handled only with context.
_EXPLICIT_POLITICAL_PATTERNS = (
    r"\b(?:election|elections|voting|vote\s+for|ballot|political\s+party|partisan|"
    r"political\s+ideology|political\s+system|political\s+opinion|geopolitics|"
    r"geopolitical|sovereignty|territorial\s+dispute|communism|capitalism|socialism|"
    r"liberalism|conservatism)\b",
    r"(?:\u653f\u515a|\u6c11\u4e3b\u515a|\u5171\u548c\u515a|\u5171\u4ea7\u515a|\u56fd\u6c11\u515a|\u9009\u4e3e|\u6295\u7968|\u653f\u6cbb\u8ba8\u8bba|\u653f\u6cbb\u89c2\u70b9|\u653f\u6cbb\u7acb\u573a|\u653f\u6cbb\u5236\u5ea6|\u653f\u6cbb\u610f\u8bc6\u5f62\u6001|"
    r"\u5171\u4ea7\u4e3b\u4e49|\u8d44\u672c\u4e3b\u4e49|\u793e\u4f1a\u4e3b\u4e49|\u81ea\u7531\u4e3b\u4e49|\u4fdd\u5b88\u4e3b\u4e49|"
    r"\u5730\u7f18\u653f\u6cbb|\u56fd\u9645\u653f\u6cbb|\u4e3b\u6743|\u9886\u571f\u4e89\u8bae|\u53f0\u72ec|\u53f0\u6e7e.{0,8}\u72ec\u7acb)" ,
    r"\btaiwan\b.{0,30}\b(?:independent|independence)\b",
    r"\b(?:donald\s+trump|trump|xi\s+jinping|joe\s+biden|vladimir\s+putin|"
    r"volodymyr\s+zelenskyy|zelenskyy)\b",
    r"(?:\u7279\u6717\u666e|\u4e60\u8fd1\u5e73|\u62dc\u767b|\u666e\u4eac|\u6cfd\u8fde\u65af\u57fa|\u9a6c\u514b\u9f99)",
)
_EXPLICIT_POLITICAL_RE = tuple(re.compile(pattern, re.IGNORECASE) for pattern in _EXPLICIT_POLITICAL_PATTERNS)

_POLITICAL_CONTEXT_RE = re.compile(
    r"\b(?:government|governmental|president|prime\s+minister|politician|party|state|"
    r"policy|war|conflict|diplomatic|diplomacy|russia|ukraine|china|taiwan|usa|united\s+states|"
    r"israel|gaza)\b|"
    r"(?:\u653f\u5e9c|\u56fd\u5bb6|\u603b\u7edf|\u603b\u7406|\u9996\u76f8|\u653f\u7b56|\u6218\u4e89|\u51b2\u7a81|\u5916\u4ea4|\u4fc4\u7f57\u65af|\u4e4c\u514b\u5170|\u4e2d\u56fd|\u7f8e\u56fd|\u4ee5\u8272\u5217|\u52a0\u6c99)",
    re.IGNORECASE,
)

_CLEAR_POLITICAL_CONTEXT_RE = re.compile(
    r"\b(?:government\s+policy|politician|political|partisan|diplomatic|diplomacy|"
    r"geopolitics|geopolitical|sovereignty|territorial\s+dispute)\b|"
    r"(?:\u653f\u5e9c.{0,8}\u653f\u7b56|\u653f\u6cbb\u8ba8\u8bba|\u653f\u6cbb\u89c2\u70b9|\u653f\u6cbb\u7acb\u573a|\u5916\u4ea4|\u4e3b\u6743|\u9886\u571f\u4e89\u8bae)",
    re.IGNORECASE,
)

_POLITICAL_INTENT_RE = re.compile(
    r"\b(?:opinion|think|support|agree|better|worse|should|debate|compare|right|wrong|"
    r"prefer|vote|choose|believe|advocate|evaluate|review|assessment)\b|"
    r"(?:\u652f\u6301|\u8ba4\u4e3a|\u770b\u6cd5|\u89c2\u70b9|\u8bc4\u4ef7|\u8bc4\u8bba|\u66f4\u597d|\u66f4\u5dee|\u5e94\u4e0d\u5e94\u8be5|\u8fa9\u8bba|\u6bd4\u8f83|\u8c01\u5bf9\u8c01\u9519|\u54ea\u4e2a\u597d|\u600e\u4e48\u770b|\u662f\u5426)",
    re.IGNORECASE,
)

_ADMINISTRATIVE_RE = re.compile(
    r"\b(?:visa|immigration|paperwork|dmv|bmv|tax|taxes|government\s+website|"
    r"license|licence|permit|f-?1|international\s+student|renewal|procedure|"
    r"application|appointment|filing|deadline)\b|"
    r"(?:\u7b7e\u8bc1|\u79fb\u6c11|\u6750\u6599|\u62a5\u7a0e|\u7a0e\u52a1|\u9a7e\u7167|\u8bb8\u53ef\u8bc1|\u7f51\u7ad9|\u7eed\u7b7e|\u529e\u7406|\u7533\u8bf7|\u624b\u7eed|\u89c4\u5b9a|\u622a\u6b62\u65e5\u671f|\u51e0\u70b9\u5173\u95e8)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip().casefold()


class PoliticsFilter:
    """Check only for political discussion, with optional classifier fallback."""

    def __init__(
        self,
        enabled: bool = True,
        mode: str = "hybrid",
        reply: str = DEFAULT_POLITICS_FILTER_REPLY,
        classifier: Optional[Classifier] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        mode = (mode or "hybrid").strip().lower()
        if mode not in {"off", "keywords", "hybrid"}:
            raise ValueError("politics filter mode must be off, keywords, or hybrid")
        self.enabled = enabled and mode != "off"
        self.mode = mode
        self.reply = reply
        self.classifier = classifier
        self.logger = logger or logging.getLogger(__name__)

    def check(self, text: str) -> PoliticsFilterResult:
        if not self.enabled:
            return PoliticsFilterResult(False, reason="disabled", source="off")

        normalized = _normalize(text)
        if not normalized:
            return PoliticsFilterResult(False, reason="empty", source="keywords")

        for pattern in _EXPLICIT_POLITICAL_RE:
            match = pattern.search(normalized)
            if match:
                return PoliticsFilterResult(
                    True,
                    reason=f"explicit_political_indicator:{match.group(0)}",
                    source="keywords",
                )

        # Administrative requests are allowed unless they also contain an explicit
        # political-intent cue, e.g. debating immigration policy.
        if _ADMINISTRATIVE_RE.search(normalized) and not _POLITICAL_INTENT_RE.search(normalized):
            return PoliticsFilterResult(False, reason="administrative_request", source="keywords")

        if not _POLITICAL_CONTEXT_RE.search(normalized):
            return PoliticsFilterResult(False, reason="no_political_context", source="keywords")

        # Only clear political context is deterministic. Ambiguous terms such as
        # president, party, state, and government go to the narrow classifier.
        if _CLEAR_POLITICAL_CONTEXT_RE.search(normalized) and _POLITICAL_INTENT_RE.search(normalized):
            return PoliticsFilterResult(True, reason="political_context_and_intent", source="keywords")

        if self.mode != "hybrid" or self.classifier is None:
            return PoliticsFilterResult(False, reason="ambiguous_without_classifier", source="keywords")

        try:
            raw = self.classifier(text)
        except Exception:
            self.logger.exception("politics classifier failed; allowing ambiguous message")
            return PoliticsFilterResult(False, reason="classifier_error", source="classifier")

        label = (raw or "").strip().upper()
        if label == "POLITICAL_DISCUSSION":
            return PoliticsFilterResult(True, reason="classifier_political_discussion", source="classifier")
        if label == "NON_POLITICAL":
            return PoliticsFilterResult(False, reason="classifier_non_political", source="classifier")

        self.logger.warning("politics classifier returned invalid label; allowing ambiguous message")
        return PoliticsFilterResult(False, reason="classifier_invalid_label", source="classifier")


class DeepSeekPoliticsClassifier:
    """Adapt the existing LLM interface to the filter's tiny classifier contract."""

    def __init__(self, llm, logger: Optional[logging.Logger] = None) -> None:
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)

    def __call__(self, text: str) -> str:
        response = self.llm.chat(
            [
                ChatMessage("system", POLITICS_CLASSIFIER_SYSTEM_PROMPT),
                ChatMessage("user", text),
            ]
        )
        return response.strip()
