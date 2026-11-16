import hashlib
import sys
import os

def verify_p4():
    print("--- NSS Assignment 2: P4 Flag Verifier ---")
    
    # 1. Check for files
    if not os.path.exists("key.txt") or not os.path.exists("flag.txt"):
        print("[ERROR] 'flag.txt' and 'key.txt' must be in this folder.")
        return

    # 2. Read files
    try:
        with open("key.txt", "r") as kf:
            key = kf.read().strip()
        with open("flag.txt", "r") as ff:
            flag_found = ff.read().strip()
    except Exception as e:
        print(f"[ERROR] Could not read files: {e}")
        return

    # 3. Verification Logic
    # Logic: SHA256("P4:" + KEY)
    prefix = "P4:"
    raw_data = prefix + key
    
    # Calculate expected hash
    calculated_flag = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    # 4. Output Results
    print(f"[*] Boot Key:        {key}")
    print(f"[*] Your Flag:       {flag_found}")
    print(f"[*] Calculated Flag: {calculated_flag}")
    print("-" * 50)

    if flag_found == calculated_flag:
        print("[SUCCESS] Your P4 flag is mathematically CORRECT.")
    else:
        print("[FAILURE] The flag does not match the key.")
        print("   (Check if you pasted the correct P4 flag)")

if __name__ == "__main__":
    verify_p4()