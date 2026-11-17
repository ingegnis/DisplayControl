# Android native build supplement — 0.11.0-alpha

Built on 2026-11-17 after explicit user acceptance of the Android SDK license.

- APK: `DisplayControl_Player_TV_v0.11.0-alpha.apk` (74,526 bytes).
- SHA-256: `fd225b972f87c9eb189152171d1ccdd0de315e3f2bd748fb3d2618b52f78f480`.
- App: `it.carisma.player`, versionName `0.11.0-alpha`, versionCode `110`.
- Minimum Android API 26 (Android 8.0), target/compile API 35. Actual WebView/device compatibility still requires testing.
- Toolchain: Microsoft OpenJDK 21.0.13, official Android command-line tools (pinned SHA-256 verified), Android platform 35 and build-tools 35.0.0.
- Real aapt2 resource compile/link, javac, D8 and zipalign succeeded. javac reported Java 8 option/deprecated API warnings; compilation succeeded.
- apksigner verified APK Signature Schemes v2 and v3, one RSA-3072 signer. Certificate SHA-256: `d273ec0e250726bd5806b4794c450d886cc672dbb20ca2b1f66ac8c7833bdd7b`.
- Final signed APK alignment and ZIP CRC checks passed; DEX/manifest and all four bundled shell assets verified. No signing files or private configuration in the APK.
- Seven Android build utility tests passed. Every Android source/resource/asset is byte-identical to release commit `670996413ff18c7ee7fbdb5fbe868b84a6b4e8fc`.

The real build exposed a builder-only password-file bug: apksigner consumed the same single-line file twice when both store/key password arguments were supplied. The corrected builder omits the redundant key-password argument; the generated key uses the store password. See the updated `build_android.py` on GitHub main when rebuilding. No player code changed.

The original full/patch ZIPs and historical test report remain unchanged. This supplement records the later native build; its checksum file covers the APK and this report. The SDK, caches, private key and password are excluded from publication. Back up `data/android-signing/` privately for future updates. This signing identity was generated locally; compatibility with an older APK signed on another installation has not been established. Never uninstall an existing player automatically to bypass a signature mismatch.

No emulator or physical Android/Chromecast was available: launch, pairing, playback, offline recovery, remote-control interaction, HDMI/audio and sustained operation remain untested on device. Native compilation/signature checks do not certify physical operation.
