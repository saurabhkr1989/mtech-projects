Java.perform(function () {
    // Replace with the actual activity/class name found in JADX
    let EmulatorActivity = Java.use("owasp.sat.agoat.EmulatorDetectionActivity");

    // Standard method naming in AndroGoat
    EmulatorActivity.isEmulator.implementation = function () {
        console.log("[!] Emulator check detected! Forcing 'false'...");
        return false;
    };
});