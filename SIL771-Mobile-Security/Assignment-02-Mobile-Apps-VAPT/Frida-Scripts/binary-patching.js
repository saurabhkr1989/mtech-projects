Java.perform(function() {
    var BinaryPatchingActivity = Java.use("owasp.sat.agoat.BinaryPatchingActivity");
    var Button = Java.use("android.widget.Button");
    var TextView = Java.use("android.widget.TextView");

    BinaryPatchingActivity.onCreate.overload('android.os.Bundle').implementation = function(savedInstanceState) {
        // 1. Let the original onCreate run first
        this.onCreate(savedInstanceState);
        console.log("[*] onCreate finished. Manually patching UI components...");

        try {
            // 2. Find the 'Administration' button by its ID name
            var btnId = this.getResources().getIdentifier("adminButton", "id", this.getPackageName());
            var adminBtn = Java.cast(this.findViewById(btnId), Button);
            
            // 3. Force it to be enabled
            adminBtn.setEnabled(true);
            console.log("[+] Admin Button FORCED to Enabled.");

            // 4. Find the status text and update it
            var textId = this.getResources().getIdentifier("isAdminText", "id", this.getPackageName());
            var statusText = Java.cast(this.findViewById(textId), TextView);
            statusText.setText("You are Admin Now (Frida Bypass)");
            console.log("[+] Status Text FORCED to Admin.");

        } catch (err) {
            console.log("[-] Error during manual UI patch: " + err);
        }
    };
});