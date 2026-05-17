import re
import sys

def expand_jedec_32bits(input_text):
    # 1. Determine default value from *F flag
    default_val = '0' if '*F0' in input_text else '1'
    
    qf_match = re.search(r'\*QF(\d+)', input_text)
    if not qf_match:
        raise ValueError("Could not find fuse count (*QF) field in JEDEC file.")
    total_fuses = int(qf_match.group(1))
    
    # 2. Initialize the entire fuse array with the default value
    fuse_array = [default_val] * total_fuses
    
    # 3. Parse and fill explicit allocation fields (*LXXXX)
    l_fields = re.findall(r'\*L(\d+)\s+([01\s]+)', input_text)
    
    for start_index_str, bit_string in l_fields:
        start_index = int(start_index_str)
        bits = bit_string.replace(" ", "").replace("\n", "").replace("\r", "")
        
        for i, bit in enumerate(bits):
            if start_index + i < total_fuses:
                fuse_array[start_index + i] = bit

    # 4. Calculate Fuse Checksum (Sum of all 8-bit fuse bytes)
    fuse_checksum = 0
    for i in range(0, total_fuses, 8):
        byte_bits = "".join(fuse_array[i:i+8])
        if len(byte_bits) < 8:
            byte_bits = byte_bits.ljust(8, '0')
        # Standard JEDEC checksum mirrors the bit order of each byte
        byte_val = int(byte_bits[::-1], 2)
        fuse_checksum = (fuse_checksum + byte_val) & 0xFFFF

    # 5. Construct the Longform Output Body (Row width = 32 bits)
    output_lines = []
    
    # Grab everything before the QF tag to keep original headers/comments
    header_end_idx = input_text.find('*QF')
    output_lines.append(input_text[:header_end_idx].strip())
    output_lines.append(f"*QF{total_fuses}*")
    
    row_size = 32  # 32 bits per row configuration
    for addr in range(0, total_fuses, row_size):
        chunk = fuse_array[addr:addr+row_size]
        chunk_str = "".join(chunk)
        
        # Append row format: *L<address> <bits>*
        # Keeping a space here as it is standard formatting for readability
        output_lines.append(f"*L{addr:05d} {chunk_str}")

    # Add the generated fuse checksum
    output_lines.append(f"*C{fuse_checksum:04X}*")
    
    # End of text transmission block
    output_body = "\n".join(output_lines) + "\n\x03"
    
    # 6. Calculate File Checksum (ASCII sum from STX to ETX)
    file_checksum = sum(ord(c) for c in output_body) + 0x02  # Include STX (0x02)
    file_checksum &= 0xFFFF
    
    final_jedec = f"\x02\n{output_body}{file_checksum:04x}"
    return final_jedec

# --- Execution ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: expand_jedec.py <input.jed> [output.jed]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.rsplit(".", 1)[0] + "_expanded.jed"

    try:
        with open(input_file, "r", encoding="ascii") as f:
            shortform_data = f.read()

        longform_jedec = expand_jedec_32bits(shortform_data)
        with open(output_file, "w", encoding="ascii") as f:
            f.write(longform_jedec)
        print(f"Success! Generated '{output_file}' with 32-bit width arrays.")
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error expanding JEDEC map: {e}")
        sys.exit(1)
