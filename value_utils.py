from dataclasses import dataclass

@dataclass
class ValuePick:
    odds: float
    model_probability: float

    @property
    def implied_probability(self) -> float:
        return 1 / self.odds

    @property
    def edge(self) -> float:
        return self.model_probability - self.implied_probability

if __name__ == "__main__":
    pick = ValuePick(odds=1.61, model_probability=0.622)
    print("Probabilidad implicita:", round(pick.implied_probability * 100, 2), "%")
    print("Edge:", round(pick.edge * 100, 2), "%")
