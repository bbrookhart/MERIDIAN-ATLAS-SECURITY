from atlas_retrieval.trust_boundary import wrap_chunk


def test_wrap_chunk_includes_provenance_and_trust_tier():
    wrapped = wrap_chunk("doc-42", "untrusted", "some retrieved body text")
    assert 'source_doc_id="doc-42"' in wrapped
    assert 'trust="untrusted"' in wrapped
    assert "some retrieved body text" in wrapped
    assert wrapped.startswith("<retrieved-context")
    assert wrapped.endswith("</retrieved-context>")


def test_wrap_chunk_handles_missing_source_doc_id():
    wrapped = wrap_chunk(None, "untrusted", "body")
    assert 'source_doc_id="unknown"' in wrapped
