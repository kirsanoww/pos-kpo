from dependency_injector import containers, providers

from pos.adapters.console import Console
from pos.adapters.export import CsvExporter
from pos.adapters.storage import JsonRepository
from pos.application.facade import AssessmentFacade
from pos.domain.calculation import AllCriteria, GradedCriteria, TotalCalculator
from pos.domain.model import EvaluationFactory


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    repository = providers.Singleton(JsonRepository, path=config.data_path)
    factory = providers.Factory(EvaluationFactory)
    calculators = providers.Dict(
        all=providers.Factory(TotalCalculator, strategy=providers.Factory(AllCriteria)),
        graded=providers.Factory(TotalCalculator, strategy=providers.Factory(GradedCriteria)),
    )
    exporter = providers.Factory(CsvExporter, protected_path=config.data_path)
    facade = providers.Factory(
        AssessmentFacade,
        repository=repository,
        factory=factory,
        calculators=calculators,
        exporter=exporter,
    )
    console = providers.Factory(Console, facade=facade)
