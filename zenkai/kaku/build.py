from abc import ABC, abstractmethod
import typing

from .machine import LearningMachine


class BuilderFunctor(ABC):
    """Base class for functors used in building a learning machine
    """

    @abstractmethod
    def __call__(self, **kwargs):
        pass

    @abstractmethod
    def clone(self) -> 'BuilderFunctor':
        pass

    @abstractmethod
    def vars(self) -> typing.List['Var']:
        pass


class Var(BuilderFunctor):

    def __init__(self, name: str, dtype: typing.Type=None):
        """

        Args:
            name (str): 
            dtype (typing.Type, optional): . Defaults to None.
        """
        self._name = name
        self._dtype = dtype

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def dtype(self) -> typing.Type:
        return self._dtype

    def __call__(self, **kwargs):

        try:
            return kwargs[self._name]
        except KeyError:
            raise KeyError(f'Variable {self._name} not found in kwargs passed in.')

    def clone(self) -> 'Var':
        return Var(self._name, self._dtype)

    def vars(self) -> typing.List['Var']:
            
        return [self]


class Factory(BuilderFunctor):

    def __init__(self, factory, *args, **kwargs):
        
        self._factory = factory
        self._args = BuilderArgs(args=args, kwargs=kwargs)

    def __call__(self, **kwargs):
        
        args, kwargs = self._args(**kwargs)
        return self._factory(*args, **kwargs)

    def vars(self) -> typing.List[Var]:            
        return self._args.vars()

    def clone(self) -> 'Factory':
        factory = Factory(self._factory)
        factory._args = self._args.clone()
        return factory


class BuilderArgs(BuilderFunctor):
    
    def __init__(self, args=None, kwargs=None):
        """

        Args:
            args (_type_, optional): _description_. Defaults to None.
            kwargs (_type_, optional): _description_. Defaults to None.
        """
        
        self._args = args or []
        self._kwargs = kwargs or {}

    def __call__(self, **kwargs) -> typing.Any:

        result_args = []
        result_kwargs = {}
        for arg in self._args:
            if isinstance(arg, BuilderFunctor):
                result_args.append(arg(**kwargs))
            else:
                result_args.append(arg)
        for key, arg in self._kwargs.items():
            if isinstance(arg, BuilderFunctor):
                result_kwargs[key] = arg(**kwargs)
            else:
                result_kwargs[key] = arg
        return result_args, result_kwargs

    def update(self, key, value):

        if isinstance(key, int):
            self._args[key] = value
        else:
            self._kwargs[key] = value

    def vars(self) -> typing.List[Var]:

        vars = []

        for arg in self._args:
            if isinstance(arg, BuilderFunctor):
                vars.extend(arg.vars())

        for arg in self._kwargs.values():
            if isinstance(arg, BuilderFunctor):
                vars.extend(arg.vars())            

        return vars

    def clone(self):

        result_args = []
        result_kwargs = {}
        for arg in self._args:
            if isinstance(arg, BuilderFunctor):
                result_args.append(arg.clone())
            else:
                result_args.append(arg)
        for key, arg in self._kwargs.items():
            if isinstance(arg, BuilderFunctor):
                result_kwargs[key] = arg.clone()
            else:
                result_kwargs[key] = arg
        return BuilderArgs(
            result_args, result_kwargs
        )


class Builder(BuilderFunctor):

    class Updater(object):

        def __init__(self, builder: 'Builder', name: str):
            self.builder = builder
            self.name = name

        def __call__(self, value):

            clone = self.builder.clone()
            clone[self.name] = value
            return clone

    def __init__(self, learning_machine_cls: typing.Type[LearningMachine], arg_names: typing.List[str], **kwargs):
        """
        Args:
            learning_machine_cls (typing.Type[LearningMachine]): _description_
            arg_names (typing.List[str]): _description_

        Raises:
            ValueError: _description_
        """
        

        super().__init__()
        super().__setattr__('_learning_machine_cls', learning_machine_cls)
        super().__setattr__('_arg_names', arg_names)
        difference = set(kwargs.keys()).difference(arg_names)
        if len(difference) != 0:
            raise ValueError(f'Keys in kwargs {list(kwargs.keys())} must be a subset of arg_names {arg_names}')
        super().__setattr__('_builder_kwargs', BuilderArgs(kwargs=kwargs))

    def __setitem__(self, name: str, value: typing.Any) -> None:
        self._builder_kwargs.update(name, value)
    
    def __setattr__(self, name: str, value: typing.Any) -> None:
        """Update or 

        Args:
            name (str): _description_
            value (typing.Any): _description_
        """
        if name in self._arg_names:
            self[name] = value
        else:
            object.__setattr__(self, name, value)

    def __getitem__(self, name: str) -> None:
        return self.Updater(self, name)

    def __getattr__(self, name: str) -> None:
        
        if name in self._arg_names:
            
            return self[name]
            # self._builder_kwargs.update(name, value)
        return super().__getattr__(name)
    
    def get(self, name: str):

        if name in self._arg_names:
            return self._builder_kwargs.get(name)
        return super().__getattr__(name)

    def clone(self):
        kwargs = self._builder_kwargs.clone()
        builder = Builder(
            self._learning_machine_cls, [*self._arg_names], 
        )
        builder._builder_kwargs = kwargs
        return builder

    def vars(self) -> typing.List[Var]:
        return self._builder_kwargs.vars()

    def __call__(self, **kwargs) -> LearningMachine:
        
        args, kwargs = self._builder_kwargs(**kwargs)
        return self._learning_machine_cls(
            *args, **kwargs
        )