Java.perform(function () {
    let RootDetectionActivity = Java.use("owasp.sat.agoat.RootDetectionActivity");

    // Hook the first check (File based)
    RootDetectionActivity.isRooted.implementation = function () {
        console.log("[*] Intercepted isRooted(). Forcing false...");
        return false;
    };

    // Hook the second check (Command based)
    RootDetectionActivity.isRooted1.implementation = function () {
        console.log("[*] Intercepted isRooted1(). Forcing false...");
        return false;
    };
});