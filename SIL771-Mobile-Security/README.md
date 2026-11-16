# SIL771 — Mobile Security

M.Tech coursework, IIT Delhi (Semester II).

## Assignments

| # | Topic | Contents |
|---|-------|----------|
| 1 | [Cryptography on Android](Assignment-01-Crypto-on-Android) | Android app using hardware-backed KeyStore: AES-256/CBC/PKCS7 symmetric encryption and SHA-256 message digest, built around a dedicated `ProjectSecurityVault` crypto engine |
| 2 | [Mobile Apps VAPT](Assignment-02-Mobile-Apps-VAPT) | Security testing / vulnerability analysis and penetration testing of the AndroGoat app and a Google Play app (SHEIN); includes Frida instrumentation scripts and Signal Mapper network-data capture |

## Notes

- `Assignment-02`'s `Frida-Scripts/` holds the authored Frida hook scripts used during dynamic analysis (binary patching, SSL/certificate-pinning bypass, emulator-detection bypass, root-detection bypass) plus the resulting patched AndroGoat APK build.
- `Assignment-02`'s `Signal-Mapper-Data/` holds the raw cellular signal capture (CSV) and map tile cache (SQLite) that back `Signal Mapper Report.pdf`.
- Third-party analysis tooling (MobSF, Genymotion emulator images, jadx-gui, Android platform-tools, frida-server binary, DB Browser for SQLite installer, apktool) and the extracted/decompiled third-party app packages (SHEIN APK splits and decompiled Java source, OpenSignal APK) are excluded — see `references.md`.
