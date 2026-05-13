import stock_dictionary.graph_pipeline as graph_pipeline


def _node(name):
    def run(state):
        return {"logs": [name]}

    return run


def test_dictionary_pipeline_graph_runs_full_mode_in_order(monkeypatch):
    monkeypatch.setattr(graph_pipeline, "category_assignment_node", _node("category_assignment"))
    monkeypatch.setattr(graph_pipeline, "duplicate_alias_judgment_node", _node("duplicate_alias_judgment"))
    monkeypatch.setattr(graph_pipeline, "definition_rewrite_node", _node("definition_rewrite"))
    monkeypatch.setattr(graph_pipeline, "source_conflict_resolution_node", _node("source_conflict_resolution"))
    monkeypatch.setattr(graph_pipeline, "term_augmentation_node", _node("term_augmentation"))
    monkeypatch.setattr(graph_pipeline, "augmented_definition_rewrite_node", _node("augmented_definition_rewrite"))
    monkeypatch.setattr(graph_pipeline, "build_final_artifacts_node", _node("build_final_artifacts"))

    result = graph_pipeline.build_dictionary_pipeline_graph().invoke({"mode": "full", "logs": []})

    assert result["logs"] == [
        "category_assignment",
        "duplicate_alias_judgment",
        "definition_rewrite",
        "source_conflict_resolution",
        "term_augmentation",
        "augmented_definition_rewrite",
        "build_final_artifacts",
    ]


def test_dictionary_pipeline_graph_can_resume_at_augmented_definition_rewrite(monkeypatch):
    monkeypatch.setattr(graph_pipeline, "augmented_definition_rewrite_node", _node("augmented_definition_rewrite"))
    monkeypatch.setattr(graph_pipeline, "build_final_artifacts_node", _node("build_final_artifacts"))

    result = graph_pipeline.build_dictionary_pipeline_graph().invoke(
        {"mode": "augmented_definition_rewrite_only", "logs": []}
    )

    assert result["logs"] == ["augmented_definition_rewrite", "build_final_artifacts"]
