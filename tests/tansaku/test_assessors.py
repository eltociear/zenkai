import torch
import pytest
from zenkai.kaku.assess import AssessmentDict
from zenkai.kaku.io import IO
from zenkai.kaku.state import State

from zenkai.tansaku import assessors, Population
from zenkai.kaku import IO, State, LearningMachine, ThLoss
from ..kaku.test_machine import SimpleLearner


class SimpleLearner2(SimpleLearner):

    def forward(self, x: IO, state: State, release: bool = True) -> torch.Tensor:
        y = super().forward(x, state, False)
        y = IO(torch.mean(x[0], dim=1))
        return y.out(release)


class SimpleLearner3(LearningMachine):

    def __init__(self, in_groups: int, in_features: int, out_features: int):
        super().__init__()
        self.weight = torch.nn.parameter.Parameter(
            torch.rand(in_groups, in_features, out_features)
        )
        self.loss = ThLoss('mse')

    def step(self, x: IO, t: IO, state: State):
        pass

    def step_x(self, x: IO, t: IO, state: State) -> IO:
        pass

    def assess_y(self, x: IO, t: IO, reduction_override: str = None) -> AssessmentDict:
        return self.loss.assess_dict(x, t, reduction_override)

    def forward(self, x: IO, state: State, release: bool = True) -> torch.Tensor:
        
        y = IO((x[0].transpose(1, 0) @ self.weight).transpose(1, 0).contiguous())
        return y

class TestXPopulationAssessor:

    def test_assess_outputs_correct_size(self):
        learner = SimpleLearner(3, 4)

        population = Population(x=torch.rand(8, 3, 3))
        t = torch.rand(3, 4)
        assessor = assessors.XPopulationAssessor(
            learner, ['x'], 'loss', 'mean'
        )
        assessor.assess(population, IO(t))
        assert len(population.stack_assessments()) == 8
    
    def test_assess_outputs_correct_size_with_3_dims(self):
        learner = SimpleLearner3(3, 3, 4)

        population = Population(x=torch.rand(8, 4, 3, 3))
        t = torch.rand(4, 3, 4)
        assessor = assessors.XPopulationAssessor(
            learner, ['x'], 'loss', 'mean'
        )
        assessor.assess(population, IO(t))
        assert len(population.stack_assessments()) == 8