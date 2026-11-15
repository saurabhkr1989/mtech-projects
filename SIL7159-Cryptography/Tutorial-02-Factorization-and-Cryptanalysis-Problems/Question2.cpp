#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define MAX_BASE 30
#define MAX_REL 50

// Simple prime check for small N
int is_prime(long long n) {
    if (n < 2) return 0;
    for (long long i = 2; i*i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}

// Returns 1 if n is B-smooth over base[], and fills exp[] with exponents
int is_B_smooth(long long n, int base[], int base_size, int exp[]) {
    for (int i = 0; i < base_size; i++) exp[i] = 0;
    for (int i = 0; i < base_size; i++) {
        while (n % base[i] == 0) {
            n /= base[i];
            exp[i]++;
        }
    }
    return n == 1;
}

void print_factorization(int base[], int exp[], int base_size) {
    printf("  ");
    for (int i = 0; i < base_size; i++) {
        if (exp[i] > 0) printf("%d^%d ", base[i], exp[i]);
    }
    printf("\n");
}

long long gcd_steps(long long a, long long b) {
    printf("\nGCD Calculation Steps:\n");
    printf("|   A   |   B   |   Q   |   R   |\n");
    while (b != 0) {
        long long q = a / b;
        long long r = a % b;
        printf("| %6lld | %6lld | %6lld | %6lld |\n", a, b, q, r);
        a = b;
        b = r;
    }
    printf("| %6lld | %6lld |        |        |\n", a, b);
    return a;
}

int main() {
    long long N;
    int base[MAX_BASE], base_size = 0;
    printf("Enter number to factor (N): ");
    scanf("%lld", &N);
    if (is_prime(N)) {
        printf("%lld is prime. Dixon's method will not find factors.\n", N);
        return 0;
    }
    // Build factor base up to 23 (or higher for larger N)
    int B = 23;
    if (N > 10000) B = 29;
    for (int i = 2; i <= B && base_size < MAX_BASE; i++) {
        int is_p = 1;
        for (int j = 2; j*j <= i; j++) if (i % j == 0) is_p = 0;
        if (is_p) base[base_size++] = i;
    }
    printf("Factor base: ");
    for (int i = 0; i < base_size; i++) printf("%d ", base[i]);
    printf("\n\n");
    // Find B-smooth squares
    long long x[MAX_REL], y[MAX_REL];
    int exp[MAX_REL][MAX_BASE], rels = 0;
    long long start = (long long)ceil(sqrt(N));
    printf("Searching for B-smooth squares...\n");
    for (long long k = start; rels < base_size + 5 && k < N; k++) {
        long long sq = (k*k) % N;
        int e[MAX_BASE];
        if (is_B_smooth(sq, base, base_size, e)) {
            x[rels] = k;
            y[rels] = sq;
            for (int j = 0; j < base_size; j++) exp[rels][j] = e[j];
            printf("x = %lld, x^2 mod N = %lld, factorization:", k, sq);
            print_factorization(base, e, base_size);
            rels++;
        }
    }
    if (rels < base_size + 1) {
        printf("Not enough B-smooth relations found. Try increasing N or rerun.\n");
        return 0;
    }
    // Try all pairs of relations
    printf("\nTrying all pairs of relations to find a factor...\n");
    for (int i = 0; i < rels; i++) {
        for (int j = i+1; j < rels; j++) {
            long long a = x[i] * x[j] % N;
            long long b = 1;
            for (int k = 0; k < base_size; k++) {
                int total_exp = exp[i][k] + exp[j][k];
                if (total_exp % 2 != 0) continue; // Only even exponents
                for (int l = 0; l < total_exp/2; l++) b = (b * base[k]) % N;
            }
            if (a == b || a == N-b) continue; // Trivial
            long long f1 = gcd_steps(a - b, N);
            long long f2 = gcd_steps(a + b, N);
            if (f1 > 1 && f1 < N) {
                printf("\nNon-trivial factor found: %lld\n", f1);
                return 0;
            }
            if (f2 > 1 && f2 < N) {
                printf("\nNon-trivial factor found: %lld\n", f2);
                return 0;
            }
        }
    }
    printf("No non-trivial factor found. Try more relations or a larger N.\n");
    return 0;
}
