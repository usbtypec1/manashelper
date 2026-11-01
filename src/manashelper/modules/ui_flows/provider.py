from dishka import AsyncContainer, Provider, Scope, alias, provide

from manashelper.core.config import Settings
from manashelper.modules.student_questions.service import StudentQuestionsService
from manashelper.modules.student_questions.survey_delegates import SurveyDelegates
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.catalog import CATALOG_KEYS
from manashelper.modules.ui_flows.infrastructure.deliveries import DeliveryRepository
from manashelper.modules.ui_flows.infrastructure.dialogs import DialogRepository
from manashelper.modules.ui_flows.infrastructure.flows import FlowRepository
from manashelper.modules.ui_flows.infrastructure.locations import LocationRepository
from manashelper.modules.ui_flows.infrastructure.maintenance import FlowMaintenanceRepository
from manashelper.modules.ui_flows.infrastructure.rollout import RolloutRepository
from manashelper.modules.ui_flows.menus import FEATURES
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.observation import ObservationCoordinator
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.locations import LocationService
from ui_flows.application.maintenance import FlowMaintenanceService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.schema import DataField
from ui_flows.ports.repositories import DeliveryStore, DialogStore, FlowStore, LocationStore, MaintenanceStore


class UiFlowsProvider(Provider):
    scope = Scope.REQUEST

    flows = provide(FlowRepository)
    dialogs = provide(DialogRepository)
    interpreter = provide(FlowInterpreter)
    flow_service = provide(FlowService)
    dialog_service = provide(DialogService)
    delivery_repository = provide(DeliveryRepository)
    delivery_service = provide(ScreenDeliveryService)
    location_repository = provide(LocationRepository)
    location_service = provide(LocationService)
    maintenance_repository = provide(FlowMaintenanceRepository)
    maintenance_service = provide(FlowMaintenanceService)
    rollout_repository = provide(RolloutRepository)
    rollout_service = provide(RolloutService)
    flow_store = alias(FlowRepository, provides=FlowStore)
    dialog_store = alias(DialogRepository, provides=DialogStore)
    delivery_store = alias(DeliveryRepository, provides=DeliveryStore)
    location_store = alias(LocationRepository, provides=LocationStore)
    maintenance_store = alias(FlowMaintenanceRepository, provides=MaintenanceStore)
    observation = provide(ObservationCoordinator, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def coordinator(self, container: AsyncContainer) -> FlowTelegramCoordinator:
        return FlowTelegramCoordinator(container)

    @provide
    def registry(self, survey: StudentQuestionsService) -> DelegateRegistry:
        return SurveyDelegates(survey).registry()

    @provide
    def policy(self, settings: Settings) -> FlowPolicy:
        return FlowPolicy(
            catalog_keys=CATALOG_KEYS,
            features=FEATURES,
            capability_fields={"eders_enabled": DataField(type="boolean")},
            capabilities={"eders_enabled": settings.eders_enabled},
        )
