# 1st party
from abc import abstractmethod

# 3rd party
import numpy as np

# local
from ..kaku import (
    IO,
    StepTheta,
    PostStepTheta,
    State
)


class StackPostStepTheta(PostStepTheta):
    """Save the inputs and outputs to a 
    Useful if you want to optimize after propagating backwards like when
    you want to reuse a layer
    """

    def __init__(self, base_step_theta: StepTheta):
        """initializer

        Args:
            base_step_theta (StepTheta): The base step method to call after postponing
        """
        super().__init__()
        self._base_step_theta = base_step_theta
    
    def step(self, x: IO, t: IO, state: State):
        
        if (self, 'stack') not in state:
            state[self, 'stack_x'] = []
            state[self, 'stack_t'] = []
        state[self, 'stack_x'].append(x)
        state[self, 'stack_t'].append(t)
    
    def adv(self, state: State):
        """complete the step by concatenating all ios and running
        the base step method

        Args:
            state (State): The learning state

        Raises:
            RuntimeError: if step has not been executed
        """
        
        stack_x = state.get(self, 'stack_x')
        stack_t = state.get(self, 'stack_t')
        if stack_x is None or stack_t is None:
            raise RuntimeError('Cannot adv if step has not been executed')
        
        x = IO.cat(stack_x)
        t = IO.cat(stack_t)
        self._base_step_theta.step(x, t, state)
