# Error and edge states

## Observed

- Empty notebook with three starter prompts.
- Submit disabled with no query.
- Source More/customise controls disabled during processing/generation.
- Share Owner combobox and Save button disabled without a permitted change.
- Async source processing and long-running Studio generation remain visible.
- Delete note requires explicit confirmation.
- Reload briefly showed shell loading before persisted content returned.

## Not observed

- NotebookLM source-processing failure/retry.
- Studio artifact failure/retry.
- Offline product messaging.
- Unsupported-source product error.
- Citation Previous/Next controls.

The PDF upload block came from Chrome extension file permission and is not
classified as a NotebookLM defect.
