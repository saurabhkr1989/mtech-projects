#include <stdio.h>
#include <stdlib.h>

long long f(long long x, long long n) {
    return (x * x + 1) % n;
}

long long absll(long long x) {
    return x < 0 ? -x : x;
}

// Euclidean algorithm with step printing
long long gcd_steps(long long a, long long b) {
    printf("\nGCD Calculation Steps:\n");
    printf("|    A    |    B    |    Q    |    R    |\n");
    while (b != 0) {
        long long q = a / b;
        long long r = a % b;
        printf("| %6lld | %6lld | %6lld | %6lld |\n", a, b, q, r);
        a = b;
        b = r;
    }
    printf("| %6lld | %6lld |         |         |\n", a, b);
    return a;
}

int main() {
    long long n;
    int max_iter = 1000;
    printf("Enter n: ");
    scanf("%lld", &n);
    long long x = 2, y = 2, d = 1;
    int iter = 0;
    printf("\n|  X  | F(X) MOD N |  Y  | F(F(Y)) MOD N | |X-Y| MOD N |");
    printf("\n----------------------------------------------------------\n");
    while (d == 1 && iter < max_iter) {
        long long next_x = f(x, n);
        long long next_y = f(f(y, n), n);

        long long diff = absll(next_x - next_y) % n;
        
        printf("| %3lld | %12lld | %3lld | %15lld | %12lld |\n", x, next_x, y, next_y, diff);
        
        d = gcd_steps(diff, n);
        printf("GCD(|X-Y|, n) = %lld\n", d);

        if (d > 1 && d < n) {
            printf("\nNon-trivial factor found: %lld\n", d);
            break;
        }

        x = next_x;
        y = next_y;
        iter++;
    }

    if (d == n || d == 1) {
        printf("\nNo non-trivial factor found after %d iterations. %lld is likely prime.\n", max_iter, n);
    }

    return 0;
}