import pytest
import yaml

from indexer.openapi_normalizer import normalize_operation, parse_spec


@pytest.fixture
def mini_spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "components": {
            "schemas": {
                "SessionResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Session ID"},
                        "status": {"type": "string", "enum": ["active", "expired"]},
                    },
                    "required": ["id"],
                }
            }
        },
        "paths": {
            "/v1/sessions": {
                "post": {
                    "summary": "Create session",
                    "description": "Creates a new session",
                    "tags": ["Sessions"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Session name"},
                                        "email": {"type": "string", "description": "Email address"},
                                    },
                                    "required": ["name"],
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Session created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SessionResponse"
                                    }
                                }
                            },
                        },
                        "400": {"description": "Bad request"},
                    },
                }
            }
        },
    }


def test_normalize_operation_basic(mini_spec):
    op = mini_spec["paths"]["/v1/sessions"]["post"]
    doc = normalize_operation(mini_spec, "post", "/v1/sessions", op)
    assert doc.doc_id == "openapi:POST-/v1/sessions"
    assert doc.method == "POST"
    assert doc.path == "/v1/sessions"
    assert doc.tag == "Sessions"
    assert doc.summary == "Create session"
    assert doc.description == "Creates a new session"


def test_normalize_operation_includes_request_body(mini_spec):
    op = mini_spec["paths"]["/v1/sessions"]["post"]
    doc = normalize_operation(mini_spec, "post", "/v1/sessions", op)
    assert "Request body:" in doc.text
    assert "name" in doc.text
    assert "email" in doc.text
    assert "required" in doc.text


def test_normalize_operation_includes_responses(mini_spec):
    op = mini_spec["paths"]["/v1/sessions"]["post"]
    doc = normalize_operation(mini_spec, "post", "/v1/sessions", op)
    assert "Responses:" in doc.text
    assert "200" in doc.text
    assert "400" in doc.text


def test_normalize_operation_resolves_ref(mini_spec):
    op = mini_spec["paths"]["/v1/sessions"]["post"]
    doc = normalize_operation(mini_spec, "post", "/v1/sessions", op)
    assert "Session ID" in doc.text
    assert "active" in doc.text
    assert "expired" in doc.text


def test_parse_spec_from_file(tmp_path, mini_spec):
    spec_path = tmp_path / "openapi.yaml"
    spec_path.write_text(yaml.dump(mini_spec, default_flow_style=False))
    docs = parse_spec(str(spec_path))
    assert len(docs) == 1
    assert docs[0].doc_id == "openapi:POST-/v1/sessions"


def test_parse_spec_multiple_operations(tmp_path):
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": {
            "/v1/items": {
                "get": {"summary": "List items", "tags": ["Items"], "responses": {"200": {"description": "OK"}}},
                "post": {"summary": "Create item", "tags": ["Items"], "responses": {"200": {"description": "OK"}}},
            }
        },
    }
    spec_path = tmp_path / "openapi.yaml"
    spec_path.write_text(yaml.dump(spec, default_flow_style=False))
    docs = parse_spec(str(spec_path))
    assert len(docs) == 2
    doc_ids = {d.doc_id for d in docs}
    assert "openapi:GET-/v1/items" in doc_ids
    assert "openapi:POST-/v1/items" in doc_ids


def test_deprecated_operation(mini_spec):
    mini_spec["paths"]["/v1/sessions"]["post"]["deprecated"] = True
    op = mini_spec["paths"]["/v1/sessions"]["post"]
    doc = normalize_operation(mini_spec, "post", "/v1/sessions", op)
    assert "DEPRECATED" in doc.text


def test_operation_with_parameters():
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": {
            "/v1/sessions/{id}": {
                "get": {
                    "summary": "Get session",
                    "tags": ["Sessions"],
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "description": "Session ID",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    op = spec["paths"]["/v1/sessions/{id}"]["get"]
    doc = normalize_operation(spec, "get", "/v1/sessions/{id}", op)
    assert "Parameters:" in doc.text
    assert "id" in doc.text
    assert "path" in doc.text
