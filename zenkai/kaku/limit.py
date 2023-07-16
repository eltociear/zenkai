from abc import ABC, abstractmethod

# 3rd party
import torch

# local
from .machine import Idx


class FeatureLimitGen(ABC):
    """Use to limit which connections are updated
    in an iteration
    """

    @abstractmethod
    def sample_limit(self) -> Idx:
        pass

    def __call__(self) -> Idx:
        """
        Returns:
            Idx: The index to select
        """
        return self.sample_limit()


class RandomFeatureIdxGen(FeatureLimitGen):
    """
    """

    def __init__(self, n_features: int, choose_count: int):
        """initializer

        Args:
            n_features (int): The number of features to select from
            choose_count (int): The number of features to choose
        """

        assert choose_count <= n_features
        self._n_features = n_features
        self._choose_count = choose_count

    @property
    def n_features(self) -> int:
        """
        Returns:
            int: The number of features to select from
        """
        return self._n_features

    @n_features.setter
    def n_features(self, n_features: int):
        """
        Args:
            n_features (int): The number of features to select from

        Raises:
            ValueError: If the number of features to select from is less
            than the number to choose from
        """
        if n_features < self._choose_count:
            raise ValueError(
                "n_features must be greater than "
                f"the number of features to choose from, {self._choose_count}")
        self._n_features = n_features

    @property
    def choose_count(self) -> int:
        """
        Returns:
            int: The number of features to choose
        """
        return self._choose_count

    @choose_count.setter
    def choose_count(self, choose_count: int):
        """_summary_

        Args:
            choose_count (int): _description_

        Raises:
            ValueError: _description_
        """
        if choose_count > self._n_features:
            raise ValueError(
                "The number of features to choose  "
                f"must be greater than the number to select from, {self._n_features}"
            )
        self._choose_count = choose_count

    def sample_limit(self) -> Idx:
        """
        Returns:
            Idx: Generate a sample limit
        """
        return Idx(torch.randperm(self.n_features)[: self.choose_count], 1)
