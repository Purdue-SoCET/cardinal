# SoCET GPU Emulator

## File Structure

Please follow the following file structure:

    - emulator/
        - docs/              # document for the simulator
            - eg: isa.txt

        - utils/             # commonly used utilities
            - eg: logger.py

        - src/
            - core/
                - eg: core.py
                - frontend/
                - backend/
                
            - mem/
                - eg: dcache.py

        - tests/             # test cases

## Usage

> The SoCET GPU Emulator only supports usage on Linux

To use the SoCET GPU Emulator, first activate the Python virtual environment by running the following commands in a Linux terminal:

```
cd ./gpu_sim/emulator
source venv/bin/activate
```

To run the emulator:
- First add an assembled binary file named `meminit.hex`
- Then run the command:
  ```
  make run
  ```
