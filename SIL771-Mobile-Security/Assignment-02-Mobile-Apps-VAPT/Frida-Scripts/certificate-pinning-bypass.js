Java.perform(function() {
    console.log("\n[.] Universal SSL Pinning Bypass Started");

    // 1. Hooking TrustManager to accept all certificates
    var TrustManager = Java.use('javax.net.ssl.X509TrustManager');
    var SSLContext = Java.use('javax.net.ssl.SSLContext');

    var TrustManagerImpl = Java.registerClass({
        name: 'com.example.TrustManagerImpl',
        implements: [TrustManager],
        methods: {
            checkClientTrusted: function(chain, authType) {},
            checkServerTrusted: function(chain, authType) {},
            getAcceptedIssuers: function() { return []; }
        }
    });

    var TrustManagers = [TrustManagerImpl.$new()];

    SSLContext.init.overload(
        '[Ljavax.net.ssl.KeyManager;', 
        '[Ljavax.net.ssl.TrustManager;', 
        'java.security.SecureRandom'
    ).implementation = function(keyManager, trustManager, secureRandom) {
        console.log("[+] Bypassing standard SSLContext TrustManager...");
        this.init(keyManager, TrustManagers, secureRandom);
    };

    // 2. Hooking OkHttp3 CertificatePinner (Very common in Kotlin)
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, chain) {
            console.log("[+] Bypassing OkHttp3 CertificatePinner for: " + hostname);
            return; 
        };
    } catch (err) {
        console.log("[!] OkHttp3 not found or not used in this app flow.");
    }

    // 3. Hooking Android-specific TrustManagerImpl
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        TrustManagerImpl.checkTrustedRecursive.implementation = function(chain, host, checkServer, isChainValid, isVerifyCertificateNetPolicy) {
            console.log("[+] Bypassing TrustManagerImpl (Conscrypt) for: " + host);
            return Java.use('java.util.ArrayList').$new();
        };
    } catch (err) {
        console.log("[!] Conscrypt TrustManagerImpl hook failed.");
    }
});