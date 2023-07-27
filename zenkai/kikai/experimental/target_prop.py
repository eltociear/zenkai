# 1st party
import typing
from abc import abstractmethod

# 3rd Party
import torch
import torch.nn as nn

# Local
from ...kaku import AssessmentDict, OptimFactory, ThLoss
from ...kaku import (
    IO,
    LearningMachine,
    State,
    Loss,
    AssessmentDict
)


class TargetPropNet(nn.Module):

    @abstractmethod
    def forward(self, x: torch.Tensor, t: torch.Tensor, y: torch.Tensor) -> typing.Tuple[torch.Tensor]:
        pass


class StandardTargetPropNet(nn.Module):

    def __init__(self, base_net: nn.Module):
        """initializer

        Args:
            base_net (nn.Module): The base "reverse" network. Must take in the output as an input
            and predict a variation of the input
        """
        super().__init__()
        self.base_net = base_net

    def forward(self, x: torch.Tensor, t: torch.Tensor, y: torch.Tensor) -> typing.Tuple[torch.Tensor]:
        """Calculate the reconstruction of the input

        Args:
            x (torch.Tensor): The input to the "encoder"
            t (torch.Tensor): The target for the "encoder"
            y (torch.Tensor): The output from the "encoder"

        Returns:
            typing.Tuple[torch.Tensor]: the input predicted by the target, the input predicted by the output
        """
        y = self.base_net(torch.cat([t, y]))
        return y[:len(t)], y[len(t):]


class TargetPropLoss(Loss):

    @abstractmethod
    def forward(self, x: typing.Tuple[torch.Tensor], t, reduction_override: str=None) -> torch.Tensor:
        pass


class StandardTargetPropLoss(TargetPropLoss):

    def __init__(self, base_loss: ThLoss):
        """initializer

        Args:
            base_loss (ThLoss): The base loss to use in evaluation
        """
        super().__init__(base_loss.reduction, base_loss.maximize)
        self.base_loss = base_loss
    
    def forward(self, x: typing.Tuple[torch.Tensor], t, reduction_override: str = None) -> torch.Tensor:
        
        # 1) map y to the input (learn to autoencode)
        return self.base_loss(x[1], t, reduction_override=reduction_override)


class RegTargetPropLoss(TargetPropLoss):

    def __init__(self, base_loss: ThLoss, reg_loss: ThLoss):
        """initializer

        Args:
            base_loss (ThLoss): The loss to learn the decoding (ability to predict )
            reg_loss (ThLoss): The loss to minimize the difference between the x prediction
             based on the target and the x prediction based on y
        """
        super().__init__(base_loss.reduction, base_loss.maximize)
        self.base_loss = base_loss
        self.reg_loss = reg_loss
    
    def forward(self, x: typing.Tuple[torch.Tensor], t, reduction_override: str = None) -> torch.Tensor:
        
        # 1) map y to the input (learn to autoencode)
        # 2) reduce the difference between the mapping from y to x and the mapping from t to x 
        return (
            self.base_loss(x[1], t, reduction_override=reduction_override) +
            self.reg_loss(x[0], x[1].detach(), reduction_override=reduction_override)
        )


class TargetPropLearner(LearningMachine):

    def __init__(self, net: TargetPropNet, loss: TargetPropLoss, optim_factory: OptimFactory):
        """initializer

        Usage:
        
        # Typical usage would be to use target prop in the step x method
        # for a Learning Machine
        def step_x(self, ...)
            prop_conn = self.target_prop.prepare_conn(conn, prev_x)
            x = self.target_prop(prop_conn.step.x).sub(1).detach()
            self.target_prop.step(prop_conn)
            conn.step.x = x
            return conn.step.x.tie_inp()

        Args:
            net (TargetPropNet): The network to learn the reverse connection
            loss (TargetPropLoss): The loss function to assess the prediction of the inputs with
            optim_factory (OptimFactory): The optimizer factory to generate the optim
        """
        super().__init__()
        self.net = net
        self.optim_factory = optim_factory
        self.optim = self.optim_factory(net.parameters())
        self.loss = loss

    def prepare_io(self, x: IO, t: IO, y: IO):
        return IO(x[0], t[0], y[0]), x

    def assess_y(self, y: IO, t: IO, reduction_override: str = None) -> AssessmentDict:
        return self.loss.assess_dict(
            tuple(y), t[0], reduction_override
        )
    
    def step(self, x: IO, t: IO, state: State):
        """

        Args:
            x (IO): _description_
            t (IO): _description_
            state (State): _description_
        """
        
        y = state[self, 'y']
        self.optim.zero_grad()
        assessment = self.assess_y(y, t)
        assessment['loss'].backward()
        self.optim.step()
    
    def step_x(self, x: IO, t: IO, state: State) -> IO:
        """

        Args:
            x (IO): _description_
            t (IO): _description_
            state (State): _description_

        Returns:
            IO: _description_
        """
        x = x[0]
        x = x - x.grad
        x.grad = None

        return IO(x, detach=True)
    
    def forward(self, x: IO, state: State, release: bool = True) -> IO:
        x.freshen()
        y = state[self, 'y'] = IO(*self.net(*x), detach=False)
        return y.out(release)
