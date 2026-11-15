#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define MAXM 1000

// Modular exponentiation: (base^exp) % mod
long long modpow(long long base, long long exp, long long mod) {
    long long result = 1;
    base = base % mod;
    while (exp > 0) {
        if (exp % 2 == 1)
            result = (result * base) % mod;
        base = (base * base) % mod;
        exp /= 2;
    }
    return result;
}

// Extended Euclidean Algorithm for modular inverse
typedef struct { long long value; int j; } BabyStep;

long long modinv(long long a, long long m) {
    long long m0 = m, t, q;
    long long x0 = 0, x1 = 1;
    if (m == 1) return 0;
    while (a > 1) {
        q = a / m;
        t = m;
        m = a % m, a = t;
        t = x0;
        x0 = x1 - q * x0;
        x1 = t;
    }
    if (x1 < 0) x1 += m0;
    return x1;
}

int main() {
    long long A = 2, B = 1898, N = 2909;
    printf("BABY STEP–GIANT STEP for 2^x ≡ 1898 (mod 2909)\n");
    printf("---------------------------------------------------\n");
    // Step 1: Compute m
    long long m = (long long)ceil(sqrt(N));
    printf("Step 1: Compute m = ceil(sqrt(%lld)) = %lld\n\n", N, m);
    if (m > MAXM) {
        printf("N is too large for this demo program.\n");
        return 1;
    }

    // Step 2: Baby Steps
    BabyStep* babysteps = (BabyStep*)malloc(m * sizeof(BabyStep));
    printf("Step 2: BABY STEPS\n");
    printf("Compute 2^j mod 2909 for j = 0 to %lld:\n", m-1);
    long long aj = 1;
    for (long long j = 0; j < m; j++) {
        babysteps[j].value = aj;
        babysteps[j].j = j;
        printf("  j = %2lld: 2^%2lld mod 2909 = %4lld\n", j, j, aj);
        aj = (aj * A) % N;
    }
    printf("\n");

    // Step 3: Compute 2^m mod 2909 and its inverse
    long long Am = modpow(A, m, N);
    printf("Step 3: Compute 2^m mod 2909 = 2^%lld mod 2909 = %lld\n", m, Am);
    long long Am_inv = modinv(Am, N);
    printf("Compute modular inverse of %lld mod 2909: %lld\n\n", Am, Am_inv);

    // Step 4: Giant Steps
    printf("Step 4: GIANT STEPS\n");
    printf("For i = 0 to %lld, compute gamma = 1898 * (%lld^i) mod 2909:\n", m-1, Am_inv);
    long long gamma = B;
    int found = 0;
    for (long long i = 0; i < m; i++) {
        printf("  i = %2lld: gamma = %4lld\n", i, gamma);
        // Search for gamma in baby steps
        for (long long j = 0; j < m; j++) {
            if (babysteps[j].value == gamma) {
                long long x = i * m + babysteps[j].j;
                printf("\nSUCCESS!\n");
printf("Found match: gamma = 2^%d mod 2909\n", babysteps[j].j);
printf("So, x = i * m + j = %lld * %lld + %d = %lld\n", i, m, babysteps[j].j, x);
                printf("Check: 2^%lld mod 2909 = %lld\n", x, modpow(2, x, 2909));
                found = 1;
                break;
            }
        }
        if (found) break;
        gamma = (gamma * Am_inv) % N;
    }
    if (!found) {
        printf("\nNo solution found in the given range.\n");
    }
    free(babysteps);
    return 0;
}
