import typing
from dataclasses import dataclass

import  torch
from torch import nn

from ..kaku import (
    State, IO, LearningMachine, Assessment, 
    acc_dep, step_dep, 
    AccLearningMachine
)
from abc import abstractmethod, ABC


class Network(LearningMachine):

    def __init__(self, container_prototype: 'Container'):

        super().__init__()
        self.container_prototype = container_prototype

    def spawn_container(self, x: IO, state: State) -> 'Container':
        container = self.container_prototype.spawn()
        state[(self, x), 'container'] = container
        return container


class ZenNode(AccLearningMachine):

    def __init__(self, learning_machine: typing.Union[LearningMachine, AccLearningMachine], step_priority: bool=False):

        super().__init__()
        self._learning_machine = learning_machine
        self.step_priority = step_priority
        self._accumulate = isinstance(self._learning_machine, AccLearningMachine)
    
    @property
    def accumulate(self) -> bool:
        return self._accumulate

    def forward(self, x: IO, state: State, release: bool = True, container: 'Container'=None) -> IO:
        
        y = self._learning_machine(x, state, release)
        if container is not None:
            container.add(Connection(x, y, self))
        return y

    def assess_y(self, y: IO, t: IO, reduction_override: str = None) -> Assessment:
        return self._learning_machine.assess_y(y, t, reduction_override)

    def step(self, x: IO, t: IO, state: State):
        self._learning_machine.step(x, t, state)
    
    def step_x(self, x: IO, t: IO, state: State) -> IO:
        
        return self._learning_machine.step_x(x, t, state)  
    
    def accumulate(self, x: IO, t: IO, state: State):

        if self._accumulate:
            self._learning_machine.accumulate(x, t, state)

    def __repr__(self):
        return f'Node({self._learning_machine})'


class Container(ABC):

    @abstractmethod
    def add(self, connection: 'Connection'):
        pass

    @abstractmethod
    def set_out(self, y: IO):
        pass

    @abstractmethod
    def set_out_target(self, t: IO):
        pass

    @abstractmethod
    def get_target(self, y: IO) -> IO:
        pass

    @abstractmethod
    def set_t(self, *key_targs):
        pass

    @abstractmethod
    def detach_t(self, *keys):
        pass

    @abstractmethod
    def reverse(self) -> typing.Iterator[typing.Tuple[IO, IO, ZenNode, IO]]:
        pass

    @abstractmethod
    def contains_y(self, y: IO) -> bool:
        pass

    @abstractmethod
    def set_x_prime(self, y: IO, x_prime: IO):
        pass

    def spawn(self) -> 'Container':
        return self.__class__()

    @abstractmethod
    def first(self) -> typing.Iterator[typing.Tuple[IO, IO, ZenNode, IO]]:
        pass


@dataclass
class Connection:

    # can be more than one input incoming (use with cat)
    x: IO
    y: IO
    # node can be defined by a string
    node: typing.Union[ZenNode, str]
    multi: bool=False
    t: IO=None
    x_prime: IO=None

    def vals(self) -> typing.Tuple[IO, IO, ZenNode, IO]:
        return self.x, self.y, self.node, self.t


class Pipeline(Container):

    def __init__(self):
        
        super().__init__()
        self._nodes: typing.List[Connection] = []
        self._indices: typing.Dict[IO, int] = {}
        self._out = None
        self._out_set = False
        self._t = None
        self._ts: typing.Dict[IO, IO] = {}
    
    def add(self, connection: Connection):
        
        if len(self._nodes) > 0 and connection.x != self._nodes[-1].y:
            raise ValueError(f'The connections in a pipeline must be added in sequence')
        self._nodes.append(connection)
        self._indices[connection.y] = len(self._nodes) - 1
        if not self._out_set:
            self._out = connection.y

    def set_out(self, y: IO):
        
        if y not in self._indices:
            raise KeyError(f'IO y has not been added to the Pipeline')
        self._out = self._indices[Connection.y]
        self._out_set = True

    def set_out_target(self, t: IO):
        
        self._t = t
    
    def get_target(self, y: IO) -> IO:

        if y in self._ts:
            t = self._ts[y]
            if t == "t":
                return self._t
            return self._nodes[self._indices[t]].x_prime
        if y == self._out:
            return self._t
        if y == self._nodes[-1].y and self._out_set is False:
            return self._t
        index = self._indices[y] + 1
        if index < len(self._nodes):
            return self._nodes[self._indices[y] + 1].x_prime
        return None
    
    def set_t(self, *key_targs):

        for x, t in key_targs:
            if t != "t" and self._indices[t] <= self._indices[x]:
                raise ValueError(f"Cannot set t to a previous value in the pipeline")

            self._ts[x] = t

    def detach_t(self, *keys):

        for x in keys:
            del self._ts[x]

    def set_x_prime(self, y: IO, x_prime: IO):
        
        connection = self._nodes[self._indices[y]]
        connection.x_prime = x_prime

    def reverse(self) -> typing.Iterator[typing.Tuple[IO, IO, ZenNode, IO]]:
        
        if self._out_set:
            nodes = self._nodes[:self._out+1]
        else:
            nodes = self._nodes

        for connection in reversed(nodes):
            connection.t = self.get_target(connection.y)
            yield connection.vals()
    
    def contains_y(self, y: IO) -> bool:

        return y in self._indices
    
    def first(self) -> typing.Tuple[IO, IO, ZenNode, IO]:

        return self._nodes[0].vals()


class NetworkLearner(Network):

    def step(self, x: IO, t: IO, state: State):

        container: Container = state[(self, x), 'container']
        container.set_out_target(t)
        for x, y, node, t in container.reverse():
            if node.step_priority:
                
                node.step(x, t, state)
                x_prime = node.step_x(x, t, state)
            else: 
                x_prime = node.step_x(x, t, state)
                node.step(x, t, state)
            container.set_x_prime(y, x_prime)

        state[(self, x), 'stepped'] = True
        return x_prime
    
    @step_dep('stepped', False, True)
    def step_x(self, x: IO, t: IO, state: State) -> IO:

        x, y, node, t = state[(self, x), 'container'].first()
        return node.step_x(x, t, state)

    @abstractmethod
    def forward(self, x: IO, state: State, release: bool = True) -> IO:
        raise NotImplementedError


class AccNetworkLearner(Network, AccLearningMachine):

    def accumulate(self, x: IO, t: IO, state: State):
        
        container: Container = state[(self, x), 'container']
        container.set_out_target(t)
        for x, y, node, t in container.reverse():
            node.accumulate(x, t, state)
            x_prime = node.step_x(x, t, state)
            container.set_x_prime(y, x_prime)
            # if container.contains_y(x):
            #    container.target(x, x_prime)
        
        state[self, 'accumulated'] = True
    
    @acc_dep('accumulated', False)
    def step(self, x: IO, t: IO, state: State) -> IO:

        for x, _, node, t  in state[(self, x), 'container'].reverse():
            node.step(x, t, state)

    @acc_dep('accumulated', False)
    def step_x(self, x: IO, t: IO, state: State) -> IO:

        x, _, node, t = state[(self, x), 'container'].first()
        return node.step_x(x, t, state)

    def add_node(self, learning_machine: LearningMachine) -> 'ZenNode':
        return ZenNode(self, learning_machine, priority_step=False)

    @abstractmethod
    def forward(self, x: IO, state: State, release: bool = True) -> IO:
        raise NotImplementedError


# class Graph(Container):

#     def __init__(self):
#         super().__init__()

#         self._conns: typing.Dict[IO, Connection] = {}

#         self._out = None
#         self._out_set = False
#         self._cur = None
#         self._out_map: typing.Dict[IO, typing.List[IO]] = {}
#         self._t_fixed: typing.Dict[IO, bool] = {}
#         self._t = None
#         self._targets = {}
    
#     def add(self, connection: Connection):
        
#         self._targets = {}
#         self._conns[connection.y] = connection

#         x = connection.x
        
#         if x in self._conns and self._t_fixed[connection.x] is False:
#             self._out_map[connection.x].append(connection.y)
#         self._cur = connection.y
#         self._out_map[connection.y] = []
#         self._t_fixed[connection.y] = False
#         if not self._out_set:
#             self._out = connection.y

#     def cat(self, xs: typing.List[IO]) -> IO:

#         y = IO.join(xs)
        
#         self._targets = {}
#         # manage the dependencies of the input on other nodes
#         connection = Connection(
#             IO(*xs), y,  
#             node="merge", multi=True
#         )
#         self._conns[connection.y] = connection
        
#         for x in xs:
#             if self._t_fixed[x] is False:

#                 self._out_map[x].append(connection.y)

#         self._out_map[y] = []
#         self._cur = y
        
#         self._t_fixed[connection.y] = False
#         if not self._out_set:
#             self._out = connection.y
#         return y

#     def set_out(self, y: IO):
        
#         if y not in self._conns:
#             raise KeyError(f'IO y has not been added to the Graph')
#         self._out = y
#         self._out_set = True

#     def set_out_target(self, t: IO):
#         # Add error checking
#         self._t = t

#     def get_target(self, y: IO) -> IO:

#         if y in self._targets:
#             return self._targets[y]

#         out_y = self._out_map.get(y)
#         if y == self._out:
#             target = self._t
#         elif isinstance(out_y, typing.List):
            
#             x_primes = []
#             for out_y_i in out_y:
#                 x_prime = self._conns[out_y_i].get_x_prime(y)
#                 if x_prime is None:
#                     return None
#                 x_primes.append(x_prime)
#             target = IO.agg(x_primes, sum)
#         else: target = self._conns[out_y].get_x_prime(y)
#         self._targets[y] = target
#         return target

#     def set_x_prime(self, y: IO, x_prime: IO):
        
#         self._conns[y].x_prime = x_prime

#     def _target_available(self, y: IO):

#         if y in self._targets:
#             return True
#         if y == self._out:
#             return True
#         t = self._out_map[y]
#         if isinstance(t, typing.List):
#             for t in self._out_map:
#                 if self._conns[t].get_x_prime(y) is None:
#                     return False
#             return True
#         if t == 't':
#             return True
#         return self._conns[t].get_x_prime(y) is not None
    
#     def set_t(self, **key_targs):
#         pass

#     def detach_t(self, *keys):
#         pass

#     def _traversed_dependencies(self, conn: Connection, traversed: typing.Set):

#         for y in self._out_map[conn.y]:
#             if self._conns[y].node not in traversed:
#                 return False
#         return True

#     def _reverse_helper(self, cur: IO, cur_t: IO=None, traversed: typing.Set[ZenNode]=None) -> typing.Iterator[typing.Tuple[IO, IO, IO, ZenNode]]:
        
#         traversed = traversed or set()
#         conn = self._conns[cur]

#         if not self._traversed_dependencies(conn, traversed):
#             return
        
#         traversed.add(self._conns[cur].node)
#         if conn.node == "merge":
#             start = 0
#             upto = None
#             in_ys = []
#             in_ts = []
#             for x in conn.x:
#                 upto = len(x) + start

#                 if x not in self._conns:
#                     next
#                 in_y = x
#                 in_t = IO(*cur_t[start: upto]) if cur_t is not None else None
#                 in_ys.append(in_y)
#                 in_ts.append(in_t)
#             conn.x_prime = IO(*in_ts)
#             for in_y, in_t in zip(in_ys, in_ts):
#                 for vals in self._reverse_helper(in_y, in_t, traversed):
#                     yield vals
#                 start = upto 
#         else:
#             yield conn.x, conn.y, conn.node, cur_t
#             if conn.x not in self._conns:
#                 return
#             in_y = self._conns[conn.x].y
#             in_t = self.get_target(in_y)
#             for vals in self._reverse_helper(in_y, in_t, traversed):
#                 yield vals

#     def reverse(self) -> typing.Iterator[typing.Tuple[IO, IO, IO, ZenNode]]:
        
#         cur = self._out
#         cur_t = self.get_target(cur)
#         for x, y, node, t in self._reverse_helper(cur, cur_t):
#             yield x, y, node, t

#     def contains_y(self, y: IO) -> bool:

#         return y in self._conns

#     def first(self) -> typing.Tuple[IO, IO, ZenNode, IO]:

#         return self._conns[0].vals()
