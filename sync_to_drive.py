name: Sync docs to Google Drive

on:
  push:
    branches: [master]
    paths:
      - 'README.md'
      - 'CLAUDE.md'
      - 'ARQUITECTURA.md'
      - 'CHANGELOG.md'
      - 'docs/**'
  workflow_dispatch: {}

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install google-api-python-client google-auth

      - name: Decode service account key
        run: echo "${{ secrets.GDRIVE_SA_KEY_B64 }}" | base64 -d > sa_key.json

      - name: Sync files to Drive
        env:
          GDRIVE_FOLDER_ID: 1dOeSC1D4Lu5NGGvteMb1JF9iehRUr-bQ
          GDRIVE_SA_KEY_FILE: sa_key.json
        run: python .github/scripts/sync_to_drive.py

      - name: Clean up key
        if: always()
        run: rm -f sa_key.json
