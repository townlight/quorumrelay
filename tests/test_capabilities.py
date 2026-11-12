from civic_data_connectors import Engine, Source
from civic_data_connectors.capabilities import provider_capabilities
from civic_data_connectors.compat import source_formats


def test_all_roster_providers_have_honest_nonempty_packaged_capabilities():
    from jsonschema import Draft202012Validator
    from civic_data_connectors.schemas import json_schema

    validator = Draft202012Validator(json_schema("capability"))
    rows = Engine().providers().data["providers"]
    assert len(rows) == 31
    assert {row["provider"] for row in rows} == {row["connector"] for row in source_formats()}
    for row in rows:
        capabilities = row["capabilities"]
        assert capabilities["canonical_id"] == row["provider"]
        assert set(capabilities["operations"]) >= {
            "identify", "discover", "fetch", "parse", "native_search", "local_search",
            "neutral_export", "vendor_file_export", "create", "update",
        }
        assert capabilities["evidence"]
        validator.validate(capabilities)


def test_every_alias_resolves_to_single_exact_registry_provider_without_extra_family():
    rows = Engine().providers().data["providers"]
    for row in rows:
        for alias in row["aliases"]:
            assert provider_capabilities(alias)["canonical_id"] == row["provider"]
            assert Source(alias, "https://example.org").provider == row["provider"]
            result = Engine().execute("capabilities", {"provider": alias})
            assert result.status == "completed" and len(result.data["providers"]) == 1
            assert result.data["providers"][0]["provider"] == row["provider"]
    assert Engine().execute("capabilities", {"provider": "not-a-provider"}).status == "failed"


def test_registered_native_search_implementations_have_honest_packaged_labels():
    from civic_data_connectors import create_engine
    engine = create_engine()
    catalog = {row["provider"]: row["capabilities"] for row in engine.providers().data["providers"]}
    assert engine.native_searches
    assert {provider: catalog[provider]["operations"]["native_search"]["implementation_status"]
            for provider in engine.native_searches} == {provider: "implemented" for provider in engine.native_searches}


def test_changed_explicit_public_routes_have_implemented_labels_without_catalog_acceptance():
    pairs = [("swagit", "discover"), ("peak", "discover"), ("onbase", "discover"),
             ("digital-towpath", "discover"), ("digital-towpath", "fetch"), ("civicweb", "fetch")]
    for provider, operation in pairs:
        metadata = provider_capabilities(provider)["operations"][operation]
        assert metadata["implementation_status"] == "implemented"
        assert metadata["acceptance_status"] == "not_run"
        assert metadata["evidence_ids"]
