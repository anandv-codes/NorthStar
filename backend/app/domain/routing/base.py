from abc import ABC, abstractmethod

from .contracts import IntentContext, IntentDecision, IntentSignal


class BaseIntentRule(ABC):
    @abstractmethod
    def score(self, context: IntentContext) -> IntentSignal | None:
        pass


class BaseIntentClassifier(ABC):
    @abstractmethod
    def classify(self, context: IntentContext) -> IntentDecision:
        pass

