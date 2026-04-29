for (( i=0; i<12; i++ ))
do
    # 1. Safely find the input file
    files=(tests/complex_tests/teapot_32x32/triangles/triangleInput${i}_memDump_*.hex)
    input_file="${files}"

    # Check if the file actually exists
    if [[ ! -e "$input_file" ]]; then
        echo "File for triangle ${i} not found, skipping..."
        continue
    fi

    # 2. Extract the numbers using robust string slicing
    filename=$(basename "$input_file")       # e.g., triangleInput0_memDump_1_81.hex
    
    numbers="${filename##*_memDump_}"        # Strips everything up to _memDump_ -> 1_81.hex
    numbers="${numbers%.hex}"                # Strips the .hex extension -> 1_81
    
    b="${numbers%_*}"                        # Extracts everything before the underscore -> 1
    t="${numbers#*_}"                        # Extracts everything after the underscore -> 81

    echo "Running Triangle ${i} | Blocks: ${b}, Threads: ${t}"

    # 3. Run the emulator
    python3 src/emulator.py --mem-format hex "$input_file" -b "$b" -t "$t" --start-pc 0x00000024 --arg-pointer 0x00100058

    # 4. Construct the expected output file name
    expected_file="tests/complex_tests/teapot_32x32/triangles/triangleOutput${i}_memDump_${b}_${t}.hex"

    # 5. Run the diff
    python3 diffs.py --compare --allow-approx memsim.hex "$expected_file" "diff_tri_${i}.txt"
    
    echo "----------------------------------------"
done