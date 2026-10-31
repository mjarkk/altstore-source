# CLAUDE.md

The AltStore PAL source for all of the user's apps. Each app version's package is stored in a
GitHub release of this repo; `source.json` points at it.

The user commits, pushes and runs `add-version.py` (it creates a public GitHub release)
themselves. Only edit files.

## Publishing a version

1. Submit the version in App Store Connect with review type **Notarization**.
2. Once it's approved, copy its **Alternative Distribution Package ID** (app → Distribution → History).
3. Run `./add-version.py <ADP ID>`. It downloads the package from AltStore PAL, uploads it to a
   release and adds the version to `source.json`. Needs `gh`, logged in.
4. If the version added entitlements or `NS…UsageDescription` keys to the app, add them to its
   `appPermissions`. AltStore refuses to install an app with permissions the source doesn't list.
5. Commit and push `source.json`.

## Adding an app

1. In App Store Connect, under Users and Access → Integrations → Marketplace → AltStore PAL, make the
   app eligible for distribution.
2. Add it to `apps` in `source.json` with `"versions": []`. The fields are described in
   [Make a Source](https://faq.altstore.io/developers/make-a-source); icons go in `icons/`,
   screenshots in `screenshots/<app>/`.
3. Publish its first version as above.
