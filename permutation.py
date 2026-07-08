from itertools import permutations

# Ask user for values
A = input("Enter value for A: ")
B = input("Enter value for B: ")


groups = [
    [A, A, B],
    [A, B, B]
]

unique_permutations = []

for group in groups:
    for p in permutations(group):
        if p not in unique_permutations:
            unique_permutations.append(p)

print("\nGenerated permutations:")

for p in unique_permutations:
    print(" ".join(p))

print("\nTotal permutations:", len(unique_permutations))