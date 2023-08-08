"""
Modules to wrap inputs ond outputs for the network
"""

# 1st party
import typing

# 3rd party
import torch
import numpy as np
from torch import nn

# local
from .. import utils as base_utils


class IO(object):
    """Handles IO into and out of learning machines
    to give a consistent system to handle it
    """

    def __init__(self, *x, detach: bool = False, names: typing.List[str] = None):
        """initializer

        Args:
            detach (bool, optional): The values making up the IO. Defaults to False.
            names (typing.List[str], optional): The name of each value. Defaults to None.
        """
        super().__init__()

        self._x = []
        self._freshened = False
        self._singular = len(x) == 1
        for x_i in x:
            if isinstance(x_i, torch.Tensor) and detach:
                x_i = x_i.detach()

            self._x.append(x_i)
        
        # TODO: Use this
        self._names = enumerate(dict(names or []))

    def freshen(self, inplace: bool = False) -> 'IO':
        """Set the values of the IO

        Args:
            inplace (bool, optional): Whether to freshen 'in place' or not. Defaults to False.

        Returns:
            IO: self
        """
        if self._freshened:
            return False

        self._x = [base_utils.freshen(x_i, inplace=inplace) for x_i in self._x]
        self._freshened = True
        return self

    def items(self) -> typing.Dict:
        return dict(enumerate(self._x))

    def tolist(self) -> typing.List:
        """Convert to a list

        Returns:
            list: The values in the IO
        """
        return list(self._x)
    
    def totuple(self) -> typing.Tuple:
        """Convert to a list

        Returns:
            typing.Tuple: the values making up the io as a tuple
        """
        return tuple(self._x)

    def __getitem__(self, idx: int):
        """Retrieve item from the IO

        Args:
            idx (int): The index to retrieve for

        Returns:
            the value at the index
        """
        return self._x[idx]

    def to(self, device) -> "IO":
        """Change the device of all tensors in the IO

        Args:
            device: The device to change the convert to

        Returns:
            IO: self
        """
        if device is None:
            return self

        self._x = [
            x_i.to(device) if isinstance(x_i, torch.Tensor) else x_i for x_i in self._x
        ]
        if self._freshened:
            self._freshened = False
            self.freshen(self._x)
        return self

    @property
    def names(self) -> typing.List[str]:
        """
        Returns:
            typing.List[str]: The names of all of the fields
        """
        return [*self._names]

    def __len__(self) -> int:
        """
        Returns:
            int: The number of fields in the IO
        """
        return len(self._x)

    def __iter__(self) -> typing.Iterator:
        """
        Returns:
            typing.Iterator: Iterator of all of the elements
        """
        return iter(self._x)

    def clone(self, detach: bool = True) -> "IO":
        """create a copy of the of all of the tensors

        Args:
            detach (bool, optional): Whether to clone the gradients. Defaults to True.

        Returns:
            IO: The cloned IO
        """
        x = [torch.clone(x_i) for x_i in self._x]
        result = IO(*x, detach=detach, names=self._names)
        if not detach:
            result._freshened = self._freshened
        return result

    def detach(self) -> "IO":
        """Create a new IO detaching all of the tensors

        Returns:
            IO: The new IO
        """

        return IO(*self._x, detach=True, names=self._names)

    def release(self) -> "IO":
        return self.clone()

    def out(self, release: bool = True) -> "IO":
        if release:
            return self.release()
        return self

    def is_empty(self) -> bool:
        return len(self) == 0
    
    def sub(self, idx, detach: bool=False) -> 'IO':

        if isinstance(idx, int):
            return IO(self._x[idx], detach=detach)

        return IO(*self._x[idx], detach=detach)
    
    def range(self, low: int=None, high: int=None, detach: bool=False) -> 'IO':

        return IO(*self._x[low:high], detach=detach)

    @classmethod
    def cat(cls, ios: typing.Iterable['IO']) -> 'IO':
        """Concatenate

        Args:
            ios (IO): the ios to concatenate

        Returns:
            IO: the concatenated IO
        """
        results = []
        for elements in zip(*ios):
            if isinstance(elements[0], torch.Tensor):
                results.append(torch.cat(elements))
            elif isinstance(elements[0], np.ndarray):
                results.append(np.concatenate(elements))
            else:
                # TODO: revisit if i want to do it like this
                results.append(elements)
        return IO(*results)


class Idx(object):
    """Class used to index a tensor
    """

    def __init__(self, idx=None, dim: int = 0):
        """initializer

        Set an index on the IO to

        usage: Use when the connection should retrieve a subset of the values
        in the IO

        Args:
            idx (optional): The values to index by. Defaults to None.
        """
        if not isinstance(idx, torch.LongTensor) and idx is not None:
            if isinstance(idx, torch.Tensor):
                idx = idx.long()
            else:
                idx = torch.LongTensor(idx)
        self.dim = dim
        self.idx = idx

    def idx_th(
        self, *x: torch.Tensor
    ) -> typing.Union[typing.Tuple[torch.Tensor], torch.Tensor]:
        """Index a tensor

        Returns:
            typing.Union[typing.Tuple[torch.Tensor], torch.Tensor]: _description_
        """
        if self.idx is not None:
            x = [x_i.index_select(self.dim, self.idx.detach()) for x_i in x]

        return x

    def tolist(self) -> typing.Union[None, typing.List[int]]:
        """
        Returns:
            typing.Union[None, typing.List[int]]: The index converted to a list. 
            None if the idx is None
        """
        if self.idx is None:
            return None
        return self.idx.tolist()

    def idx_list(self) -> typing.List[int]:
        """

        Returns:
            typing.List[int]: _description_
        """
        result = []
        for i in self.idx:
            result.append(self.idx[i.item()])
        return result
    
    def detach(self) -> 'Idx':
        """Remove the grad function from the index

        Returns:
            Idx: The detached index
        """
        if self.idx is None:
            return Idx(dim=self.dim)
        return Idx(self.idx.detach(), dim=self.dim)

    def update(self, source: IO, destination: IO, idx_both: bool=False):
        """Update an io in place with the index

        Args:
            source (IO): The io to update with
            destination (IO): The io to update
            idx_both (bool): Whether only the destination is indexed or both are indexed
        """
        for source_i, destination_i in zip(source, destination):
            if destination_i.requires_grad:
                requires_grad = True
                destination_i.detach_().requires_grad_(False)
            else:
                requires_grad = False
            if self.idx is not None:
                if idx_both:
                    source_i = source_i[self.idx]
                destination_i.data[self.idx] = source_i
            else:
                destination_i.data = source_i
            if requires_grad:
                destination_i.requires_grad_(True).retain_grad()

    def update_th(self, source: torch.Tensor, destination: torch.Tensor):
        """Update a torch.Tensor with the idx

        Args:
            source (torch.Tensor): The tensor to update wtih
            destination (torch.Tensor): The tensor to update
        """
        if self.idx is not None:
            destination[self.idx] = source
        else:
            destination[:] = source

    def sub(self, idx: "Idx") -> "Idx":
        """Get a sub index of the index
        Args:
            idx (Idx): The index to get the sub index with

        Returns:
            Idx: This Idx sub-indexed
        """
        if not isinstance(idx, Idx):
            idx = Idx(idx)

        if idx.idx is None:
            return self
        elif self.idx is None:
            return idx

        return Idx(self.idx[idx.idx])

    def __len__(self) -> int:
        """
        Returns:
            int: The number of elements in the index
        """
        return len(self.idx)

    def to(self, device) -> 'Idx':
        """Change the device of the index if specified

        Args:
            device: The device to change to

        Returns:
            Idx: the resulting index
        """
        if self.idx is not None:
            self.idx = self.idx.to(device)
        return self

    def __call__(self, x: IO, detach: bool = False) -> IO:

        selected = self.idx_th(*x)

        result = IO(*selected, detach=detach, names=x.names)
        if x._freshened and not detach:
            result._freshened = True
        return result


def idx_io(io: IO, idx: Idx = None, release: bool = False) -> IO:
    """Use Idx on an IO. It is a convenience function for when you don't know if idx is 
    specified

    Args:
        io (IO): The IO to index
        idx (Idx, optional): The Idx to use. If not specified, will just return x . Defaults to None.
        release (bool, optional): Whether to release the result. Defaults to False.

    Returns:
        IO: The resulting io
    """

    if idx is not None:
        io = idx(io)

    return io.out(release)


def idx_th(x: torch.Tensor, idx: Idx = None, detach: bool = False) -> torch.Tensor:
    """Use the index on a tensor. It is a convenience function for when you don't know if idx is 
    specified

    Args:
        x (torch.Tensor): Tensor to calculate the index for
        idx (Idx, optional): The Idx to use. If not specified, will just return x . Defaults to None.
        detach (bool, optional): Whether to detach the result. Defaults to False.

    Returns:
        torch.Tensor: The resulting tensor
    """

    if idx is not None:
        x = idx.idx_th(x)

    if detach:
        x = x.detach()
    return x


# TODO: DEBUG. This is not working for some reason
def update_io(source: IO, destination: IO, idx: Idx = None, detach: bool=True, idx_both: bool=False) -> IO:
    """Update the IO in place

    Args:
        source (IO): The io to update with
        destination (IO): The io to update
        idx (Idx, optional): The index for the source. Defaults to None.

    Returns:
        IO: the updated IO
    """

    if idx is None:
        idx = Idx()
    idx.update(source, destination, idx_both)
    if detach:
        return destination.detach()
    return destination


def update_tensor(
    source: torch.Tensor, destination: torch.Tensor, idx: Idx = None, detach: bool=True
) -> torch.Tensor:
    """Update the tensor in place

    Args:
        source (torch.Tensor): The tensor to update with
        destination (torch.Tensor): The tensor to update
        idx (Idx, optional): The index for the source. Defaults to None.

    Returns:
        torch.Tensor: The updated tensor
    """
    if idx is None:
        idx = Idx()
    idx.update_th(source, destination)
    if detach:
        return destination.detach()
    return destination


class ToIO(nn.Module):

    def __init__(self, detach: bool=False):
        super().__init__()
        self.detach = detach

    def forward(self, *x: torch.Tensor, detach_override: bool=None) -> IO:
        if detach_override is not None:
            detach = detach_override
        else:
            detach = self.detach
        return IO(*x, detach=detach)


class FromIO(nn.Module):

    def __init__(self, detach: bool=False):
        super().__init__()
        self.detach = detach

    def forward(self, io: IO) -> IO:

        if self.detach:
            io = io.detach()
    
        if len(io) == 1:
            return io[0]
        return io.totuple()
