#include <stdio.h>
#include <stdlib.h>

#define P 1187   // prime modulus
#define G 7      // base g
#define H 945    // target h
#define ORDER 1186  // group order = p-1

// Structure to hold state (X, a, b)
typedef struct {
    long long X;
    int a;
    int b;
} State;

// Partition function f (Pollard Rho DLP)
State f(State s, char *set, char *formulaX, char *formulaAB) {
    State next = s;

    if (s.X % 3 == 0) {
        // S0: multiply by g
        *set = '0';
        sprintf(formulaX, "X = g * %lld mod %d = %lld", s.X, P, (G * s.X) % P);
        sprintf(formulaAB, "a = %d+1 = %d, b = %d", s.a, (s.a+1)%ORDER, s.b);
        next.X = (G * s.X) % P;
        next.a = (s.a + 1) % ORDER;
    } else if (s.X % 3 == 1) {
        // S1: square
        *set = '1';
        sprintf(formulaX, "X = %lld^2 mod %d = %lld", s.X, P, (s.X * s.X) % P);
        sprintf(formulaAB, "a = 2*%d = %d, b = 2*%d = %d", s.a, (2*s.a)%ORDER, s.b, (2*s.b)%ORDER);
        next.X = (s.X * s.X) % P;
        next.a = (2 * s.a) % ORDER;
        next.b = (2 * s.b) % ORDER;
    } else {
        // S2: multiply by h
        *set = '2';
        sprintf(formulaX, "X = h * %lld mod %d = %lld", s.X, P, (H * s.X) % P);
        sprintf(formulaAB, "a = %d, b = %d+1 = %d", s.a, s.b, (s.b+1)%ORDER);
        next.X = (H * s.X) % P;
        next.b = (s.b + 1) % ORDER;
    }
    return next;
}

// Extended Euclidean Algorithm to compute gcd and modular inverse
int extended_gcd(int a, int b, int *x, int *y) {
    if (b == 0) {
        *x = 1;
        *y = 0;
        return a;
    }
    int x1, y1;
    int gcd = extended_gcd(b, a % b, &x1, &y1);
    *x = y1;
    *y = x1 - (a / b) * y1;
    return gcd;
}

int mod_inverse(int a, int m) {
    int x, y;
    int g = extended_gcd(a, m, &x, &y);
    if (g != 1) return -1; // no inverse
    else return (x % m + m) % m;
}

// Modular exponentiation
long long modexp(long long base, long long exp, long long mod) {
    long long result = 1;
    base %= mod;
    while (exp > 0) {
        if (exp & 1) result = (result * base) % mod;
        base = (base * base) % mod;
        exp >>= 1;
    }
    return result;
}

int main() {
    State tortoise = {G, 1, 0}; // initial state (X0=7, a=1, b=0)
    State hare = tortoise;

    printf("%-8s %-8s %-40s %-35s %-20s\n", 
           "Iter", "Set", "Formula for X", "Formula for (a,b)", "Result (X,a,b)");
    printf("-------------------------------------------------------------------------------------------------------------\n");

    for (int i = 1; i <= 2000; i++) {
        char set, formulaX[100], formulaAB[100];

        // move tortoise one step
        tortoise = f(tortoise, &set, formulaX, formulaAB);
        // move hare two steps
        hare = f(f(hare, &set, formulaX, formulaAB), &set, formulaX, formulaAB);

        printf("%-8d S%c       %-40s %-35s (%lld, %d, %d)\n", 
               i, set, formulaX, formulaAB, tortoise.X, tortoise.a, tortoise.b);

        if (tortoise.X == hare.X) {
            printf("\nCollision found at iteration %d: X = %lld\n", i, tortoise.X);
            printf("Tortoise (a=%d, b=%d), Hare (a=%d, b=%d)\n", tortoise.a, tortoise.b, hare.a, hare.b);

            // Solve congruence: (a_t - a_h) ≡ x (b_h - b_t) (mod ORDER)
            int delta_a = (tortoise.a - hare.a) % ORDER;
            if (delta_a < 0) delta_a += ORDER;
            int delta_b = (hare.b - tortoise.b) % ORDER;
            if (delta_b < 0) delta_b += ORDER;

            printf("Equation: %d ≡ x * %d (mod %d)\n", delta_a, delta_b, ORDER);

            int g = 0, x, y;
            g = extended_gcd(delta_b, ORDER, &x, &y);

            if (delta_a % g != 0) {
                printf("No solution exists.\n");
            } else {
                int mod = ORDER / g;
                int inv = mod_inverse(delta_b / g, mod);
                if (inv == -1) {
                    printf("No modular inverse found.\n");
                } else {
                    int solution = ( (delta_a / g) * inv ) % mod;
                    printf("Possible solutions for x (mod %d): ", ORDER);
                    for (int k = 0; k < g; k++) {
                        int sol = (solution + k * mod) % ORDER;
                        printf("%d ", sol);
                    }
                    printf("\n");

                    // Verification of solutions
                    printf("\nVerifying candidate solutions...\n");
                    for (int k = 0; k < g; k++) {
                        int sol = (solution + k * mod) % ORDER;
                        long long val = modexp(G, sol, P);
                        printf("x = %d → 7^x mod 1187 = %lld", sol, val);
                        if (val == H) printf("  ✅ matches h=945\n");
                        else printf("  ❌ not a match\n");
                    }
                }
            }
            break;
        }
    }
    return 0;
}