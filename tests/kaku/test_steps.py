# import torch

# from zenkai import utils
# from zenkai.kaku.machine import IO, Conn
# from zenkai.kaku.state import State
# from zenkai.kaku.steps import IterHiddenStep, IterOutStep

# from .test_machine import SimpleLearner


# class TestIterHiddenStep:
    
#     def test_iter_hiddenstep_updates_the_parameters_with_one_iteration(self):

#         torch.manual_seed(3)
#         learner1 = SimpleLearner(2, 3)
#         learner2 = SimpleLearner(3, 3)    
#         x = IO(torch.rand(2, 2))
#         t = IO(torch.rand(2, 3))
#         iter_step = IterHiddenStep(learner1, learner2, 1, 1, 1)
#         state = State()
#         y1 = learner1(x, state)
#         learner2(y1, state)
#         learner2.step(y1, t, state)

#         before = utils.get_model_parameters(learner1)
#         iter_step.step(Conn(in_x=x, in_t=y1, out_x=y1, out_t=t), state)
#         after = utils.get_model_parameters(learner1)
#         assert (before != after).any()


# class TestIterOutStep:

#     def test_iter_outstep_updates_the_parameters_with_one_iteration(self):

#         torch.manual_seed(1)
#         learner1 = SimpleLearner(2, 3)  
#         x = IO(torch.rand(2, 2))
#         t = IO(torch.rand(2, 3))
#         iter_step = IterOutStep(learner1, 1, 128)
#         before = utils.get_model_parameters(learner1)
#         state = State()
#         y1 = learner1(x, state)
#         iter_step.step(Conn(in_x=x, in_t=t), state)
#         after = utils.get_model_parameters(learner1)
#         assert (before != after).any()
