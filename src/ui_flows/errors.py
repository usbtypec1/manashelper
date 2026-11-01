"""Public errors of the scenario application; messages never include submitted values."""

from ui_flows.domain.contracts import ContractIssue


class FlowNotFoundError(Exception):
    pass


class FlowConflictError(Exception):
    pass


class InvalidFlowError(Exception):
    def __init__(self, issues: list[ContractIssue]) -> None:
        self.issues = issues
        super().__init__("Scenario validation failed")


class DialogNotFoundError(Exception):
    pass


class ActiveDialogError(Exception):
    pass


class StaleEventError(Exception):
    pass


class InvalidEventError(Exception):
    pass


class FlowExecutionError(Exception):
    pass
