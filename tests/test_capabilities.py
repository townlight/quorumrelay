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
             ("digital-towpath", "discover"), ("digital-towpath", "fetch"), ("civicweb", "fetch"),
             ("civicweb", "discover")]
    for provider, operation in pairs:
        metadata = provider_capabilities(provider)["operations"][operation]
        assert metadata["implementation_status"] == "implemented"
        # The observed Akron window now has attributed fixture execution;
        # this does not promote other public routes to provider acceptance.
        assert metadata["acceptance_status"] == ("fixture_passed" if provider == "onbase" else "not_run")
        if provider == "onbase":
            assert "onbase-akron-model-window-execution" in metadata["evidence_ids"]
        assert metadata["evidence_ids"]


def test_known_explicit_listing_and_native_write_labels_are_not_stale_access_gates():
    from civic_data_connectors.write_adapters import default_adapters
    for provider in ("legistar", "wistia"):
        assert provider_capabilities(provider)["operations"]["discover"]["implementation_status"] == "implemented"
    adapters = default_adapters()
    for provider in ("legistar", "wistia", "laserfiche-weblink"):
        assert provider in adapters
        operations = provider_capabilities(provider)["operations"]
        assert all(operations[operation]["implementation_status"] == "implemented"
                   for operation in ("create", "update", "upload"))
        # Registration is not acceptance. Only attributed Legistar sample routes
        # have synthetic proof; every other entry keeps its existing status.
        for operation in ("create", "update", "upload"):
            expected = "mock_passed" if provider == "legistar" and operation != "upload" else "not_run"
            assert operations[operation]["acceptance_status"] == expected
    essential = provider_capabilities("municode-meetings")
    assert essential["operations"]["update"]["acceptance_status"] == "mock_passed"
    multimedia = [row for row in essential["outbound_mappings"] if row["acceptance_status"] == "mock_passed"]
    assert len(multimedia) == 1 and multimedia[0]["entity"] == "meeting.multimedia"
    assert all(row["acceptance_status"] == "not_run"
               for row in provider_capabilities("telvue")["outbound_mappings"])


def test_attributed_outbound_subsets_match_exact_public_dispatches():
    accepted = {"granicus": 19, "wistia": 8, "laserfiche-weblink": 6,
                "civicplus-select": 1, "onbase": 1}
    for provider, count in accepted.items():
        rows = provider_capabilities(provider)["outbound_mappings"]
        assert sum(row["acceptance_status"] == "mock_passed" for row in rows) == count
    assert provider_capabilities("legistar")["outbound_mappings"][4]["acceptance_status"] == "mock_passed"
    assert provider_capabilities("wistia")["outbound_mappings"][4]["operation"] == "create"
    assert provider_capabilities("laserfiche-weblink")["outbound_mappings"][3]["operation"] == "update"
