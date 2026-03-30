import sys
import argparse

#python DiffLavaMD.py result.txt reference.txt -p 4
def compare_files(file1_path, file2_path, precision):
    """
    Compares two files containing comma-separated floats line by line.
    precision: Number of decimal places to compare (sig figs after decimal).
    """
    try:
        with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()

        if len(lines1) != len(lines2):
            print(f"Warning: File lengths differ. File1: {len(lines1)} lines, File2: {len(lines2)} lines.")

        mismatches = 0
        total_lines = min(len(lines1), len(lines2))

        for i in range(total_lines):
            # Split lines by comma and strip whitespace
            parts1 = [p.strip() for p in lines1[i].split(',') if p.strip()]
            parts2 = [p.strip() for p in lines2[i].split(',') if p.strip()]

            if len(parts1) != len(parts2):
                print(f"Column mismatch at line {i+1}")
                mismatches += 1
                continue

            line_match = True
            for val1, val2 in zip(parts1, parts2):
                try:
                    v1 = round(float(val1), precision-1)
                    v2 = round(float(val2), precision-1)
                    
                    if v1 != v2:
                        line_match = False
                        break
                except ValueError:
                    if val1 != val2: 
                        line_match = False
                        break

            if not line_match:
                print(f"Difference found at line {i+1}:")
                print(f"   File1: {lines1[i].strip()}")
                print(f"   File2: {lines2[i].strip()}")
                mismatches += 1

        if mismatches == 0:
            print(f"✅ Success: Files match at {precision} decimal places.")
        else:
            print(f"\nTotal lines with differences: {mismatches}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two LavaMD output files.")
    parser.add_argument("file1", help="Path to the first text file")
    parser.add_argument("file2", help="Path to the second text file")
    parser.add_argument("-p", "--precision", type=int, default=4, 
                        help="Number of decimal places to check (default: 4)")

    args = parser.parse_args()
    
    compare_files(args.file1, args.file2, args.precision)