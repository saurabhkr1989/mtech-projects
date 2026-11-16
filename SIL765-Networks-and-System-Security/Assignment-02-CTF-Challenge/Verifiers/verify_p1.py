import hashlib
import os

def verify_p1():
    print("--- NSS Assignment 2: P1 Verifier ---")
    
    # 1. Try to read from files automatically
    try:
        with open("key.txt", "r") as kf:
            key = kf.read().strip()
        with open("flag.txt", "r") as ff:
            flag = ff.read().strip()
        print(f"[+] Loaded files automatically.")
    except FileNotFoundError:
        # 2. Fallback: Ask user to paste them
        print("[-] Files not found. Please paste the values below.")
        key = input("Enter content of key.txt: ").strip()
        flag = input("Enter content of flag.txt: ").strip()

    # 3. The Verification Logic (from provision_p1.sh)
    # Logic: SHA256("P1:" + KEY)
    raw_data = f"P1:{key}"
    calculated_flag = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    print("\n---------------------------------------")
    print(f"Key used:       {key}")
    print(f"Your Flag:      {flag}")
    print(f"Calculated Flag:{calculated_flag}")
    print("---------------------------------------")

    if flag == calculated_flag:
        print("✅ SUCCESS: This Key and Flag pair is VALID.")
    else:
        print("❌ FAILURE: The Key does not match the Flag.")
        print("   (Ensure you copied the FULL key string exactly)")

if __name__ == "__main__":
    verify_p1()