Assignment 1 :  Cryptography on Android Devices
Course :  SIL771 -  Mobile Security
Submitted by :  Saurabh Kumar Singh (2025JCS3011)

+++++++++++++++++++++++++++++++++++++++++
1 . PROJECT OVERVIEW
+++++++++++++++++++++++++++++++++++++++++

This application implements secure cryptographic operations on Android using the system's hardware backed KeyStore fulfilling the requirements for Part I (Symmetric Encryption) & Part II (Message Digest) .

Important Features of the application have been given as under : 

    -  Secure Key Management  :  Uses Android KeyStore to generate & store 256 bit AES keys in TEE/ StrongBox .
    -  Symmetric Encryption  :  It is implementing AES, CBC and PKCS7 Padding for secure file encryption .
    -  Data Integrity  :  It is implementing SHA-256 hashing for verfication of message digest .
    -  AtRest Protection  :  Encrypts source 'input .txt' using a dedicated storage key to ensure no plaintext exists in internal storage .
    -  Detailed Visualization  :  Shows hex encoded ciphertext, decrypted plaintext & hardware key metadata on screen .

+++++++++++++++++++++++++++++++++++++++++
2 . FILE STRUCTURE & ROLE
+++++++++++++++++++++++++++++++++++++++++

    -  ProjectSecurityVault .kt  :  The core cryptographic engine h&ling KeyStore, AES& SHA-256 logic .
    -  MainActivity .kt  :  The dashboard for navigating between Part I & Part II .
    -  SymmetricActivity .kt  :  H&les the step    - by    - step workflow for Part I (Encryption/Decryption/Comparison) .
    -  DigestActivity .kt  :  H&les the workflow for Part II (Digest Generation/Verification) .
    -  activity_* .xml  :  Layout files designed for modular, step    - by    - step interaction .
    -  file_paths .xml  :  Configuration for FileProvider to allow secure internal file inspection .

+++++++++++++++++++++++++++++++++++++++++
3 . WORKFLOW GUIDE
+++++++++++++++++++++++++++++++++++++++++

Part I :  Symmetric Encryption
1 . Enter text in the 'Input Management' card & click 'Save Input Securely' . This creates an encrypted 'input .txt' .
2 . Click 'View Secure Key Info' to see the hardware    - backed metadata of the AES key .
3 . Click 'Encrypt' to produce 'output .txt' . The ciphertext is displayed in Hex .
4 . Click 'Decrypt' to produce 'plaintext .txt' . The decrypted text is displayed on    - screen .
5 . Click 'Compare' to verify that 'plaintext .txt' matches the original 'input .txt' .

Part II :  Message Digest
1 . (Optional) Edit the input text specifically for the digest task & save .
2 . Click 'Generate digest .txt' to compute the SHA-256 hash .
3 . Click 'Verify Integrity' to parse 'digest .txt' & compare the stored hash with a freshly computed hash of the content .

Note :  You can use the 'Open File' buttons at any step to see the absolute path & raw content of the generated files .

+++++++++++++++++++++++++++++++++++++++++
4 . INSTALLATION & SETUP
+++++++++++++++++++++++++++++++++++++++++

1 . Open Android Studio (Iguana or later recommended) .
2 . Select 'Open' & point to the project root folder .
3 . Ensure the project Gradle Sync completes successfully .
4 . Connect an Android device or Emulator (API Level 31 or higher) .
5 . Click 'Run' to install the 'app' module .

+++++++++++++++++++++++++++++++++++++++++
5 . STORAGE LOCATIONS
+++++++++++++++++++++++++++++++++++++++++

All files (input .txt, output .txt, plaintext .txt, digest .txt) are stored in the app's private internal storage : 
/data/user/0/com .example .a1_2025jcs3011_saurabhkumarsingh/files/
