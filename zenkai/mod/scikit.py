# 1st party
import typing
from copy import deepcopy
import numpy as np
import torch.nn as nn
import torch.nn.functional

# 3rd party
from sklearn.base import BaseEstimator
from sklearn.multioutput import MultiOutputClassifier, MultiOutputRegressor
from torch.nn.functional import one_hot
import sklearn.base

# local
from .. import utils
from .classify import Argmax, Sign


class ScikitEstimator(nn.Module):
    """Adapts an Scikit Estimator in an nn.Module"""

    def __init__(
        self,
        sklearn_estimator,
        in_features: int = 1,
        out_features: int = 1,
        partial_fit: bool = True,
        use_predict: bool = True,
        backup: nn.Module = None,
    ):
        """initializer

        Args:
            sklearn_machine (_type_):
            multitarget (bool, optional): Whether or not the sklearn estimator is multitarget. Defaults to False.
            n_outputs (int, optional): The number of estimates . Defaults to 1.
            regressor (bool, optional): Whether the estimator is a regressor. Defaults to True.
            partial_fit (bool, optional): Whether to use partial fit. Defaults to True.
            use_predict (bool, optional): Whether to predict the output or use 'transform'. Defaults to True.
        """
        super().__init__()
        self._sklearn_estimator = sklearn_estimator
        if partial_fit and not hasattr(self._sklearn_estimator, "partial_fit"):
            raise RuntimeError(
                "Using partial fit but estimator does not have partial fit method available"
            )

        if not partial_fit and not hasattr(self._sklearn_estimator, "fit"):
            raise RuntimeError(
                "Using fit but estimator does not have fit method available"
            )

        self._output = self._predict if use_predict else self._transform
        self.fit = self._partial_fit if partial_fit else self._full_fit
        self._fitted = False
        self._use_partial_fit = partial_fit
        self._use_predict = use_predict
        self._in_features = in_features
        self._out_features = out_features
        self.backup = backup or nn.Linear(in_features, out_features)
        self._is_multioutput = isinstance(
            sklearn_estimator, MultiOutputClassifier
        ) or isinstance(sklearn_estimator, MultiOutputRegressor)

    def _predict(self, x):
        return self._sklearn_estimator.predict(x)

    def _transform(self, x):
        return self._sklearn_estimator.transform(x)

    def is_multioutput(self) -> bool:
        return self._is_multioutput

    @property
    def estimator(self) -> BaseEstimator:
        """
        Returns:
            BaseEstimator: the estimator wrapped by the SciKitEstimator
        """
        return self._sklearn_estimator

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Send the tensor through the estimator

        Args:
            x (torch.Tensor): the input

        Returns:
            torch.Tensor: the result of the scikit esimator converted to a Tensor
        """

        if not self.fitted:
            y = self.backup(x)
            return y
        x_np = utils.to_np(x)
        y = utils.to_th_as(self._sklearn_estimator.predict(x_np), x)

        return y

    def _prepare(
        self, y: np.ndarray, limit: typing.List[int]
    ) -> typing.List[BaseEstimator]:
        """

        Args:
            y (np.ndarray): _description_
            limit (typing.List[int]): _description_

        Returns:
            typing.List[BaseEstimator]: _description_
        """
        if limit is None:
            return y, None

        if not (
            isinstance(self._sklearn_estimator, MultiOutputClassifier)
            or isinstance(self._sklearn_estimator, MultiOutputRegressor)
        ):
            return y, None
            # raise ValueError(f"Cannot set limit if not using multioutput regressor or classifier")
        cur_estimators = self._sklearn_estimator.estimators_
        fit_estimators = [self._sklearn_estimator.estimators_[i] for i in limit]
        self._sklearn_estimator.estimators_ = fit_estimators
        return y[:, limit], cur_estimators

    def _replace_estimators(
        self, cur_estimators: typing.List[BaseEstimator], limit: typing.List[int]
    ):

        if limit is None or cur_estimators is None:
            return
        fit_estimators = self._sklearn_estimator.estimators_
        self._sklearn_estimator.estimators_ = cur_estimators
        for i, estimator in zip(limit, fit_estimators):
            self._sklearn_estimator.estimators_[i] = estimator

    def _partial_fit(
        self, X: torch.Tensor, y: torch.Tensor, limit: typing.List[int] = None
    ):
        if limit is not None and not self.fitted:
            raise RuntimeError("Must fit model before setting a limit")
        X = utils.to_np(X)
        y = utils.to_np(y)

        y, cur_estimators = self._prepare(y, limit)
        if limit is not None and len(limit) == 1:
            self._sklearn_estimator.partial_fit(X, y)
        else:
            self._sklearn_estimator.estimators_[0].partial_fit(X, y.flatten())

        self._replace_estimators(cur_estimators, limit)
        self.fitted = True

    def fit(self, X: torch.Tensor, y: torch.Tensor, limit: typing.List[int] = None):
        pass

    def _full_fit(
        self, X: torch.Tensor, y: torch.Tensor, limit: typing.List[int] = None
    ):
        """Runs a fit operation

        Args:
            X (torch.Tensor): the input
            y (torch.Tensor): the target tensor
            limit (typing.List[int], optional): the index of the limit. Defaults to None.

        Raises:
            RuntimeError: If the model has not been fit yet and a "limit" was set
        """
        if limit is not None and not self.fitted:
            raise RuntimeError("Must fit model before setting a limit")
        X = utils.to_np(X)
        y = utils.to_np(y)
        y, cur_estimators = self._prepare(y, limit)

        if limit is not None and len(limit) == 1:
            self._sklearn_estimator.estimators_[0].fit(X, y.flatten())
        else:
            self._sklearn_estimator.fit(X, y)
        self._replace_estimators(cur_estimators, limit)
        self._fitted = True

    @property
    def fitted(self) -> bool:
        """
        Returns:
            bool: If the model has been fitted already
        """
        return self._fitted

    def clone(self) -> 'ScikitEstimator':
        return ScikitEstimator(
            sklearn.base.clone(self.estimator), self._in_features,
            self._out_features,
            self._use_partial_fit,
            self._use_predict,
            self.backup
        )


class ScikitRegressor(ScikitEstimator):
    """Adapter for Scikit-Learn regressors"""

    def __init__(
        self,
        sklearn_estimator,
        in_features: int = 1,
        out_features: int = 1,
        multi: bool = False,
        partial_fit: bool = True,
        use_predict: bool = True,
    ):
        """initializer

        Args:
            sklearn_machine (_type_):
            multitarget (bool, optional): Whether or not the sklearn estimator is multitarget. Defaults to False.
            n_outputs (int, optional): The number of estimates . Defaults to 1.
            regressor (bool, optional): Whether the estimator is a regressor. Defaults to True.
            partial_fit (bool, optional): Whether to use partial fit. Defaults to True.
            preprocessor (nn.Module, optional): . Defaults to None.
            postprocessor (nn.Module, optional): . Defaults to None.
            use_predict (bool, optional): Whether to predict the output or use 'transform'. Defaults to True.
        """
        self._base = sklearn_estimator
        if multi:
            sklearn_estimator = MultiOutputRegressor(sklearn_estimator)
        backup = nn.Linear(in_features, out_features)
        self._multi = multi
        super().__init__(
            sklearn_estimator,
            in_features,
            out_features,
            partial_fit,
            use_predict,
            backup,
        )


    def clone(self) -> 'ScikitRegressor':
        return ScikitRegressor(
            sklearn.base.clone(self._base), self._in_features,
            self._out_features, self._multi, self._use_partial_fit,
            self._use_predict
        )


class ScikitMulticlass(ScikitEstimator):
    """Adapter for a multiclass estimator"""

    def __init__(
        self,
        sklearn_estimator,
        in_features: int,
        n_classes: int,
        multi: bool = False,
        out_features: int = 1,
        partial_fit: bool = True,
        use_predict: bool = True,
        output_one_hot: bool = True,
    ):
        """initializer

        Args:
            sklearn_machine : The estimator to adapt
            in_features (int): The number of features into the estimator
            n_classes (int): The number of classes to predict
            multi (bool, optional): Whether multioutput is used. Defaults to False.
            out_features (int, optional): The number of output features. Defaults to 1.
            partial_fit (bool, optional): Whether to use partial fit. Defaults to True.
            use_predict (bool, optional): Whether to use predict. Defaults to True.
            output_one_hot (bool, optional): Whether the output should be a one hot vector. Defaults to True.
        """

        self._base = sklearn_estimator
        if multi and out_features > 1:
            sklearn_estimator = MultiOutputClassifier(sklearn_estimator)

        self._multi = multi
        backup = nn.Sequential(nn.Linear(in_features, n_classes), Argmax())
        self.output_one_hot = output_one_hot
        self._n_classes = n_classes
        super().__init__(
            sklearn_estimator,
            in_features,
            out_features,
            partial_fit,
            use_predict,
            backup,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x (torch.Tensor): the input to the estimator

        Returns:
            torch.Tensor: Output of the estimator convert to one hot if required
        """
        y = super().forward(x).long()

        if self.output_one_hot:
            return torch.nn.functional.one_hot(y, num_classes=self._n_classes)
        return y

    def clone(self) -> 'ScikitMulticlass':
        return ScikitMulticlass(
            sklearn.base.clone(self._base), self._in_features,
            self._n_classes, self._multi,
            self._out_features, self._use_partial_fit,
            self._use_predict, self.output_one_hot
        )


class ScikitBinary(ScikitEstimator):
    """Adapter for a binary estimator"""

    def __init__(
        self,
        sklearn_estimator,
        in_features: int = 1,
        out_features: int = 1,
        multi: bool = False,
        partial_fit: bool = True,
        use_predict: bool = True,
    ):
        """initializer

        Args:
            sklearn_estimator (_type_): the estimator to adapt
            in_features (int, optional): The number of input features. Defaults to 1.
            out_features (int, optional): The number of output features. Defaults to 1.
            multi (bool, optional): Whether MultiOutput is used. Defaults to False.
            partial_fit (bool, optional): Whether to use partial_fit() or fit(). Defaults to True.
            use_predict (bool, optional): Whether to predict the output or use 'transform'. Defaults to True.
        """
        self._base = sklearn_estimator
        if multi and out_features > 1:
            sklearn_estimator = MultiOutputClassifier(sklearn_estimator)

        self._multi = multi
        backup = nn.Sequential(nn.Linear(in_features, out_features), Sign())
        super().__init__(
            sklearn_estimator,
            in_features,
            out_features,
            partial_fit,
            use_predict,
            backup,
        )

    def clone(self) -> 'ScikitBinary':
        return ScikitBinary(
            sklearn.base.clone(self._base), self._in_features,
            self._out_features, self._multi,
            self._use_partial_fit,
            self._use_predict,
        )