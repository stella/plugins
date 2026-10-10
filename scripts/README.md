# stella package checks

Run the offline release checks and their boundary tests from the repository root:

```sh
python3 scripts/validate_listing.py --self-test
claude plugin validate ./plugins/stella --strict
claude plugin validate ./.claude-plugin/marketplace.json --strict
```

The Python check uses only the standard library. `listing.schema.json` records
the release's field types, required fields, text and array limits, HTTPS links,
and allowed extension fields. The evaluator implements the schema's declared
keywords and rejects unsupported keywords. It is a focused local schema based
on the [package field reference](https://developers.openai.com/plugins/deploy/submission#manifest-fields),
not the complete hosted validator. It also checks both manifest versions, both
root entries, the shared URL-backed HTTP configuration, bundled PNGs, skill
metadata, README length, and package hygiene. No sign-in or live tool calls run.

The existing `.claude-plugin/plugin.json` retains its supported standard fields;
the extended listing lives in `.codex-plugin/plugin.json`. The two root indexes
continue pointing to the same package. This package does not introduce a root
`plugin.json` in the separate Agent Plugins format.

To build the local release archive:

```sh
cd plugins
zip -r stella.zip stella -x '*/.git' '*/.git/*'
```

Keep the archive out of Git. Increment the versions in both package manifests
and the root versioned entry for each release. Additional test fixtures and a
recording can be added once verified; the current package omits those fields.
