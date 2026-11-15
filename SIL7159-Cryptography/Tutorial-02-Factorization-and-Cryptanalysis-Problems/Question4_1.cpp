#include <stdio.h>
#define MODP    1187   // modulus
#define ORDER   (MODP-1)
#define G       7      // generator
#define H       945    // target

#define MAXSTEPS 1000

typedef struct {
    int X, a, b;
} State;

int modmul(int a, int b, int mod) { return (int)(((long long)a * b) % mod); }
int modpow(int base, int exp, int mod) {
    long long res = 1, b = base;
    while(exp) { if(exp&1) res = (res*b)%mod; b = (b*b)%mod; exp >>= 1;}
    return (int)res;
}

// Extended Euclid for modular inverse with trace
int modinv_verbose(int a, int mod) {
    int t=0, newt=1, r=mod, newr=a;
    printf("\nFinding modular inverse of %d mod %d:\n\n", a, mod);
    int step = 0;
    while(newr != 0) {
        int q = r/newr;
        printf("  Step %d: r=%d, newr=%d, q=%d, t=%d, newt=%d\n\n", step++, r, newr, q, t, newt);
        int tmp = newt; newt = t-q*newt; t=tmp;
        tmp = newr; newr = r-q*newr; r=tmp;
    }
    if(r > 1) return -1;
    if(t < 0) t += mod;
    printf("  ==> Inverse is %d\n\n", t);
    return t;
}

int partition(int X) { return X % 3; }

State pollard_step(State s, int *rule, char *desc) {
    int set = partition(s.X);
    *rule = set + 1;
    State ns = s;
    if(set == 0) { // S1
        ns.X = modmul(G, ns.X, MODP);
        ns.a = (ns.a+1) % ORDER;
        sprintf(desc, "S1: X=g*X=%d*%d mod %d=%d, a=%d+1=%d, b=%d", G, s.X, MODP, ns.X, s.a, ns.a, s.b);
    } else if(set == 1) { // S2
        ns.X = modmul(ns.X, ns.X, MODP);
        ns.a = (2*ns.a) % ORDER;
        ns.b = (2*ns.b) % ORDER;
        sprintf(desc, "S2: X=X^2=%d^2 mod %d=%d, a=2*%d=%d, b=2*%d=%d", s.X, MODP, ns.X, s.a, ns.a, s.b, ns.b);
    } else { // S3
        ns.X = modmul(H, ns.X, MODP);
        ns.b = (ns.b+1) % ORDER;
        sprintf(desc, "S3: X=h*X=%d*%d mod %d=%d, a=%d, b=%d+1=%d", H, s.X, MODP, ns.X, s.a, s.b, ns.b);
    }
    return ns;
}

int gcd_verbose(int a, int b) {
    printf("\nGCD computation for (%d,%d):\n\n", a, b);
    while(b!=0) { printf("  gcd(%d,%d)=gcd(%d,%d)\n\n", a, b, b, a%b); int t=b; b=a%b; a=t; }
    printf("  ==> gcd=%d\n\n",a);
    return a;
}

int main() {
    printf("Pollard's Rho for Discrete Logarithm (7^x ≡ 945 mod 1187)\n\n");
    printf("Step |  Tortoise (X,a,b)        |  Rule / Calculation\n\n");
    printf("----------------------------------------------------------\n");
    State tort={G,1,0}, hare={G,1,0};
    char tdesc[100], hdesc1[100], hdesc2[100];
    int tRule, hRule1, hRule2;
    int collision_found=0;
    printf("%3d | (%4d,%4d,%4d)        |  Start\n\n", 0, tort.X,tort.a,tort.b);

    for(int step=1; step<MAXSTEPS; ++step) {
        tort = pollard_step(tort, &tRule, tdesc);
        State hare1 = pollard_step(hare, &hRule1, hdesc1); // Hare Move 1
        State hare2 = pollard_step(hare1, &hRule2, hdesc2); // Hare Move 2
        hare = hare2;

        printf("%3d | (%4d,%4d,%4d)        |  T:%s\n\n", step, tort.X,tort.a,tort.b, tdesc);
        printf("    | (%4d,%4d,%4d)        |  H1:%s\n\n", hare1.X, hare1.a, hare1.b, hdesc1);
        printf("    | (%4d,%4d,%4d)        |  H2:%s\n\n", hare2.X, hare2.a, hare2.b, hdesc2);

        if(tort.X == hare.X && !collision_found) {
            printf("\n*** COLLISION found at step %d! X = %d\n\n", step, tort.X);
            printf("Tortoise  (a, b) = (%d, %d), Hare (a, b) = (%d, %d)\n\n", tort.a, tort.b, hare.a, hare.b);

            int diff_a = (tort.a - hare.a + ORDER) % ORDER;
            int diff_b = (hare.b - tort.b + ORDER) % ORDER;
            printf("\nSetting up congruence equation:\n\n");
            printf("    (a_t - a_h) ≡ x(b_h - b_t) mod %d\n\n", ORDER);
            printf("    (%d - %d) ≡ x (%d - %d) mod %d\n\n", tort.a, hare.a, hare.b, tort.b, ORDER);
            printf("    %d * x ≡ %d mod %d\n", diff_b, diff_a, ORDER);

            int d = gcd_verbose(diff_b, ORDER);
            if(diff_a % d != 0) {
                printf("No solution! (gcd does not divide right hand side)\n\n");
                break;
            }
            int bb = diff_b / d, aa = diff_a / d, nn = ORDER / d;
            printf("\nReduced congruence:\n    %d * x ≡ %d mod %d\n\n", bb, aa, nn);

            int inv = modinv_verbose(bb, nn);
            if(inv == -1){ printf("\nNo inverse exists!\n\n"); break; }
            int x0 = ((long long)inv * aa) % nn;

            printf("\nAll possible solutions for x (modulo %d):\n\n", ORDER);
            for(int k=0; k<d; ++k) {
                int sol = (x0 + k*nn) % ORDER;
                printf("  Possible solution: x = %d", sol);
                int powcheck = modpow(G, sol, MODP);
                printf(" ; Check: %d^%d %% %d = %d", G, sol, MODP, powcheck);
                if(powcheck == H) printf("   <== Correct discrete log\n\n");
                else printf("\n");
            }
            break;
        }
    }
    return 0;
}
