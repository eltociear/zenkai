# 1st Party
import math
import typing
from functools import singledispatch

import numpy as np
import torch
import torch.nn as nn
import torch.nn.utils as nn_utils

# 3rd party
from torch.nn.utils import parameters_to_vector, vector_to_parameters
from torch.utils import data as torch_data


def to_np(x: torch.Tensor) -> np.ndarray:
    return x.detach().cpu().numpy()


def to_th(
    x: np.ndarray,
    dtype: torch.dtype,
    device: torch.device,
    requires_grad: bool = False,
    retains_grad: bool = False,
) -> torch.Tensor:
    """

    Args:
        x (np.ndarray): Array to convert
        dtype (torch.dtype): type to convert to
        device (torch.device): device to convert to
        requires_grad (bool, optional): Whether the tensor requires grad. Defaults to False.
        retains_grad (bool, optional): Whether the tensor retains a grad. Defaults to False.

    Returns:
        torch.Tensor: _description_
    """
    x: torch.Tensor = torch.tensor(
        x, dtype=dtype, requires_grad=requires_grad, device=device
    )
    if retains_grad:
        x.retain_grad()
    return x


def to_th_as(
    x: np.ndarray,
    as_: torch.Tensor,
    requires_grad: bool = False,
    retains_grad: bool = False,
) -> torch.Tensor:
    """

    Args:
        x (np.ndarray): _description_
        as_ (torch.Tensor): _description_
        requires_grad (bool, optional): _description_. Defaults to False.
        retains_grad (bool, optional): _description_. Defaults to False.

    Returns:
        torch.Tensor: _description_
    """

    x: torch.Tensor = torch.tensor(
        x, dtype=as_.dtype, requires_grad=requires_grad, device=as_.device
    )
    if retains_grad:
        x.retain_grad()
    return x


def coalesce(value, default_value) -> typing.Any:
    """
    Args:
        value: Value to coalesce if none
        default_value: Value to coalesce to

    Returns:
        Any: Either the default value or the value if not None
    """

    return value if value is not None else default_value


def expand_dim0(x: torch.Tensor, k: int, reshape: bool = False):
    """Expand an input to repeat k times"""
    y = x[None].repeat(k, *([1] * len(x.size())))  # .transpose(0, 1)
    if reshape:
        return y.view(y.shape[0] * y.shape[1], *y.shape[2:])
    return y


def flatten_dim0(x: torch.Tensor):
    """Flatten the population and batch dimensions of a population"""
    return x.view(x.shape[0] * x.shape[1], *x.shape[2:])


def deflatten_dim0(x: torch.Tensor, k: int) -> torch.Tensor:
    """Deflatten the population and batch dimensions of a population"""
    if x.dim() == 0:
        raise ValueError("Input dimension == 0")

    return x.view(k, -1, *x.shape[1:])


def freshen(x: torch.Tensor, requires_grad: bool = True, inplace: bool = False):
    if not isinstance(x, torch.Tensor):
        return x
    if inplace:
        x.detach_()
    else:
        x = x.detach()
    x = x.requires_grad_(requires_grad)
    x.retain_grad()
    return x


def set_parameters(parameters: torch.Tensor, net: nn.Module):
    vector_to_parameters(parameters, net.parameters())


def get_parameters(net: nn.Module):
    return parameters_to_vector(net.parameters())


def update(
    current: torch.Tensor, new_: torch.Tensor, lr: typing.Optional[float] = None
):
    assert lr is None or (0.0 <= lr <= 1.0)
    if lr is not None:
        new_ = (lr * new_) + (1 - lr) * (current)
    return new_


def update_param(
    current: torch.Tensor, new_: torch.Tensor, lr: typing.Optional[float] = None
):
    p = nn.parameter.Parameter(update(current, new_, lr).detach())
    return p


def to_zero_neg(x: torch.Tensor) -> torch.Tensor:
    """convert a 'signed' binary tensor to have zeros for negatives

    Args:
        x (torch.Tensor): Signed binary tensor

    Returns:
        torch.Tensor: The binary tensor with negatives as zero
    """

    return (x + 1) / 2


def to_signed_neg(x: torch.Tensor) -> torch.Tensor:
    """convert a 'zero' binary tensor to have negative ones for negatives

    Args:
        x (torch.Tensor): Binary tensor with zeros for negatives

    Returns:
        torch.Tensor: The signed binary tensor
    """
    return (x * 2) - 1


def add_prev(cur, prev=None):

    if cur is not None and prev is not None:
        return cur + prev
    if cur is not None:
        return cur

    return prev


def get_model_parameters(model: nn.Module) -> torch.Tensor:
    """Convenience function to retrieve the parameters of a model

    Args:
        model (nn.Module): _description_

    Returns:
        torch.Tensor: _description_
    """

    return nn_utils.parameters_to_vector(model.parameters())


def update_model_parameters(model: nn.Module, theta: torch.Tensor):
    """Convenience function to update the parameters of a model

    Args:
        model (nn.Module): Model to update parameters for
        theta (torch.Tensor): The new parameters for the model
    """

    nn_utils.vector_to_parameters(theta, model.parameters())


def set_model_grads(model: nn.Module, theta_grad: torch.Tensor):
    """Set the gradients of a module to the values specified by theta_grad

    Args:
        model (nn.Module): The module to update gradients for
        theta_grad (torch.Tensor): The gradient values to update with
    """
    start = 0
    for p in model.parameters():
        finish = start + p.numel()
        cur = theta_grad[start:finish].reshape(p.shape)
        p.grad = cur.detach()
        start = finish


def update_model_grads(model: nn.Module, theta_grad: torch.Tensor, to_add: bool=True):
    """Update the gradients of a module

    Args:
        model (nn.Module): The module to update gradients for
        theta_grad (torch.Tensor): The gradient values to update with
    """
    start = 0
    for p in model.parameters():
        finish = start + p.numel()
        cur = theta_grad[start:finish].reshape(p.shape)
        if p.grad is None:
            p.grad = cur.detach()
        elif to_add:
            p.grad.data += cur.detach()
        else:
            raise RuntimeError(f"To add is set to False but the gradient has already been set")
        start = finish


def get_model_grads(model: nn.Module) -> typing.Union[torch.Tensor, None]:
    """Get all of the gradients in a module

    Args:
        model (nn.Module): the module to get grads for

    Returns:
        torch.Tensor or None: the grads flattened. Returns None if any of the grads have not been set
    """

    grads = []
    for p in model.parameters():
        if p.grad is None:
            return None
        grads.append(p.grad.flatten())
    if len(grads) == 0:
        return None
    return torch.cat(grads)


def update_grads_from_model(model: nn.Module, theta_grad: torch.Tensor, to_add: bool=True):
    """Update the gradients of a module

    Args:
        model (nn.Module): The module to update gradients for
        theta_grad (torch.Tensor): The gradient values to update with
    """
    start = 0
    for p in model.parameters():
        finish = p.numel()
        cur = theta_grad[start:finish].reshape(p.shape)
        if p.grad is None:
            p.grad = cur.detach()
        elif to_add:
            p.grad.data += cur.detach()
        else:
            raise RuntimeError(f"To add is set to False but the gradient has already been set")


def calc_correlation_mae(x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
    """Calculate the mean absolute error in correlation

    Args:
        x1 (torch.Tensor)
        x2 (torch.Tensor)

    Returns:
        torch.Tensor: The correlation MAE
    """

    corr1 = torch.corrcoef(torch.flatten(x1, 1))
    corr2 = torch.corrcoef(torch.flatten(x2, 1))
    return torch.abs(corr1 - corr2).mean()


def calc_stride2d(x: torch.Tensor, stride):
    return (x.stride(0), x.stride(1), x.stride(2), stride[0], x.stride(2), stride[1])


def calc_size2d(x: torch.Tensor, stride, kernel_size):
    return (
        x.size(0),
        x.size(1),
        (x.size(2) - (kernel_size[0] - 1)) // stride[0],
        (x.size(3) - (kernel_size[1] - 1)) // stride[1],
        kernel_size[0],
        kernel_size[1],
    )


@singledispatch
def to_2dtuple(value: int) -> typing.Tuple[int, int]:
    return (value, value)


@to_2dtuple.register
def _(value: tuple) -> typing.Tuple[int, int]:
    return value


def binary_encoding(
    x: torch.LongTensor, n_size: int, bit_size: bool = False
) -> torch.Tensor:
    """Convert an integer tensor to a binary encoding

    Args:
        x (torch.LongTensor): The integer tensor
        n_size (int): The size of the encoding (e.g. number of bits if using bits or the max number)
        bit_size (bool, optional): Whether the size is described in terms of number of bits . Defaults to False.

    Returns:
        torch.Tensor: The binary encoding
    """

    if not bit_size:
        n_size = int(math.ceil(math.log2(n_size)))
    results = []
    for _ in range(n_size):
        results.append(x)
        x = x >> 1
    results = torch.stack(tuple(reversed(results))) & 1
    shape = list(range(results.dim()))
    shape = shape[1:] + shape[0:1]
    return results.permute(*shape)


# def chain(x, torch_modules: typing.Iterable[nn.Module]):

#     for module in torch_modules:
#         x = module.forward(x)
#     return x


# def create_dataloader(
#     x: torch.Tensor,
#     t: torch.Tensor,
#     batch_size: int = 64,
#     shuffle: bool = True,
#     get_indices: bool = False,
# ):
#     """Create data loader to loop over an input

#     Args:
#         x (torch.Tensor): _description_
#         t (torch.Tensor): _description_
#         batch_size (int, optional): _description_. Defaults to 64.
#         shuffle (bool, optional): _description_. Defaults to True.
#         get_indices (bool, optional): _description_. Defaults to False.

#     Returns:
#         _type_: _description_
#     """
#     if get_indices:
#         indices = torch.range(0, len(x))
#         dataset = torch_data.TensorDataset(x, t, indices)
#     else:
#         dataset = torch_data.TensorDataset(x, t)
#     return torch_data.DataLoader(dataset, batch_size, shuffle)

# def detach(x: typing.Union[typing.Iterable[torch.Tensor], torch.Tensor]):

#     if isinstance(x, list) or isinstance(x, tuple):
#         result = []
#         for x_i in x:
#             if isinstance(x_i, torch.Tensor):
#                 result.append(x_i.detach())
#             else:
#                 result.append(x_i)
#         return result

#     return x.detach() if isinstance(x, torch.Tensor) else x

# def to_float(x: typing.List[torch.Tensor]):
#     return list(map(lambda xi: xi.mean().item(), x))


# def get_indexed(
#     x: torch.Tensor, indices: typing.Optional[torch.LongTensor] = None
# ) -> torch.Tensor:

#     if indices is not None:
#         return x[indices]

#     return x


# def repeat_on_indices(
#     x: torch.Tensor, t: torch.Tensor, indices: torch.LongTensor, iterations: int
# ):
#     """Convenience function to loop over indieces

#     Args:
#         x (torch.Tensor): The input tensor
#         t (torch.Tensor): The target tensor
#         indices (torch.LongTensor): The indices to retrieve
#         iterations (int): Number of times to iterate

#     Yields:
#         torch.Tensor, torch.Tensor : The sampled input and target tensor
#     """

#     x = get_indexed(x, indices)
#     t = get_indexed(t, indices)

#     for i in range(iterations):

#         yield x, t
