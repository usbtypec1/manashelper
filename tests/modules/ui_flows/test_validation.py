import pytest


@pytest.mark.parametrize("fixture", ["main_menu_document", "survey_document"])
def test_reference_scenarios_satisfy_registered_contracts(fixture, request, validate_document):
    assert validate_document(request.getfixturevalue(fixture)) == []


@pytest.mark.parametrize(
    "change, code",
    [
        ("entry", "missing_entry"),
        ("target", "missing_target"),
        ("duplicate_node", "duplicate_node"),
        ("duplicate_button", "duplicate_button"),
        ("feature", "unknown_feature"),
        ("reference", "unknown_reference"),
        ("key", "unknown_message_key"),
        ("unreachable", "unreachable_node"),
        ("layout", "unknown_layout_node"),
        ("reply_url", "reply_url"),
    ],
)
def test_broken_menu_contracts_are_reported(main_menu_document, validate_document, change, code):
    first_button = main_menu_document["nodes"][0]["buttons"][0][0]
    if change == "entry":
        main_menu_document["entry"] = "missing"
    elif change == "target":
        first_button["target"] = "missing"
    elif change == "duplicate_node":
        main_menu_document["nodes"].append(main_menu_document["nodes"][0])
    elif change == "duplicate_button":
        main_menu_document["nodes"][0]["buttons"][0].append(first_button)
    elif change == "feature":
        main_menu_document["nodes"][2]["feature"] = "unregistered"
    elif change == "reference":
        first_button["when"] = {"kind": "exists", "reference": {"kind": "ref", "scope": "user", "field": "password"}}
    elif change == "key":
        first_button["label"]["key"] = "not.registered"
    elif change == "unreachable":
        main_menu_document["nodes"].append({"kind": "end", "id": "orphan", "status": "completed"})
    elif change == "layout":
        main_menu_document["layout"] = {"unknown": {"x": 1.0, "y": 2.0}}
    else:
        first_button.clear()
        first_button.update(
            kind="url", id="link", label={"kind": "catalog", "key": "menu.food"}, url="https://example.com"
        )
    issues = validate_document(main_menu_document)
    assert code in {issue.code for issue in issues}
    assert all(issue.path.startswith("/") for issue in issues)


@pytest.mark.parametrize(
    "change, code",
    [
        ("delegate", "unknown_delegate"),
        ("version", "unknown_delegate"),
        ("arguments", "delegate_arguments"),
        ("argument_type", "value_type"),
        ("results", "delegate_results"),
        ("outcomes", "delegate_outcomes"),
        ("initial", "initial_data"),
        ("assignment", "value_type"),
        ("input", "input_type"),
        ("cycle", "automatic_cycle"),
    ],
)
def test_broken_form_contracts_are_reported(survey_document, validate_document, change, code):
    check = survey_document["nodes"][0]
    if change == "delegate":
        check["delegate"] = "os.system"
    elif change == "version":
        check["contract_version"] = 99
    elif change == "arguments":
        check["arguments"] = {}
    elif change == "argument_type":
        check["arguments"]["user_id"] = {"kind": "literal", "value": True}
    elif change == "results":
        check["results"]["submitted"] = "course"
    elif change == "outcomes":
        check["outcomes"]["unexpected"] = "course"
    elif change == "initial":
        survey_document["initial_data"]["overwrite"] = "false"
    elif change == "assignment":
        survey_document["nodes"][2]["buttons"][0][0]["assignments"]["overwrite"] = {"kind": "literal", "value": "true"}
    elif change == "input":
        survey_document["nodes"][5]["input_type"] = "integer"
    else:
        survey_document["nodes"][1]["default"] = "check_submission"
    assert code in {issue.code for issue in validate_document(survey_document)}


def test_layout_and_manual_menu_cycles_do_not_affect_execution_contract(main_menu_document, validate_document):
    main_menu_document["layout"] = {"main": {"x": 12.0, "y": -34.0}}
    assert validate_document(main_menu_document) == []


def test_survey_requires_replacement_confirmation_and_only_writes_at_submit(survey_document):
    nodes = {node["id"]: node for node in survey_document["nodes"]}
    assert nodes["choose_start"]["branches"][0]["target"] == "overwrite"
    assert nodes["overwrite"]["buttons"][0][0]["assignments"]["overwrite"]["value"] is True
    assert nodes["cancel"]["status"] == "cancelled"
    assert nodes["submit"]["outcomes"]["already_submitted"] == "overwrite"
    writes = [node for node in nodes.values() if node.get("delegate") == "student_questions.submit"]
    assert len(writes) == 1
    assert nodes["thanks"]["return_flow"] == "main_menu"
