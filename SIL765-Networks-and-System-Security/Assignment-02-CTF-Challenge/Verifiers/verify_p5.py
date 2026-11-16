import hashlib
import sys

def verify_p5():
    print("--- NSS P5 Flag Verifier ---")

    # 1. Load the Key and Flag
    try:
        with open("key.txt", "r") as f:
            key = f.read().strip()
        with open("flag.txt", "r") as f:
            flag_found = f.read().strip()
    except FileNotFoundError:
        print("❌ Error: Could not find flag.txt or key.txt in this folder.")
        return

    # 2. Replicate the ctf-extract logic for P5
    # LOGIC: FLAG = SHA256("P5:" + KEY)
    raw_data = f"P5:{key}"
    calculated_flag = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    # 3. Compare
    print(f"[*] Boot Key:        {key}")
    print(f"[*] Your Flag:       {flag_found}")
    print(f"[*] Calculated Flag: {calculated_flag}")
    
    print("-" * 40)
    
    if flag_found == calculated_flag:
        print("✅ MATCH CONFIRMED: You have the correct flag!")
        print("   The system math proves this flag belongs to this key.")
    else:
        print("❌ MISMATCH: The flag you found is mathematically incorrect for this key.")
        print("   Did you copy the key from P1/P2? (It should be the same key).")

if __name__ == "__main__":
    verify_p5()