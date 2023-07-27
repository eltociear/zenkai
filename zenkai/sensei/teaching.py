# 1st party
import typing

# 3rd party
from torch.utils.data import Dataset
from tqdm import tqdm

# local
from ..kaku import Learner
from .base import Classroom, Desk, Teacher
from .materials import IODecorator, Material
from .reporting import Record, Results


class Trainer(Teacher):
    """A teacher that can train the learner"""

    def __init__(
        self,
        name: str,
        default_learner: typing.Union[Learner, str],
        default_material: typing.Union[Material, str],
        record: Record = None,
        desk: Desk = None,
        classroom: Classroom = None,
        window: int = 30,
    ):
        """initializer

        Args:
            name (str): The name of the teacher
            default_learner (typing.Union[Learner, str]): The default learning to train
            default_material (typing.Union[Material, str]): The default material to train with
            record (Record, optional): Record for the teacher to use. Defaults to None.
            desk (Desk, optional): Desk to use for retrieving materials and storing info. Defaults to None.
            classroom (Classroom, optional): The classroom to use. Defaults to None.
            window (int, optional): The size of the widnow for showing results. Defaults to 30.
        """
        super().__init__(name)
        self._desk = desk or Desk()
        self._classroom = classroom or Classroom()

        self.record = record or Record()
        self.learner = default_learner
        self.material = default_material
        self.window = window

    def teach(
        self,
        override_learner: typing.Union[Learner, str] = None,
        override_material: typing.Union[Dataset, str] = None,
        epoch: int = None,
        n_epochs: int = None,
    ):
        """Teach the learner

        Args:
            override_learner (typing.Union[Learner, str], optional): The learner if you want to override it. Defaults to None.
            override_material (typing.Union[Dataset, str], optional): The material if you want to override it. Defaults to None.
            epoch (int, optional): The current epoch. Defaults to None.
            n_epochs (int, optional): The number of epochs to run. Defaults to None.
        """
        learner = self._classroom.get(override_learner) or self._classroom.get(
            self.learner
        )
        material = self._desk.get_material(
            override_material
        ) or self._desk.get_material(self.material)
        results = Results(self.window)
        logger = self.record.create_logger(self.name, material)
        with tqdm(total=len(material)) as pbar:
            for i, (x, t) in enumerate(material):
                assessment_dict = logger(learner.learn(x, t))
                self._assistants.assist(self._name, assessment_dict, (x, t))
                results.add(assessment_dict.numpy())
                aggregation = results.aggregate()
                if epoch is not None:
                    aggregation[
                        "Epoch"
                    ] = f'{epoch}/{"?" if n_epochs is None else n_epochs}'
                pbar.set_postfix(aggregation)
                pbar.update(1)


class Validator(Teacher):
    """A teacher that can test the learner"""

    def __init__(
        self,
        name: str,
        default_learner: typing.Union[Learner, str],
        default_material: typing.Union[Material, str],
        record: Record = None,
        desk: Desk = None,
        classroom: Classroom = None,
        show_progress: bool = True,
    ):
        """initializer

        Args:
            name (str): The name of the teacher
            default_learner (typing.Union[Learner, str]): The default learning to train
            default_material (typing.Union[Material, str]): The default material to train with
            record (Record, optional): Record for the teacher to use. Defaults to None.
            desk (Desk, optional): Desk to use for retrieving materials and storing info. Defaults to None.
            classroom (Classroom, optional): The classroom to use. Defaults to None.
            window (int, optional): The size of the widnow for showing results. Defaults to 30.
        """

        super().__init__(name)
        self._desk = desk or Desk()
        self._classroom = classroom or Classroom()

        self.record = record or Record()
        self.learner = default_learner
        self.material = default_material
        self.show_progress = show_progress

    def teach(
        self,
        override_learner: typing.Union[Learner, str] = None,
        override_material: typing.Union[Dataset, str] = None,
        epoch: int = None,
        n_epochs: int = None,
    ):
        """Teach the learner

        Args:
            override_learner (typing.Union[Learner, str], optional): The learner if you want to override it. Defaults to None.
            override_material (typing.Union[Dataset, str], optional): The material if you want to override it. Defaults to None.
            epoch (int, optional): The current epoch. Defaults to None.
            n_epochs (int, optional): The number of epochs to run. Defaults to None.
        """
        learner = self._classroom.get(override_learner) or self._classroom.get(
            self.learner
        )
        material = self._desk.get_material(
            override_material
        ) or self._desk.get_material(self.material)

        results = Results(None)
        logger = self.record.create_logger(self._name, material)
        with tqdm(total=len(material)) as pbar:
            for i, (x, t) in enumerate(material):
                assessment_dict = logger(learner.test(x, t))
                self._assistants.assist(self._name, assessment_dict, (x, t))
                results.add(assessment_dict.numpy())
                aggregation = results.aggregate()
                if epoch is not None:
                    aggregation[
                        "Epoch"
                    ] = f'{epoch}/{"?" if n_epochs is None else n_epochs}'
                pbar.set_postfix(aggregation)
                pbar.update(1)


def validation_train(
    learner: Learner,
    training_material: Material,
    validation_material: Material,
    n_epochs: int = 1,
    use_io: bool = False,
) -> Record:
    """Train the learner for validation

    Args:
        learner (Learner): The learner to train
        training_material (Material): The material to use for training
        validation_material (Material): The material to use for validation
        n_epochs (int, optional): The number of epochs to run. Defaults to 1.
        use_io (bool, optional): Whehter to use io. Defaults to False.

    Returns:
        Record: The results of teaching
    """

    record = Record()
    if use_io:
        training_material = IODecorator(training_material)
        validation_material = IODecorator(validation_material)
    trainer = Trainer("Trainer", learner, training_material, record=record)
    validator = Validator("Validator", learner, validation_material, record=record)

    for i in range(n_epochs):
        trainer.teach(epoch=i, n_epochs=n_epochs)
        validator.teach(epoch=i, n_epochs=n_epochs)
    return record


def train(
    learner: Learner,
    training_material: Material,
    testing_material: Material = None,
    n_epochs: int = 1,
    use_io: bool = False,
    window: int = 30,
) -> Record:
    """Train the learner for testing

    Args:
        learner (Learner): The learner to train
        training_material (Material): The material to use for training
        validation_material (Material): The material to use for validation
        n_epochs (int, optional): The number of epochs to run. Defaults to 1.
        use_io (bool, optional): Whehter to use io. Defaults to False.

    Returns:
        Record: The results of teaching
    """
    record = Record()
    if use_io:
        training_material = IODecorator(training_material)
    trainer = Trainer("Trainer", learner, training_material, record=record, window=window)
    if testing_material:
        if use_io:
            testing_material = IODecorator(testing_material)
        tester = Validator("Validator", learner, testing_material, record=record)
    else:
        tester = None

    for i in range(n_epochs):
        trainer.teach(epoch=i, n_epochs=n_epochs)
    if tester is not None:
        tester.teach(epoch=i, n_epochs=n_epochs)
    return record
