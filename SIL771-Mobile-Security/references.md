# Excluded from this repo (SIL771 — Mobile Security)

Reproducibility of own analysis (reports, scripts, captured data) is preserved; third-party tool installations and third-party app packages are not redistributed here.

| Item | Why excluded | Where to get it |
|---|---|---|
| MobSF (Mobile Security Framework) | Third-party open-source scanner, installed locally for Assignment 2 analysis | github.com/MobSF/Mobile-Security-Framework-MobSF |
| Genymotion emulator images | Third-party Android emulator, used to run AndroGoat/SHEIN for testing | genymotion.com |
| jadx-gui / skylot-jadx source | Third-party Java decompiler used for APK analysis | github.com/skylot/jadx |
| Android `platform-tools` (adb, fastboot, …) | Standard Google Android SDK download | developer.android.com/tools/releases/platform-tools |
| frida-server binary | Third-party dynamic instrumentation toolkit server binary | github.com/frida/frida |
| DB Browser for SQLite (installer + app folder) | Third-party GUI tool used to inspect app databases | sqlitebrowser.org |
| apktool | Third-party APK decompiler/rebuilder | ibotpeaches.github.io/Apktool |
| SHEIN APK splits + decompiled Java source (`shein/`) | Third-party commercial app, extracted/decompiled for VAPT practice — not Saurabh's own work, not redistributable | Google Play (installed APK was pulled from a live device for the exercise) |
| OpenSignal extracted APK + `.ab` backup (`opensignal_extracted.apk`, `opensignal_data_leak.ab`) | Third-party commercial app extraction | Google Play |

Own analysis outputs referencing these targets (MobSF/SHEIN scan report, Signal Mapper report, Frida scripts, captured signal data) are included in `Assignment-02-Mobile-Apps-VAPT/`.
