#!/usr/bin/env bash

INPUT_DIR="../inputs"
ANSWER_DIR="../answers"
TIMEOUT=120

rm -f output-*.txt a.out

if [ -f "Makefile" ]; then
    make clean >/dev/null 2>&1
    make >/dev/null 2>&1 || exit 1
    executable="./a.out"

elif ls *.py >/dev/null 2>&1; then
    executable="python3 $(ls *.py | head -n 1)"

else
    exit 1
fi

passed=0

for i in {1..6}; do
    in="$INPUT_DIR/input-$i.txt"
    ans="$ANSWER_DIR/answer-$i.txt"
    out="output-$i.txt"

    timeout "$TIMEOUT" $executable < "$in" > "$out" 2>/dev/null || continue

    sed -i 's/[[:space:]]*$//' "$out"

    diff -q "$out" "$ans" >/dev/null && ((passed++))
done

echo "$passed/6"