from dishka import AsyncContainer, Provider, Scope, alias, provide

from manashelper.core.config import Settings
from manashelper.modules.food_menu.ui_delegates import FoodMenuUiDelegates
from manashelper.modules.notifications.ui_delegates import NotificationUiDelegates
from manashelper.modules.schedule.ui_delegates import ScheduleUiDelegates
from manashelper.modules.student_questions.service import StudentQuestionsService
from manashelper.modules.student_questions.survey_delegates import SurveyDelegates
from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.application.localized_delegate import LocalizedDelegate
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.infrastructure.deliveries import DeliveryRepository
from manashelper.modules.ui_flows.infrastructure.dialogs import DialogRepository
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.ui_flows.infrastructure.flows import FlowRepository
from manashelper.modules.ui_flows.infrastructure.locations import LocationRepository
from manashelper.modules.ui_flows.infrastructure.maintenance import FlowMaintenanceRepository
from manashelper.modules.ui_flows.infrastructure.rollout import RolloutRepository
from manashelper.modules.ui_flows.infrastructure.triggers import TriggerRepository
from manashelper.modules.ui_flows.menus import FEATURES
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.observation import ObservationCoordinator
from manashelper.modules.users.ui_delegates import UserUiDelegates
from manashelper.platform.secrets import SecretCodec
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry, ExternalDelegateRegistry
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.locations import LocationService
from ui_flows.application.maintenance import FlowMaintenanceService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.schema import DataField
from ui_flows.ports.effects import EffectStore
from ui_flows.ports.repositories import DeliveryStore, DialogStore, FlowStore, LocationStore, MaintenanceStore
from ui_flows.ports.texts import TextCatalog


class UiFlowsProvider(Provider):
    scope = Scope.REQUEST

    flows = provide(FlowRepository)
    dialogs = provide(DialogRepository)
    interpreter = provide(FlowInterpreter)
    flow_service = provide(FlowService)
    user_ui_delegates = provide(UserUiDelegates)
    effect_repository = provide(EffectRepository)
    effect_store = alias(EffectRepository, provides=EffectStore)
    secret_codec = provide(SecretCodec, scope=Scope.APP)
    effect_worker = provide(EffectWorker, scope=Scope.APP)
    delivery_repository = provide(DeliveryRepository)
    delivery_service = provide(ScreenDeliveryService)
    location_repository = provide(LocationRepository)
    location_service = provide(LocationService)
    maintenance_repository = provide(FlowMaintenanceRepository)
    maintenance_service = provide(FlowMaintenanceService)
    rollout_repository = provide(RolloutRepository)
    rollout_service = provide(RolloutService)
    trigger_repository = provide(TriggerRepository)
    trigger_service = provide(TriggerService)
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
    def registry(
        self,
        survey: StudentQuestionsService,
        external: ExternalDelegateRegistry,
        users: UserUiDelegates,
        schedule: ScheduleUiDelegates,
        food: FoodMenuUiDelegates,
        notifications: NotificationUiDelegates,
    ) -> DelegateRegistry:
        bindings = [
            *SurveyDelegates(survey).registry().bindings(),
            *users.bindings(),
            *schedule.bindings(),
            *food.bindings(),
            *notifications.bindings(),
            *external.bindings(),
        ]
        return DelegateRegistry(
            [DelegateBinding(binding.definition, LocalizedDelegate(binding.handler)) for binding in bindings]
        )

    @provide(scope=Scope.APP)
    def external_registry(self) -> ExternalDelegateRegistry:
        return ExternalDelegateRegistry()

    @provide
    def dialog_service(
        self,
        dialogs: DialogStore,
        flows: FlowStore,
        interpreter: FlowInterpreter,
        policy: FlowPolicy,
        effects: EffectStore,
    ) -> DialogService:
        return DialogService(dialogs, flows, interpreter, policy, effects)

    @provide
    def policy(self, settings: Settings, texts: TextCatalog) -> FlowPolicy:
        return FlowPolicy(
            catalog_keys=texts.keys,
            features=FEATURES,
            capability_fields={"eders_enabled": DataField(type="boolean"), "admin_id": DataField(type="integer")},
            capabilities={"eders_enabled": settings.eders_enabled, "admin_id": settings.admin_chat_id},
        )
