import torch
import torch.nn as nn

from zenkai.kaku import OptimFactory, IO, State
from zenkai.utils import get_model_parameters
from zenkai.kikai import feedback_alignment


class TestFA:

    def test_fa_updates_the_parameters(self):
        
        learner = feedback_alignment.FALinearLearner(3, 4, optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse')
        t = feedback_alignment.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
        x = IO(torch.rand(3, 3))
        before = get_model_parameters(learner)
        learner.step(x, t, State())
        assert (get_model_parameters(learner) != before).any()

    def test_fa_backpropagates_the_target(self):
    
        learner = feedback_alignment.FALinearLearner(3, 4, optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse')
        t = feedback_alignment.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
        x = IO(torch.rand(3, 3))
        x2 = learner.step_x(x, t, State())
        assert x2[0].shape == x[0].shape
        assert (x2[0] != x[0]).any()

    def test_fa_outputs_correct_value_forward(self):
        
        learner = feedback_alignment.FALinearLearner(3, 4, optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse')
        t = feedback_alignment.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
        x = IO(torch.rand(3, 3))

        y = learner(x)
        assert (y[0].shape[1] == 4)


class TestBStepX:

    def test_bstepx_backpropagates_the_target(self):
    
        step_x = feedback_alignment.BStepX(3, 4)
        t = feedback_alignment.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
        x = IO(torch.rand(3, 3))
        x2 = step_x.step_x(x, t, State())
        assert x2[0].shape == x[0].shape
        assert (x2[0] != x[0]).any()

class TestFALearner:

    def test_fa_updates_the_parameters(self):
        
        learner = feedback_alignment.FALearner(
            nn.Linear(3, 4), nn.Linear(3, 4), 
            optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse'
        )
        t = IO(torch.rand(3, 4))
        x = IO(torch.rand(3, 3))
        before = get_model_parameters(learner)
        learner.step(x, t, State())
        assert (get_model_parameters(learner) != before).any()

    # def test_fa_backpropagates_the_target(self):
    
    #     learner = fa.FALinearLearner(3, 4, optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse')
    #     t = fa.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
    #     x = IO(torch.rand(3, 3))
    #     x2 = learner.step_x(x, t, State())
    #     assert x2[0].shape == x[0].shape
    #     assert (x2[0] != x[0]).any()

    # def test_fa_outputs_correct_value_forward(self):
        
    #     learner = fa.FALinearLearner(3, 4, optim_factory=OptimFactory('sgd', lr=1e-2), loss='mse')
    #     t = fa.fa_target(IO(torch.rand(3, 4)), IO(torch.rand(3, 4)))
    #     x = IO(torch.rand(3, 3))

    #     y = learner(x)
    #     assert (y[0].shape[1] == 4)
