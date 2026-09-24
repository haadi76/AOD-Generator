"""
Run this locally:  python compare_backups.py working.bak broken.bak

It strips the MIUI text header the same way extract.py does (finds 'ustar'
and backs up 257 bytes), then lists every tar member's name, mode, mtime,
size, and type from BOTH files, and prints only the differences.

This tells us definitively whether the problem is ordering, permissions,
timestamps, or missing directory entries - instead of guessing.
"""

import sys
import tarfile
import io


def load_members(bak_path):
    with open(bak_path, "rb") as f:
        data = f.read()
    offset = data.find(b"ustar")
    if offset == -1:
        raise ValueError(f"No ustar marker found in {bak_path}")
    tar_start = max(0, offset - 257)
    tar_bytes = data[tar_start:]

    members = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tar:
        for m in tar.getmembers():
            members.append({
                "name": m.name,
                "mode": oct(m.mode),
                "mtime": m.mtime,
                "size": m.size,
                "type": m.type,
                "uid": m.uid,
                "gid": m.gid,
            })
    return members


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_backups.py working.bak broken.bak")
        sys.exit(1)

    a = load_members(sys.argv[1])
    b = load_members(sys.argv[2])

    print(f"Working backup: {len(a)} members")
    print(f"Broken backup:  {len(b)} members")

    a_by_name = {m["name"]: m for m in a}
    b_by_name = {m["name"]: m for m in b}

    names_a = set(a_by_name)
    names_b = set(b_by_name)

    only_in_a = names_a - names_b
    only_in_b = names_b - names_a
    if only_in_a:
        print("\n--- Members ONLY in working backup ---")
        for n in sorted(only_in_a):
            print(" ", n)
    if only_in_b:
        print("\n--- Members ONLY in broken backup ---")
        for n in sorted(only_in_b):
            print(" ", n)

    print("\n--- Ordering (first 10 members of each) ---")
    print("Working:", [m["name"] for m in a[:10]])
    print("Broken: ", [m["name"] for m in b[:10]])
    same_order = [m["name"] for m in a] == [m["name"] for m in b]
    print("Same member order overall:", same_order)

    print("\n--- Field differences for members present in both ---")
    diff_count = 0
    for name in sorted(names_a & names_b):
        ma, mb = a_by_name[name], b_by_name[name]
        diffs = {k: (ma[k], mb[k]) for k in ma if ma[k] != mb[k]}
        if diffs:
            diff_count += 1
            print(f"{name}: {diffs}")
    if diff_count == 0:
        print("(no field differences found on shared members)")


if __name__ == "__main__":
    main()
